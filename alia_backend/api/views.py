import json
import logging
from datetime import datetime
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import User, Medicament, Assignment, SimSession
from .auth import hash_password, check_password, make_token, get_user_from_request
from . import alia_bridge

logger = logging.getLogger(__name__)


# ── helpers ───────────────────────────────────────────────────────────────────

def _body(request) -> dict:
    try:
        return json.loads(request.body)
    except Exception:
        return {}

def _ok(data: dict, status: int = 200) -> JsonResponse:
    return JsonResponse({'ok': True, **data}, status=status)

def _err(msg: str, status: int = 400) -> JsonResponse:
    return JsonResponse({'ok': False, 'error': msg}, status=status)

def _require_auth(request):
    user_id, role = get_user_from_request(request)
    if not user_id:
        return None, None, _err('Non authentifié', 401)
    try:
        user = User.objects.get(id=user_id, is_active=True)
    except User.DoesNotExist:
        return None, None, _err('Utilisateur introuvable', 404)
    return user, role, None

def _sync_assignment_from_session(user, sim):
    """
    Synchronise l'assignment du delegue depuis la derniere session.
    """
    try:
        assignment = Assignment.objects.filter(delegue=user, medicament=sim.medicament).first()
        if not assignment:
            return

        # On garde les meilleurs scores connus par module si disponibles
        if sim.score_contenu is not None:
            assignment.score_module1 = max(assignment.score_module1 or 0, sim.score_contenu or 0)
        if sim.score_comportement is not None:
            assignment.score_module2 = max(assignment.score_module2 or 0, sim.score_comportement or 0)
        if sim.score_voix is not None:
            assignment.score_module3 = max(assignment.score_module3 or 0, sim.score_voix or 0)
        if sim.score_final is not None:
            assignment.score_global = max(assignment.score_global or 0, sim.score_final or 0)

        # Logique de statut simple et explicite
        if assignment.score_global >= 80:
            assignment.statut = 'termine'
        elif assignment.score_global > 0:
            assignment.statut = 'en_cours'
        elif assignment.statut == 'non_commence':
            assignment.statut = 'en_cours'

        assignment.save()
    except Exception:
        pass


# ── AUTH ──────────────────────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(['POST'])
def login(request):
    data = _body(request)
    email    = data.get('email', '').strip().lower()
    password = data.get('password', '')
    if not email or not password:
        return _err('Email et mot de passe requis')
    try:
        user = User.objects.get(email=email, is_active=True)
    except User.DoesNotExist:
        return _err('Identifiants incorrects', 401)
    if not check_password(password, user.password_hash):
        return _err('Identifiants incorrects', 401)
    token = make_token(user.id, user.role)
    return _ok({
        'token': token,
        'role':  user.role,
        'user': {
            'id':         user.id,
            'first_name': user.first_name,
            'last_name':  user.last_name,
            'email':      user.email,
            'niveau':     user.niveau,
            'role':       user.role,
        }
    })


# ── DÉLÉGUÉ ───────────────────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(['GET'])
def delegue_profil(request):
    user, role, err = _require_auth(request)
    if err: return err

    assignments = Assignment.objects.filter(delegue=user).select_related('medicament')
    return _ok({
        'id':             user.id,
        'first_name':     user.first_name,
        'last_name':      user.last_name,
        'email':          user.email,
        'niveau':         user.calculate_niveau(),
        'current_module': user.current_module,
        'role':           user.role,
        'assignments': [
            {
                'medicament_id':   a.medicament.id,
                'medicament_nom':  a.medicament.nom,
                'score_module1':   a.score_module1,
                'score_module2':   a.score_module2,
                'score_module3':   a.score_module3,
                'score_global':    a.score_global,
                'statut':          a.statut,
            }
            for a in assignments
        ]
    })


