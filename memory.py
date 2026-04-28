"""
memory.py - Alia Agent
Gestion de la mémoire long terme des sessions de formation.

Responsabilités :
  1. Sauvegarde de la conversation complète (JSON) à la fin de chaque session
  2. Génération d'un résumé automatique : points faibles, progression, où le délégué s'est arrêté
  3. Mise à jour du score et du niveau dans le CSV après évaluation
  4. Évaluation globale inter-modules → niveau final : débutant / intermédiaire / professionnel

Structure des fichiers générés :
  sessions/
    delegue_1_Varispray_2026-03-30_14h22.json   ← conversation complète + résumé
    delegue_1_Varispray_2026-03-30_14h22_summary.json  ← résumé seul (pour rechargement rapide)

  delegue_sessions.csv     ← mis à jour (score_module_1, niveau)
  product_assignments.csv  ← mis à jour (product_scores)
"""

import os
import json
import csv
import requests
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from dotenv import load_dotenv

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
SUMMARY_MODEL = "llama-3.1-8b-instant"   # modèle léger pour les résumés

# Dossier où sont stockées les sessions
SESSIONS_DIR = Path("sessions")
SESSIONS_DIR.mkdir(exist_ok=True)

# Seuils pour la progression de niveau
SCORE_SEUIL_INTERMEDIAIRE = 65   # score moyen ≥ 65 → intermédiaire
SCORE_SEUIL_PROFESSIONNEL = 85   # score moyen ≥ 85 → professionnel


# ══════════════════════════════════════════════════════════════════════════════
# APPEL LLM POUR LE RÉSUMÉ
# ══════════════════════════════════════════════════════════════════════════════

def _call_groq_summary(system: str, user: str) -> str:
    """Appelle Groq pour générer le résumé de session."""
    if not GROQ_API_KEY:
        return "[ERREUR] GROQ_API_KEY manquant"

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": SUMMARY_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        "max_tokens": 600,
        "temperature": 0.2,   # plus bas = plus factuel pour les résumés
    }

    try:
        response = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"[ERREUR résumé] {str(e)}"


# ══════════════════════════════════════════════════════════════════════════════
# GÉNÉRATION DU RÉSUMÉ DE SESSION
# ══════════════════════════════════════════════════════════════════════════════

def generate_session_summary(
    delegue_name: str,
    product_name: str,
    module_reached: str,
    conversation_history: List[dict],
    scores: Dict[str, int],
) -> dict:
    """
    Génère un résumé structuré de la session via LLM.
    Retourne un dict avec les points faibles, forces, et recommandations.
    """
    # Construire le texte de la conversation pour le LLM
    conv_text = "\n".join([
        f"{'Alia' if t['role'] == 'alia' else delegue_name} : {t['content']}"
        for t in conversation_history
    ])

    system = """Tu es un assistant pédagogique qui analyse des sessions de formation pharmaceutique.
Tu génères des résumés structurés en JSON uniquement. Pas de texte avant ou après le JSON."""

    user = f"""Analyse cette session de formation de {delegue_name} sur {product_name}.
Module atteint : {module_reached}
Scores : {json.dumps(scores)}

CONVERSATION :
{conv_text[:4000]}

Génère UNIQUEMENT ce JSON :
{{
  "points_forts": ["<point fort 1>", "<point fort 2>"],
  "points_faibles": ["<point faible 1>", "<point faible 2>"],
  "concepts_non_maitrisés": ["<concept>", "<concept>"],
  "ou_il_s_est_arrete": "<description courte de là où la session s'est terminée>",
  "recommandations_prochaine_session": ["<recommandation 1>", "<recommandation 2>"],
  "evaluation_qualitative": "<débutant|intermédiaire|professionnel> — justification courte"
}}"""

    raw = _call_groq_summary(system, user)

    # Parser le JSON
    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(raw[start:end])
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback si le LLM ne retourne pas du JSON propre
    return {
        "points_forts": [],
        "points_faibles": [],
        "concepts_non_maitrisés": [],
        "ou_il_s_est_arrete": module_reached,
        "recommandations_prochaine_session": [],
        "evaluation_qualitative": "analyse indisponible",
        "raw_response": raw[:500],
    }


# ══════════════════════════════════════════════════════════════════════════════
# SAUVEGARDE DE SESSION
# ══════════════════════════════════════════════════════════════════════════════

