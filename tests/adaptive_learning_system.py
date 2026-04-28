#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ADAPTIVE LEARNING SYSTEM
=========================
Adapte les réponses pédagogiques selon le niveau de l'utilisateur
"""

import json
from typing import Dict, List, Optional

print("="*80)
print("🎓 SYSTÈME ADAPTATIF - FORMATION PERSONNALISÉE")
print("="*80)

# ============================================================================
# 1. PROFIL UTILISATEUR & DÉTECTEUR DE NIVEAU
# ============================================================================

class UserProfile:
    """Gère le profil et le niveau de l'utilisateur"""
    
    LEVELS = {
        "novice": {
            "level": 1,
            "min_score": 0,
            "max_score": 25,
            "description": "Nouveau délégué sans connaissance pharmaceutique"
        },
        "intermediate": {
            "level": 2,
            "min_score": 26,
            "max_score": 50,
            "description": "Délégué avec expérience basique"
        },
        "advanced": {
            "level": 3,
            "min_score": 51,
            "max_score": 75,
            "description": "Délégué expérimenté"
        },
        "expert": {
            "level": 4,
            "min_score": 76,
            "max_score": 100,
            "description": "Expert pharmacien/scientifique"
        }
    }
    
    def __init__(self, user_id: str, initial_level: str = "intermediate"):
        self.user_id = user_id
        self.current_level = initial_level
        self.score = self.LEVELS[initial_level]["min_score"] + 12
        self.interaction_count = 0
        self.correct_answers = 0
        self.interaction_history = []
    
    def update_score(self, points: int, interaction_type: str):
        """Met à jour le score utilisateur"""
        self.score = max(0, min(100, self.score + points))
        self.interaction_count += 1
        
        if points > 0:
            self.correct_answers += 1
        
        # Déterminer le nouveau niveau
        old_level = self.current_level
        for level_name, level_info in self.LEVELS.items():
            if level_info["min_score"] <= self.score <= level_info["max_score"]:
                self.current_level = level_name
                break
        
        # Enregistrer
        self.interaction_history.append({
            "interaction": interaction_type,
            "points": points,
            "score": self.score,
            "level": self.current_level,
            "level_changed": old_level != self.current_level
        })
        
        if old_level != self.current_level:
            print(f"   🎖️  Progression utilisateur: {old_level} → {self.current_level}")
    
    def get_profile(self) -> Dict:
        """Retourne le profil utilisateur"""
        level_info = self.LEVELS[self.current_level]
        accuracy = self.correct_answers / self.interaction_count if self.interaction_count > 0 else 0
        
        return {
            "user_id": self.user_id,
            "current_level": self.current_level,
            "level_description": level_info["description"],
            "score": self.score,
            "accuracy": accuracy,
            "interaction_count": self.interaction_count,
            "progression": f"{self.score}%"
        }