@csrf_exempt
@require_http_methods(['GET'])
def delegue_historique(request):
    user, role, err = _require_auth(request)
    if err: return err

    sessions = SimSession.objects.filter(delegue=user).select_related('medicament')[:30]

    def _conv_tail(conv, n=10):
        if isinstance(conv, list):
            return conv[-n:]
        return []

    return _ok({
        'sessions': [
            {
                'id':               s.id,
                'medicament':       s.medicament.nom,
                'mode':             s.mode,
                'interlocuteur':    s.interlocuteur,
                'score_contenu':    s.score_contenu,
                'score_comportement': s.score_comportement,
                'score_voix':       s.score_voix,
                'score_final':      s.score_final,
                'nb_tours':         s.nb_tours,
                'bilan_text':       s.bilan_text,
                'objets_detectes':  s.objets_detectes,
                'started_at':       s.started_at.strftime('%Y-%m-%d %H:%M'),
                'ended_at':         s.ended_at.strftime('%Y-%m-%d %H:%M') if s.ended_at else None,
                'conversation':     _conv_tail(s.conversation_json),
            }
            for s in sessions
        ]
    })


# ── SIMULATION ────────────────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(['POST'])
def sim_start(request):
    user, role, err = _require_auth(request)
    if err: return err

    data          = _body(request)
    mode          = data.get('mode', 'training')        # training | exam
    interlocuteur = data.get('interlocuteur', 'medecin') # medecin | pharmacien
    medicament_id = data.get('medicament_id')

    # Démarrage simulation via bridge (flask si dispo, sinon local)
    start_result = alia_bridge.start_simulation(user.id, mode=mode, interlocuteur=interlocuteur)
    if not start_result.get('ok', False):
        return _err(f"Serveur Alia non prêt: {start_result.get('error', 'Unknown')}", 503)

    # Créer la session en DB
    try:
        med = Medicament.objects.get(id=medicament_id) if medicament_id else None
        if not med:
            # Prendre le produit actif du délégué
            asgn = Assignment.objects.filter(delegue=user, statut='en_cours').first()
            med  = asgn.medicament if asgn else Medicament.objects.first()

        sim = SimSession.objects.create(
            delegue=user, medicament=med,
            mode=mode, interlocuteur=interlocuteur
        )
    except Exception as e:
        return _err(f'Erreur création session: {e}')

    return _ok({
        'message': 'Simulation démarrée',
        'sim_id': sim.id,
        'mode': mode,
        'interlocuteur': interlocuteur,
        'medicament': med.nom if med else 'N/A',
        'backend': start_result.get('backend', 'unknown'),
    })


@csrf_exempt
@require_http_methods(['POST'])
def sim_message(request):
    user, role, err = _require_auth(request)
    if err: return err

    data    = _body(request)
    message = data.get('message', '').strip()
    interlocuteur = data.get('interlocuteur', 'medecin')
    if not message:
        return _err('Message vide')

    # Appeler le serveur Flask Alia
    result = alia_bridge.send_message(message, interlocuteur=interlocuteur, user_id=user.id)
    
    if 'error' in result:
        return _err(result['error'])

    return _ok({
        'response': result.get('response', ''),
        'persona': result.get('persona', 'Alia'),
        'mode': result.get('mode', 'training'),
    })


@csrf_exempt
@require_http_methods(['POST'])
def sim_stop(request):
    user, role, err = _require_auth(request)
    if err: return err

    # Envoyer un message "stop_sim" au serveur Flask pour arrêter la simulation
    result = alia_bridge.stop_simulation(user.id)
    
    if 'error' in result:
        return _ok({'message': 'Simulation arrêtée (serveur indisponible)'})

    # Mettre à jour la SimSession si on peut
    try:
        latest_sim = SimSession.objects.filter(delegue=user).order_by('-started_at').first()
        if latest_sim and not latest_sim.ended_at:
            latest_sim.ended_at = datetime.now()
            latest_sim.bilan_text = result.get('response', '')
            latest_sim.save()
    except Exception as e:
        logger.warning(f"Erreur mise à jour SimSession: {e}")

    return _ok({
        'message': 'Simulation arrêtée',
        'bilan': result.get('response', ''),
    })