def save_session(
    delegue_id: int,
    delegue_name: str,
    product_name: str,
    module_reached: str,
    conversation_history: List[dict],
    scores: Dict[str, int],
    generate_summary: bool = True,
) -> Path:
    """
    Sauvegarde la conversation complète + résumé dans sessions/.
    Retourne le chemin du fichier sauvegardé.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d_%Hh%M")
    product_slug = product_name.replace(" ", "_").replace("/", "-")[:30]
    filename = f"delegue_{delegue_id}_{product_slug}_{timestamp}.json"
    filepath = SESSIONS_DIR / filename

    # Générer le résumé si demandé
    summary = {}
    if generate_summary and len(conversation_history) > 2:
        print("[Memory] Génération du résumé de session...")
        summary = generate_session_summary(
            delegue_name=delegue_name,
            product_name=product_name,
            module_reached=module_reached,
            conversation_history=conversation_history,
            scores=scores,
        )

    session_data = {
        "meta": {
            "delegue_id": delegue_id,
            "delegue_name": delegue_name,
            "product_name": product_name,
            "module_reached": module_reached,
            "timestamp": timestamp,
            "nb_messages": len(conversation_history),
            "scores": scores,
        },
        "summary": summary,
        "conversation": conversation_history,
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(session_data, f, ensure_ascii=False, indent=2)

    print(f"[Memory] Session sauvegardée : {filepath}")
    return filepath


# ══════════════════════════════════════════════════════════════════════════════
# CHARGEMENT DE LA DERNIÈRE SESSION
# ══════════════════════════════════════════════════════════════════════════════

def load_last_session(delegue_id: int, product_name: str) -> Optional[dict]:
    """
    Charge la dernière session sauvegardée pour ce délégué et ce produit.
    Retourne None si aucune session trouvée.
    """
    product_slug = product_name.replace(" ", "_").replace("/", "-")[:30]
    prefix = f"delegue_{delegue_id}_{product_slug}_"

    matching = sorted(
        [f for f in SESSIONS_DIR.iterdir() if f.name.startswith(prefix)],
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )

    if not matching:
        return None

    with open(matching[0], "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"[Memory] Dernière session chargée : {matching[0].name}")
    return data


def get_session_context(delegue_id: int, product_name: str) -> str:
    """
    Retourne un texte de contexte de la dernière session à injecter dans le prompt.
    Utilisé pour que Alia se souvienne des sessions précédentes.
    """
    last = load_last_session(delegue_id, product_name)
    if not last:
        return ""

    summary = last.get("summary", {})
    meta    = last.get("meta", {})

    lines = [
        f"=== CONTEXTE SESSION PRÉCÉDENTE ({meta.get('timestamp', '')}) ===",
        f"Module atteint : {meta.get('module_reached', 'N/A')}",
        f"Scores : {meta.get('scores', {})}",
    ]

    if summary.get("points_faibles"):
        lines.append(f"Points faibles identifiés : {', '.join(summary['points_faibles'])}")

    if summary.get("concepts_non_maitrisés"):
        lines.append(f"Concepts à retravailler : {', '.join(summary['concepts_non_maitrisés'])}")

    if summary.get("ou_il_s_est_arrete"):
        lines.append(f"Arrêté à : {summary['ou_il_s_est_arrete']}")

    if summary.get("recommandations_prochaine_session"):
        recs = summary["recommandations_prochaine_session"]
        lines.append(f"À reprendre : {', '.join(recs)}")

    lines.append("=" * 50)
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# MISE À JOUR DES SCORES ET DU NIVEAU
# ══════════════════════════════════════════════════════════════════════════════

def update_scores(
    delegue_id: int,
    product_name: str,
    new_score: int,
    module: str,
    session_csv: str = "delegue_sessions.csv",
    assignments_csv: str = "product_assignments.csv",
):
    """
    Met à jour les scores dans les CSV après une évaluation.
    - product_assignments.csv : score du produit évalué
    - delegue_sessions.csv : score_module_X et niveau si seuil atteint
    """
    # ── 1. Mettre à jour product_assignments.csv ──────────────────────────────
    try:
        rows = []
        with open(assignments_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            for row in reader:
                if int(row["delegue_id"]) == delegue_id:
                    products = row["assigned_products"].split("|")
                    scores   = row["product_scores"].split("|")

                    for i, p in enumerate(products):
                        if p.strip() == product_name.strip():
                            scores[i] = str(new_score)
                            break

                    row["product_scores"] = "|".join(scores)
                rows.append(row)

        with open(assignments_csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        print(f"[Memory] product_assignments.csv mis à jour — {product_name} : {new_score}/100")

    except Exception as e:
        print(f"[Memory] Erreur mise à jour assignments : {e}")

    # ── 2. Mettre à jour delegue_sessions.csv ────────────────────────────────
    try:
        rows = []
        with open(session_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            for row in reader:
                if int(row["delegue_id"]) == delegue_id:
                    # Mettre à jour le score du module
                    score_key = f"score_{module}"
                    if score_key in row:
                        row[score_key] = str(new_score)

                    # Mettre à jour la date de dernière session
                    if "date_last_session" in row:
                        row["date_last_session"] = datetime.now().strftime("%Y-%m-%d")

                rows.append(row)

        with open(session_csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        print(f"[Memory] delegue_sessions.csv mis à jour — {score_key} : {new_score}")

    except Exception as e:
        print(f"[Memory] Erreur mise à jour sessions : {e}")


# ══════════════════════════════════════════════════════════════════════════════
# ÉVALUATION GLOBALE INTER-MODULES
# ══════════════════════════════════════════════════════════════════════════════

def compute_global_level(
    delegue_id: int,
    delegue_name: str,
    product_name: str,
    scores_by_module: Dict[str, int],
    session_csv: str = "delegue_sessions.csv",
) -> str:
    """
    Calcule le niveau global du délégué après avoir complété les 3 modules.
    Met à jour le niveau dans le CSV.
    Retourne le niveau : 'debutant' | 'intermediaire' | 'professionnel'
    """
    if not scores_by_module:
        return "debutant"

    score_moyen = sum(scores_by_module.values()) / len(scores_by_module)

    if score_moyen >= SCORE_SEUIL_PROFESSIONNEL:
        nouveau_niveau = "professionnel"
    elif score_moyen >= SCORE_SEUIL_INTERMEDIAIRE:
        nouveau_niveau = "intermediaire"
    else:
        nouveau_niveau = "debutant"

    # Mettre à jour le niveau dans le CSV
    try:
        rows = []
        with open(session_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            for row in reader:
                if int(row["delegue_id"]) == delegue_id:
                    if "niveau" in row:
                        row["niveau"] = nouveau_niveau
                    if "current_module" in row:
                        row["current_module"] = "1"   # reset pour prochain produit
                rows.append(row)

        with open(session_csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        print(f"[Memory] Niveau mis à jour → {nouveau_niveau} (score moyen : {score_moyen:.0f}/100)")

    except Exception as e:
        print(f"[Memory] Erreur mise à jour niveau : {e}")

    return nouveau_niveau


def generate_global_evaluation(
    delegue_name: str,
    product_name: str,
    scores_by_module: Dict[str, int],
    niveau_final: str,
    all_sessions: List[dict],
) -> str:
    """
    Génère un bilan global complet après les 3 modules via LLM.
    Retourne un texte de feedback structuré.
    """
    score_moyen = sum(scores_by_module.values()) / max(len(scores_by_module), 1)

    # Résumés des sessions précédentes
    summaries_text = ""
    for s in all_sessions:
        meta    = s.get("meta", {})
        summary = s.get("summary", {})
        summaries_text += (
            f"\n- Module {meta.get('module_reached', '?')} | "
            f"Score : {meta.get('scores', {})} | "
            f"Points faibles : {summary.get('points_faibles', [])}"
        )

    system = """Tu es Alia, formatrice pharmaceutique senior.
