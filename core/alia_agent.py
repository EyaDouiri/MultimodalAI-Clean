"""
Agent Principal ALIA
- Orchestration des modules et formations
- Gestion de la conversation interactive
- Logique décisionnelle (formation, évaluation, redirection)
- Interface naturelle et fluide
"""

import json
from typing import Dict, Tuple, List, Optional
from datetime import datetime
from pathlib import Path
from core.delegate_profile import DelegateProfile, load_delegate_profile, DelegateLevel
from modules.module_1_presentation import Module1Presentation
from generation.engine_module1 import Module1Engine


class ALIAAgent:
    """Agent ALIA - Formateur Pharmaceutique Intelligent"""
    
    # États de conversation
    STATE_INIT = "init"
    STATE_ASSESSING = "assessing"
    STATE_FORMING = "forming"
    STATE_QUESTIONING = "questioning"
    STATE_EVALUATING = "evaluating"
    STATE_REDIRECTING = "redirecting"
    STATE_COMPLETED = "completed"
    
    def __init__(self, delegate_id: str, delegate_name: str = None, ollama_model: str = "llama2"):
        """Initialise ALIA avec un délégué"""
        self.delegate_profile = load_delegate_profile(delegate_id, delegate_name)
        self.module1 = Module1Presentation(self.delegate_profile, ollama_model)
        self.state = self.STATE_INIT
        self.conversation_history = []
        self.turn_count = 0
        self.assessment_step = 0
        self.current_question = None
        self.current_context = "indications"
        self.greeting_given = False
        
        print(f"\n🤖 ALIA chargé pour {self.delegate_profile.name}")
        print(f"   Produits assignés: {', '.join(self.delegate_profile.get_assigned_products())}")
        print(f"   Niveau actuel: {self.delegate_profile.current_level.value}")
    
    def process_input(self, user_input: str) -> Dict:
        """Traite l'input utilisateur et génère la réponse"""
        
        self.turn_count += 1
        self.conversation_history.append({
            'turn': self.turn_count,
            'user': user_input,
            'timestamp': datetime.now().isoformat()
        })
        
        # Dispatcher selon l'état
        if self.state == self.STATE_INIT:
            return self._handle_init(user_input)
        elif self.state == self.STATE_ASSESSING:
            return self._handle_assessment(user_input)
        elif self.state == self.STATE_FORMING:
            return self._handle_formation(user_input)
        elif self.state == self.STATE_QUESTIONING:
            return self._handle_question(user_input)
        elif self.state == self.STATE_EVALUATING:
            return self._handle_evaluation(user_input)
        elif self.state == self.STATE_REDIRECTING:
            return self._handle_redirect(user_input)
        else:
            return {'message': '❌ État inconnu'}
    
    def _handle_init(self, user_input: str) -> Dict:
        """Gère l'initialisation (premier message)"""
        
        # Salutation
        if not self.greeting_given:
            greeting = f"""Salut {self.delegate_profile.name}! 👋

Je suis ALIA, ton formateur pharmaceutique personnel.

Je vois que tu as {len(self.delegate_profile.get_assigned_products())} produits à maîtriser:
{self._format_products_list(self.delegate_profile.get_assigned_products())}

Aujourd'hui on va travailler sur le Module 1: **La Bonne Présentation du Produit**

Je vais d'abord évaluer ton niveau, puis adapter la formation en conséquence.

Prêt? 🚀"""
            
            self.greeting_given = True
            self.state = self.STATE_ASSESSING
            
            self.conversation_history[-1]['alia'] = greeting
            
            return {
                'status': 'ready',
                'message': greeting,
                'delegate': self.delegate_profile.name,
                'level': self.delegate_profile.current_level.value,
                'next_step': 'assessment'
            }
        
        # Deuxième interaction: passer à évaluation
        self.state = self.STATE_ASSESSING
        return self._handle_assessment(user_input)
    
    def _handle_assessment(self, user_input: str) -> Dict:
        """Évaluation du niveau initial"""

        # Question 1
        if self.assessment_step == 0:
            assessment_prompt = f"""Bonjour {self.delegate_profile.name}!

Avant de commencer, je dois comprendre ton niveau actuel.

**Question 1/3**: Parmi tes produits assignés ({', '.join(self.delegate_profile.get_assigned_products()[:2])}), 
lequel maîtrises-tu le mieux en termes de **présentation** et pourquoi?

(Ta réponse m'aidera à adapter le niveau de formation.) 🔍"""
            self.state = self.STATE_ASSESSING
            self.current_question = assessment_prompt
            self.assessment_step = 1
            self.conversation_history[-1]['alia'] = assessment_prompt

            return {
                'status': 'assessing',
                'message': assessment_prompt,
                'phase': 'assessment_1'
            }

        # Réponse Question 1
        if self.assessment_step == 1:
            if self._is_off_topic_response(user_input):
                msg = f"""Hé, tu peux répondre à la question? 😊

Elle parlait de tes produits assignés - lequel maîtrises-tu le mieux et pourquoi?

Essaye à nouveau! 👇"""
                self.conversation_history[-1]['alia'] = msg
                return {
                    'status': 'assessing',
                    'message': msg,
                    'phase': 'assessment_1_retry'
                }

            self.module1.assessment.evaluate_response(user_input)
            self.assessment_step = 2
            q2 = f"""Bien! Je comprends mieux.

**Question 2/3**: Si un docteur te demande \"Pourquoi prescrire notamment {self.delegate_profile.get_assigned_products()[0]}?\",
comment tu répondrais en 30 secondes?

(Je veux voir ta capacité à synthétiser les indications) 📝"""
            self.current_question = q2
            self.conversation_history[-1]['alia'] = q2

            return {
                'status': 'assessing',
                'message': q2,
                'phase': 'assessment_2'
            }

        # Réponse Question 2
        if self.assessment_step == 2:
            if self._is_off_topic_response(user_input):
                msg = f"""Allez, focalise! 👷

Je demandais: \"Pourquoi prescrire notamment {self.delegate_profile.get_assigned_products()[0]}?\"

Comment tu répondrais? 👇"""
                self.conversation_history[-1]['alia'] = msg
                return {
                    'status': 'assessing',
                    'message': msg,
                    'phase': 'assessment_2_retry'
                }

            self.module1.assessment.evaluate_response(user_input)
            assessment_summary = self.module1.assessment.get_summary()
            level_emojis = {
                'debutant': '🟢',
                'intermediaire': '🟡',
                'professionnel': '🔴'
            }

            summary_msg = f"""{level_emojis.get(assessment_summary['current_level'], '⭕')} **Évaluation complétée!**

Ton niveau détecté: **{assessment_summary['current_level'].upper()}**
Confiance: {int(assessment_summary['confidence'] * 100)}%

Voilà! Je vais adapter ma formation à ce niveau.

Maintenant, passons à la **FORMATION**. 🎓

On va commencer par {self.delegate_profile.get_assigned_products()[0]}.
Prêt?"""

            self.state = self.STATE_FORMING
            self.conversation_history[-1]['alia'] = summary_msg
            self.assessment_step = 3

            return {
                'status': 'assessment_complete',
                'message': summary_msg,
                'level': assessment_summary['current_level'],
                'next_phase': 'formation'
            }

        # Si on est déjà à la fin
        return {
            'status': 'assessing',
            'message': 'Bon... on va continuer. Dis-moi ce que tu sais sur ton produit (FerBiotic).'
        }
    
    def _handle_formation(self, user_input: str) -> Dict:
        """Gère la phase de formation"""
        
        # Choisir le produit (premier produit assigné)
        products = self.delegate_profile.get_assigned_products()
        if not products:
            return {'status': 'error', 'message': 'Aucun produit assigné'}
        
        if self.module1.current_product is None:
            # Lancer la formation
            formation_result = self.module1.start_formation(products[0])
            
            if formation_result['status'] != 'success':
                return formation_result
            
            formation_text = formation_result['formation']
            
            # Ajouter instruction
            full_message = f"""📚 **FORMATION - {products[0]}**
Niveau: {self.delegate_profile.current_level.value.upper()}

{formation_text}

---

Maintenant que tu as lu cette formation, je vais te poser une question pour vérifier ta compréhension. 👇"""
            
            self.conversation_history[-1]['alia'] = full_message
            self.state = self.STATE_QUESTIONING
            
            # Générer la première question
            question_result = self.module1.poser_question_evaluation()
            self.current_question = question_result['question']
            
            return {
                'status': 'formation_presented',
                'product': products[0],
                'formation': formation_text,
                'message': full_message,
                'question': self.current_question,
                'next_phase': 'question'
            }
        
        # Vérifier si input = "prêt" ou similaire pour poser la question
        if user_input.lower() in ['oui', 'ok', 'pret', 'prêt', 'c bon', 'ok compris', 'y']:
            self.state = self.STATE_QUESTIONING
            
            question_result = self.module1.poser_question_evaluation()
            self.current_question = question_result['question']
            
            msg = f"""Bien! Voici ma première question:

**{self.current_question}** 🤔

À toi!"""
            
            self.conversation_history[-1]['alia'] = msg
            
            return {
                'status': 'question_ready',
                'message': msg,
                'question': self.current_question
            }
        
        return {
            'status': 'formation_ongoing',
            'message': 'Je vois. Prêt pour la question test?'
        }
    
    def _handle_question(self, user_input: str) -> Dict:
        """Gère la phase de questions d'évaluation"""
        
        if not self.current_question:
            return {'status': 'error', 'message': 'Pas de question en cours'}
        
        # Évaluer la réponse
        eval_result = self.module1.evaluer_reponse_delegue(user_input, self.current_question)
        
        if eval_result['status'] != 'success':
            return eval_result
        
        score = eval_result['score']
        feedback = eval_result['feedback']
        
        # Formater le retour
        score_visual = "🟢" if score >= 7 else "🟡" if score >= 5 else "🔴"
        
        response_msg = f"""{score_visual} **Score: {score}/10**

{feedback}

---

"""
        
        # Décider la suite
        if score >= 7:
            # Bon score: passer au prochain produit ou terminer session
            remaining_products = [p for p in self.delegate_profile.get_assigned_products() 
                                 if p != self.module1.current_product]
            
            if remaining_products:
                response_msg += f"""Excellent! Tu progresses bien sur {self.module1.current_product}.

Veux-tu continuer avec un autre produit? ({', '.join(remaining_products[:2])})
Ou tu veux aller plus loin sur {self.module1.current_product}?"""
                
                self.state = self.STATE_FORMING
            else:
                response_msg += """Bravo! T'as maîtrisé tous les produits du Module 1! 🎉

Tu peux continuer avec une autre session de révision, ou passer aux autres modules."""
                self.state = self.STATE_COMPLETED
        
        else:
            # Score moyen/faible: proposer révision
            response_msg += f"""Tu peux mieux faire! 💪

Veux-tu qu'on révise les points clés de {self.module1.current_product},
ou tu préfères répondre à une autre question?"""
            
            self.state = self.STATE_FORMING  # Revenir à formation pour révision
        
        self.conversation_history[-1]['alia'] = response_msg
        
        return {
            'status': 'question_evaluated',
            'score': score,
            'feedback': feedback,
            'message': response_msg,
            'level': eval_result['level'],
            'next_action': eval_result['next_action']
        }
    
    def _handle_evaluation(self, user_input: str) -> Dict:
        """Gère l'évaluation continue"""
        return {'status': 'evaluating', 'message': 'Évaluation en cours...'}
    
    def _handle_redirect(self, user_input: str) -> Dict:
        """Gère la redirection vers produits assignés"""
        return {'status': 'redirecting', 'message': 'Redirection en cours...'}
    
    def _format_products_list(self, products: List[str]) -> str:
        """Formate la liste des produits"""
        return "\n".join([f"  • {p}" for p in products])
    
    def _is_off_topic_response(self, user_input: str) -> bool:
        """Vérifie si la réponse est hors-sujet"""
        off_topic_keywords = ["beau", "météo", "soleil", "pluie", "temps", "manger", 
                             "sport", "vacances", "musique", "film", "voiture", "bien"]
        
        user_lower = user_input.lower()
        
        # Si réponse contient SEULEMENT des mots hors-contexte
        contains_off_topic = any(kw in user_lower for kw in off_topic_keywords)
        
        # Aucun mot médical/produit
        medical_keywords = ["produit", "médicament", "patient", "docteur", "prescription",
                           "indication", "contre", "effet", "dose", "traité", "prescri",
                           "prescrire", "feriotic", "magnésol", "vitamin"]
        contains_medical = any(kw in user_lower for kw in medical_keywords)
        
        # Trop court
        is_very_short = len(user_input.split()) < 3
        
        return (contains_off_topic and not contains_medical) or is_very_short
    
    def get_status(self) -> Dict:
        """Retourne l'état complet d'ALIA"""
        return {
            'state': self.state,
            'turn': self.turn_count,
            'delegate': self.delegate_profile.to_dict(),
            'module1_status': self.module1.get_current_status(),
            'conversation_turns': len(self.conversation_history)
        }
    
    def end_session(self) -> str:
        """Termine la session et sauvegarde"""
        self.state = self.STATE_COMPLETED
        
        # Sauvegarder
        session_path = self.module1.save_session()
        
        summary = f"""
╔═══════════════════════════════════════╗
║      RÉSUMÉ SESSION ALIA - MODULE 1     ║
╚═══════════════════════════════════════╝

Délégué: {self.delegate_profile.name}
Niveau détecté: {self.delegate_profile.current_level.value.upper()}
Progrès global: {self.delegate_profile.overall_progress}%

Produits travaillés: {len(self.module1.session_data['products_covered'])}
Questions posées: {len([i for i in self.module1.session_data['interactions'] if i['type'] == 'question_asked'])}

📊 Session sauvegardée: {session_path}

À bientôt! 👋
"""
        
        return summary
    
    def save_conversation(self, output_dir: str = "tests/results") -> str:
        """Sauvegarde l'historique complet de conversation"""
        from pathlib import Path
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"alia_conversation_{self.delegate_profile.delegate_id}_{timestamp}.json"
        filepath = output_path / filename
        
        data = {
            'delegate': self.delegate_profile.to_dict(),
            'session_start': self.conversation_history[0]['timestamp'] if self.conversation_history else None,
            'total_turns': self.turn_count,
            'conversation': self.conversation_history,
            'final_status': self.get_status()
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"✓ Conversation sauvegardée: {filepath}")
        return str(filepath)