@csrf_exempt
@require_http_methods(['POST'])
def sim_command(request):
    """Commandes annexes : eval, next, save."""
    user, role, err = _require_auth(request)
    if err: return err

    data    = _body(request)
    command = data.get('command', '').lower()

    # Envoyer la commande au serveur Flask
    result = alia_bridge.run_command(user.id, command)
    
    if 'error' in result:
        return _err(result['error'])

    return _ok({
        'response': result.get('response', ''),
        'command': command,
    })


# ── AVATAR STATE (polling depuis alia_avatar.html) ────────────────────────────

_avatar_state = {'state': 'idle', 'text': '', 'persona': 'ALIA'}

@csrf_exempt
@require_http_methods(['POST'])
def avatar_state_push(request):
    """agent.py pousse l'état ici via HTTP."""
    global _avatar_state
    _avatar_state = _body(request)
    return JsonResponse({'ok': True})

@csrf_exempt
@require_http_methods(['GET'])
def avatar_state_get(request):
    """alia_avatar.html poll cet endpoint toutes les 150ms."""
    return JsonResponse(_avatar_state)


# ── ADMIN ─────────────────────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(['GET'])
def admin_delegues(request):
    user, role, err = _require_auth(request)
    if err: return err
    if role != 'admin': return _err('Accès refusé', 403)

    delegues = User.objects.filter(role='delegue', is_active=True)
    return _ok({
        'delegues': [
            {
                'id':         d.id,
                'first_name': d.first_name,
                'last_name':  d.last_name,
                'email':      d.email,
                'niveau':     d.calculate_niveau(),
                'nb_produits': Assignment.objects.filter(delegue=d).count(),
                'assignments': [
                    {
                        'id': a.id,
                        'medicament_id': a.medicament.id,
                        'medicament_nom': a.medicament.nom,
                        'score_module1': a.score_module1,
                        'score_module2': a.score_module2,
                        'score_module3': a.score_module3,
                        'score_global': a.score_global,
                        'statut': a.statut,
                    }
                    for a in Assignment.objects.filter(delegue=d).select_related('medicament')
                ],
            }
            for d in delegues
        ]
    })

@csrf_exempt
@require_http_methods(['GET'])
def admin_assignments(request):
    """
    Flux explicite des assignments pour dashboard admin.
    Permet au frontend de reconstruire l'état même si la vue delegues change.
    """
    user, role, err = _require_auth(request)
    if err: return err
    if role != 'admin': return _err('Accès refusé', 403)

    assignments = Assignment.objects.select_related('delegue', 'medicament').all()
    return _ok({
        'assignments': [
            {
                'id': a.id,
                'delegue_id': a.delegue.id,
                'delegue_email': a.delegue.email,
                'medicament_id': a.medicament.id,
                'medicament_nom': a.medicament.nom,
                'score_module1': a.score_module1,
                'score_module2': a.score_module2,
                'score_module3': a.score_module3,
                'score_global': a.score_global,
                'statut': a.statut,
                'assigned_at': a.assigned_at.strftime('%Y-%m-%d %H:%M'),
            }
            for a in assignments
        ]
    })


@csrf_exempt
@require_http_methods(['POST'])
def admin_assign(request):
    """Assigne un médicament à un délégué."""
    user, role, err = _require_auth(request)
    if err: return err
    if role != 'admin': return _err('Accès refusé', 403)

    data          = _body(request)
    delegue_id    = data.get('delegue_id')
    medicament_id = data.get('medicament_id')

    if not delegue_id or not medicament_id:
        return _err('delegue_id et medicament_id requis')

    try:
        delegue    = User.objects.get(id=delegue_id, role='delegue')
        medicament = Medicament.objects.get(id=medicament_id)
    except User.DoesNotExist:
        return _err('Délégué introuvable')
    except Medicament.DoesNotExist:
        return _err('Médicament introuvable')

    asgn, created = Assignment.objects.get_or_create(
        delegue=delegue, medicament=medicament,
        defaults={'statut': 'non_commence'}
    )
    return _ok({
        'message':   'Assigné' if created else 'Déjà assigné',
        'assignment': {
            'delegue':     delegue.full_name(),
            'medicament':  medicament.nom,
            'score_global': asgn.score_global,
            'statut':       asgn.statut,
        }
    })