Tu génères un bilan global de formation après que le délégué a complété les 3 modules sur un produit.
Sois directe, honnête, bienveillante. Parle directement au délégué."""

    user = f"""Génère le bilan global de {delegue_name} sur {product_name}.

Scores par module : {json.dumps(scores_by_module)}
Score moyen : {score_moyen:.0f}/100
Niveau attribué : {niveau_final}

Historique des sessions :{summaries_text if summaries_text else " (première session)"}

Structure du bilan :
1. Annonce du niveau attribué avec justification (2-3 phrases)
2. Ce qu'il maîtrise vraiment bien (2-3 points concrets)
3. Ce qu'il doit encore travailler (2-3 points actionnables)
4. Conseil pour la suite : comment continuer à progresser
5. Mot de fin motivant et sincère

Ton : direct, chaleureux, comme un vrai formateur qui connaît ce délégué."""

    return _call_groq_summary(system, user)


# ══════════════════════════════════════════════════════════════════════════════
# UTILITAIRE — lister les sessions d'un délégué
# ══════════════════════════════════════════════════════════════════════════════

def list_sessions(delegue_id: int) -> List[dict]:
    """Retourne toutes les sessions sauvegardées pour un délégué."""
    prefix = f"delegue_{delegue_id}_"
    sessions = []

    for f in sorted(SESSIONS_DIR.iterdir(), key=lambda x: x.stat().st_mtime):
        if f.name.startswith(prefix) and f.suffix == ".json":
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    sessions.append(json.load(fp))
            except Exception:
                pass

    return sessions


def print_delegue_history(delegue_id: int, delegue_name: str):
    """Affiche l'historique complet des sessions d'un délégué."""
    sessions = list_sessions(delegue_id)

    if not sessions:
        print(f"[Memory] Aucune session trouvée pour {delegue_name}")
        return

    print(f"\n{'=' * 60}")
    print(f"  HISTORIQUE — {delegue_name}")
    print(f"{'=' * 60}")

    for s in sessions:
        meta    = s.get("meta", {})
        summary = s.get("summary", {})
        print(f"\n  📅 {meta.get('timestamp', '?')} | {meta.get('product_name', '?')}")
        print(f"     Module atteint : {meta.get('module_reached', '?')}")
        print(f"     Scores : {meta.get('scores', {})}")
        print(f"     Messages : {meta.get('nb_messages', 0)}")
        if summary.get("points_faibles"):
            print(f"     Points faibles : {', '.join(summary['points_faibles'])}")
        if summary.get("ou_il_s_est_arrete"):
            print(f"     Arrêté à : {summary['ou_il_s_est_arrete']}")