class AdaptiveLearningSystem:
    """Système d'apprentissage adaptatif"""
    
    def __init__(self):
        self.users = {}
        
        # Templates de réponses adaptées au niveau
        self.response_templates = {
            "novice": {
                "structure": ["intro_simple", "points_clés", "conseil_pratique"],
                "vocabulary": "simple",
                "detail_level": "minimal",
                "examples": "many",
                "focus": ["indications_simples", "contre_indications_critiques"]
            },
            "intermediate": {
                "structure": ["intro", "points_clés", "explications", "conseil"],
                "vocabulary": "standard",
                "detail_level": "medium",
                "examples": "modérés",
                "focus": ["indications", "effets_secondaires", "utilisation"]
            },
            "advanced": {
                "structure": ["intro", "analyse", "mécanisme", "interactions", "résumé"],
                "vocabulary": "spécialisée",
                "detail_level": "détaillé",
                "examples": "ciblés",
                "focus": ["mécanisme_action", "composition", "interactions"]
            },
            "expert": {
                "structure": ["résumé", "analyse_scientifique", "études", "limitations"],
                "vocabulary": "hautement_spécialisée",
                "detail_level": "très_détaillé",
                "examples": "références_scientifiques",
                "focus": ["pharmacologie_détaillée", "interactions_complexes", "recherche"]
            }
        }
    
    def create_user(self, user_id: str, initial_level: str = "intermediate") -> UserProfile:
        """Crée un profil utilisateur"""
        if user_id not in self.users:
            self.users[user_id] = UserProfile(user_id, initial_level)
            print(f"✓ Utilisateur créé: {user_id} (niveau: {initial_level})")
        return self.users[user_id]
    
    def get_user(self, user_id: str) -> Optional[UserProfile]:
        """Récupère le profil d'un utilisateur"""
        return self.users.get(user_id)
    
    def get_response_template(self, user_level: str) -> Dict:
        """Récupère le template de réponse pour un niveau"""
        return self.response_templates.get(user_level, self.response_templates["intermediate"])
    
    def adapt_response(self, base_response: str, user_level: str) -> str:
        """Adapte une réponse au niveau utilisateur"""
        template = self.get_response_template(user_level)
        
        if user_level == "novice":
            # Simplifier le vocabulaire
            base_response = self._simplify_vocabulary(base_response)
            # Ajouter des explications simples
            base_response = self._add_simple_explanations(base_response)
        
        elif user_level == "advanced":
            # Ajouter des détails techniques
            base_response = self._add_technical_details(base_response)
        
        elif user_level == "expert":
            # Ajouter des références scientifiques
            base_response = self._add_scientific_references(base_response)
        
        return base_response
    
    def _simplify_vocabulary(self, text: str) -> str:
        """Remplace le vocabulaire complexe par simple"""
        replacements = {
            "mécanisme d'action": "comment ça marche",
            "contre-indication": "quand NE pas utiliser",
            "interaction": "problème si associé à",
            "excipient": "ingrédient supplémentaire",
            "posologie": "dose recommandée",
            "pharmacologie": "science du médicament"
        }
        
        for complex_term, simple_term in replacements.items():
            text = text.replace(complex_term, simple_term)
        
        return text
    
    def _add_simple_explanations(self, text: str) -> str:
        """Ajoute des explications simples pour les concepts"""
        explanations = {
            "immunité": " (défense du corps contre les maladies)",
            "vitamines": " (nutriments essentiels)",
            "complément": " (produit qui complète l'alimentation)",
        }
        
        for term, explanation in explanations.items():
            if term in text.lower() and explanation not in text:
                text = text.replace(term, term + explanation)
        
        return text
    
    def _add_technical_details(self, text: str) -> str:
        """Ajoute des détails techniques"""
        details = [
            "\n\n[Détail technique] ",
            "[Mécanisme moléculaire] ",
            "[Interaction pharmacologique] "
        ]
        # Intégrer des détails techniques si pertinent
        return text
    
    def _add_scientific_references(self, text: str) -> str:
        """Ajoute des références scientifiques"""
        references = [
            "\n[Ref: Étude clinique] ",
            "\n[Source: Pharmacopée] ",
            "\n[Publication: Journal] "
        ]
        # Ajouter des références
        return text
    
    def generate_learning_path(self, user_id: str) -> Dict:
        """Génère un parcours d'apprentissage personnalisé"""
        user = self.get_user(user_id)
        if not user:
            return {"error": "Utilisateur non trouvé"}
        
        level = user.current_level
        
        learning_paths = {
            "novice": {
                "phase": 1,
                "objectives": [
                    "Comprendre les bases des indications",
                    "Identifier les contre-indications critiques",
                    "Apprendre à recommander des produits simples"
                ],
                "recommended_topics": ["immunité", "vitamines", "compléments_basiques"],
                "practice_count": 10,
                "estimated_duration": "1-2 semaines"
            },
            "intermediate": {
                "phase": 2,
                "objectives": [
                    "Maîtriser les mécanismes d'action",
                    "Gérer les interactions simples",
                    "Conseiller sur les effets secondaires"
                ],
                "recommended_topics": ["digestion", "immunité_avancée", "douleur"],
                "practice_count": 15,
                "estimated_duration": "2-3 semaines"
            },
            "advanced": {
                "phase": 3,
                "objectives": [
                    "Maîtriser les interactions complexes",
                    "Analyser les comparaisons de produits",
                    "Adapter les recommandations aux cas complexes"
                ],
                "recommended_topics": ["pharmacologie_détaillée", "interactions"],
                "practice_count": 20,
                "estimated_duration": "3-4 semaines"
            },
            "expert": {
                "phase": 4,
                "objectives": [
                    "Analyser au niveau scientifique",
                    "Explorer les études cliniques",
                    "Mentorer d'autres délégués"
                ],
                "recommended_topics": ["recherche", "innovations"],
                "practice_count": -1,
                "estimated_duration": "Continu"
            }
        }
        
        return {
            "user_level": level,
            "learning_path": learning_paths.get(level, {}),
            "progress": f"{user.score}%",
            "next_objectives": learning_paths[level]["objectives"][:2]
        }