@csrf_exempt
@require_http_methods(['GET'])
def admin_medicaments(request):
    user, role, err = _require_auth(request)
    if err: return err
    if role != 'admin': return _err('Accès refusé', 403)

    meds = Medicament.objects.all()
    return _ok({
        'medicaments': [
            {'id': m.id, 'nom': m.nom, 'forme': m.forme, 'classe': m.classe_therapeutique}
            for m in meds
        ]
    })


@csrf_exempt
@require_http_methods(['GET', 'PUT', 'DELETE'])
def admin_assignment_detail(request, assignment_id):
    """GET/PUT/DELETE une assignation spécifique."""
    user, role, err = _require_auth(request)
    if err: return err
    if role != 'admin': return _err('Accès refusé', 403)

    try:
        assignment = Assignment.objects.get(id=assignment_id)
    except Assignment.DoesNotExist:
        return _err('Assignation introuvable', 404)

    # ── GET: Récupérer les détails ──
    if request.method == 'GET':
        return _ok({
            'assignment': {
                'id': assignment.id,
                'delegue_id': assignment.delegue.id,
                'delegue_name': assignment.delegue.full_name(),
                'medicament_id': assignment.medicament.id,
                'medicament_nom': assignment.medicament.nom,
                'score_module1': assignment.score_module1,
                'score_module2': assignment.score_module2,
                'score_module3': assignment.score_module3,
                'score_global': assignment.score_global,
                'statut': assignment.statut,
                'assigned_at': assignment.assigned_at.isoformat(),
                'updated_at': assignment.updated_at.isoformat(),
            }
        })

    # ── PUT: Modifier l'assignation ──
    elif request.method == 'PUT':
        data = _body(request)
        
        # Mettre à jour les scores et statut
        if 'score_module1' in data:
            assignment.score_module1 = int(data['score_module1'])
        if 'score_module2' in data:
            assignment.score_module2 = int(data['score_module2'])
        if 'score_module3' in data:
            assignment.score_module3 = int(data['score_module3'])
        if 'score_global' in data:
            assignment.score_global = int(data['score_global'])
        if 'statut' in data:
            statut = data['statut'].lower()
            if statut in ['non_commence', 'en_cours', 'termine']:
                assignment.statut = statut
        
        assignment.save()
        return _ok({
            'message': 'Assignation mise à jour',
            'assignment': {
                'id': assignment.id,
                'delegue_name': assignment.delegue.full_name(),
                'medicament_nom': assignment.medicament.nom,
                'score_global': assignment.score_global,
                'statut': assignment.statut,
            }
        })

    # ── DELETE: Supprimer l'assignation ──
    elif request.method == 'DELETE':
        delegue_name = assignment.delegue.full_name()
        medicament_nom = assignment.medicament.nom
        assignment.delete()
        return _ok({
            'message': f'Assignation supprimée: {delegue_name} → {medicament_nom}'
        })


@csrf_exempt
@require_http_methods(['GET'])
def medicaments_list(request):
    """Récupère la liste de tous les médicaments (accessible aux délégués & admins)."""
    user, role, err = _require_auth(request)
    if err: return err

    meds = Medicament.objects.all().values(
        'id', 'nom', 'forme', 'classe_therapeutique', 'indications'
    )
    return _ok({'medicaments': list(meds)})


@csrf_exempt
@require_http_methods(['POST'])
def admin_create_user(request):
    """Créer un délégué depuis l'interface admin."""
    user, role, err = _require_auth(request)
    if err: return err
    if role != 'admin': return _err('Accès refusé', 403)

    data = _body(request)
    email      = data.get('email', '').strip().lower()
    password   = data.get('password', '')
    first_name = data.get('first_name', '')
    last_name  = data.get('last_name', '')

    if not all([email, password, first_name, last_name]):
        return _err('Tous les champs sont requis')
    if User.objects.filter(email=email).exists():
        return _err('Email déjà utilisé')

    new_user = User.objects.create(
        email=email,
        password_hash=hash_password(password),
        first_name=first_name,
        last_name=last_name,
        role='delegue',
    )
    return _ok({'message': 'Délégué créé', 'id': new_user.id})