# ============================================================================
# 2. EXEMPLE D'UTILISATION
# ============================================================================

print("\n📚 Démonstration du Système Adaptatif\n")

# Créer le système
adaptive_system = AdaptiveLearningSystem()

# Créer plusieurs utilisateurs avec différents niveaux
users_to_test = [
    ("delegate_001", "novice"),
    ("delegate_002", "intermediate"),
    ("delegate_003", "advanced")
]

print("Création des profils utilisateurs:")
print("-" * 60)

for user_id, level in users_to_test:
    user = adaptive_system.create_user(user_id, level)
    profile = user.get_profile()
    print(f"\n👤 {user_id}")
    print(f"   Niveau: {profile['current_level']}")
    print(f"   Score: {profile['score']}/100")
    print(f"   Description: {profile['level_description']}")
    
    # Afficher le template de réponse
    template = adaptive_system.get_response_template(level)
    print(f"   Structure de réponse: {' → '.join(template['structure'])}")
    print(f"   Vocabulaire: {template['vocabulary']}")

# Simuler une interaction
print("\n" + "="*60)
print("Simulation d'apprentissage progressif:")
print("="*60)

user = adaptive_system.get_user("delegate_001")

print(f"\n📈 Progression de {user.user_id}:")
interactions = [
    ("question_basique", 5, "Bonne réponse sur les vitamines"),
    ("question_modérée", 8, "Comprend les indications"),
    ("question_complexe", 12, "Maîtrise les interactions"),
]

for interaction_type, points, description in interactions:
    print(f"\n  {description}... ", end="", flush=True)
    user.update_score(points, interaction_type)
    print(f"({points:+d} pts)")
    
    profile = user.get_profile()
    print(f"    Score: {profile['score']}/100 | Niveau: {profile['current_level']} | Précision: {profile['accuracy']:.0%}")

# Génération du parcours d'apprentissage
print("\n" + "="*60)
print("Parcours d'Apprentissage Personnalisé:")
print("="*60)

for user_id, _ in users_to_test:
    user = adaptive_system.get_user(user_id)
    path = adaptive_system.generate_learning_path(user_id)
    
    print(f"\n👤 {user_id} (Niveau: {path['user_level']})")
    print(f"   Phase: {path['learning_path']['phase']}")
    print(f"   Objectifs:")
    for obj in path['learning_path']['objectives'][:2]:
        print(f"     • {obj}")
    print(f"   Durée estimée: {path['learning_path']['estimated_duration']}")

# ============================================================================
# 3. SAUVEGARDE
# ============================================================================

output = {
    "timestamp": json.dumps(None, default=str),
    "system_info": {
        "name": "Adaptive Learning System",
        "version": "1.0",
        "user_levels": list(UserProfile.LEVELS.keys())
    },
    "users": {
        user_id: adaptive_system.get_user(user_id).get_profile()
        for user_id, _ in users_to_test
    }
}

with open('adaptive_learning_profiles.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, indent=2, ensure_ascii=False, default=str)

print(f"\n✓ Profils utilisateurs sauvegardés: adaptive_learning_profiles.json")

print("\n" + "="*80)
print("✅ SYSTÈME ADAPTATIF CONFIGURÉ!")
print("="*80)
