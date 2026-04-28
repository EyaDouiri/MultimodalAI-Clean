#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PROMPT COMPARISON & EVALUATION
================================
Compare différents styles de prompts selon plusieurs métriques
"""

import json
import sys
from pathlib import Path

# Configuration des chemins
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "generation" / "config"))

import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from config_llm import OllamaConnection, PromptManager, USER_LEVELS, PROMPT_STYLES
import re
from datetime import datetime

print("="*80)
print("🧪 COMPARAISON STYLES DE PROMPTS & ÉVALUATION")
print("="*80)

# ============================================================================
# 1. CHARGEMENT DONNÉES
# ============================================================================
print("\n📦 Chargement système...")

chunks_path = ROOT / "data" / "processed" / "chunks_structure_based_v4.json"
embeddings_path = ROOT / "vectorial_db" / "embeddings" / "embeddings_768d_mpnet.npy"

with open(chunks_path, 'r', encoding='utf-8') as f:
    chunks = json.load(f)

embeddings = np.load(embeddings_path)
index = faiss.IndexFlatIP(embeddings.shape[1])
index.add(embeddings.astype(np.float32))

model_embedding = SentenceTransformer("all-mpnet-base-v2")

ollama = OllamaConnection()
if not ollama.check_connection():
    print("❌ Ollama non accessible")
    exit(1)

available_models = ollama.list_available_models()
available_llama = [m for m in available_models if 'llama' in m.lower()]
llm_model = available_llama[0] if available_llama else None

if not llm_model:
    print("❌ Aucun modèle LLM disponible")
    exit(1)

print(f"✓ Système prêt avec {llm_model}")

# ============================================================================
# 2. MÉTRIQUES D'ÉVALUATION
# ============================================================================

class PromptEvaluator:
    """Évalue la qualité des réponses"""
    
    @staticmethod
    def calculate_relevance(response: str, query: str) -> float:
        """Mesure la pertinence de la réponse par rapport à la requête"""
        query_words = set(query.lower().split())
        response_words = set(response.lower().split())
        
        # Jaccard similarity
        intersection = len(query_words & response_words)
        union = len(query_words | response_words)
        
        return intersection / union if union > 0 else 0.0
    
    @staticmethod
    def calculate_clarity(response: str) -> float:
        """Mesure la clarté: phrases courtes, structure simple"""
        sentences = re.split(r'[.!?]+', response)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if not sentences:
            return 0.0
        
        avg_length = np.mean([len(s.split()) for s in sentences])
        
        # Clarté optimale: 10-20 mots par phrase
        clarity = 1.0 - min(abs(15 - avg_length) / 15, 1.0)
        return clarity
    
    @staticmethod
    def calculate_completeness(response: str, query: str) -> float:
        """Mesure la complétude: couvre les aspects principaux"""
        required_aspects = ["indication", "produit", "utilisation", "conseil"]
        covered = sum(1 for aspect in required_aspects if aspect in response.lower())
        return covered / len(required_aspects)
    
    @staticmethod
    def calculate_length_score(response: str) -> float:
        """Mesure si la longueur est appropriée"""
        words = len(response.split())
        
        # Optimal: 100-300 mots
        if 100 <= words <= 300:
            return 1.0
        elif 50 <= words <= 400:
            return 0.8
        elif 30 <= words <= 500:
            return 0.6
        else:
            return 0.3
    
    @staticmethod
    def calculate_structure(response: str) -> float:
        """Mesure si la réponse est bien structurée"""
        # Indicateurs de bonne structure
        has_intro = any(word in response.lower()[:100] for word in ["voici", "recommand", "utilise", "c'est"])
        has_details = response.count('\n') >= 2 or response.count('.') >= 3
        has_conclusion = any(word in response.lower()[-100:] for word in ["résumé", "important", "conseil", "noter"])
        
        score = sum([has_intro, has_details, has_conclusion]) / 3.0
        return score
    
    @staticmethod
    def calculate_overall_score(response: str, query: str) -> Dict:
        """Calcule toutes les métriques et score global"""
        
        evaluator = PromptEvaluator()
        
        relevance = evaluator.calculate_relevance(response, query)
        clarity = evaluator.calculate_clarity(response)
        completeness = evaluator.calculate_completeness(response, query)
        length_score = evaluator.calculate_length_score(response)
        structure = evaluator.calculate_structure(response)
        
        # Score pondéré
        overall = (
            relevance * 0.25 +
            clarity * 0.20 +
            completeness * 0.20 +
            length_score * 0.15 +
            structure * 0.20
        )
        
        return {
            'relevance': relevance,
            'clarity': clarity,
            'completeness': completeness,
            'length_score': length_score,
            'structure': structure,
            'overall': overall,
            'word_count': len(response.split())
        }

# ============================================================================
# 3. TESTS COMPARATIFS
# ============================================================================

print("\n" + "="*80)
print("🔬 TESTS DE COMPARAISON - 3 REQUÊTES, 4 PROMPT STYLES")
print("="*80)

pipeline = RAGPipeline(chunks, index, model_embedding, llm_model)
evaluator = PromptEvaluator()

# Requêtes de test
test_cases = [
    {
        "query": "Quel produit recommandes-tu pour améliorer l'immunité?",
        "user_level": "intermediate",
        "description": "Immunité générale"
    },
    {
        "query": "J'ai une peau sensible qui pique. Quel soin me recommandes-tu?",
        "user_level": "novice",
        "description": "Peau sensible - novice"
    },
    {
        "query": "Explique le mécanisme d'action et composition d'un complément anti-fatigue",
        "user_level": "advanced",
        "description": "Scientifique - expert"
    }
]

# Styles de prompts à tester
prompt_styles = list(PROMPT_STYLES.keys())

comparison_results = []

for test_idx, test_case in enumerate(test_cases, 1):
    print(f"\n{'='*80}")
    print(f"📝 TEST {test_idx}: {test_case['description']}")
    print(f"Query: '{test_case['query']}'")
    print(f"{'='*80}")
    
    test_results = []
    
    for style_idx, style in enumerate(prompt_styles, 1):
        print(f"\n  [{style_idx}] Style: {PROMPT_STYLES[style]['name']}... ", end="", flush=True)
        
        try:
            # Générer réponse
            result = pipeline.process(
                query=test_case["query"],
                prompt_style=style,
                user_level=test_case["user_level"],
                k_retrieve=3
            )
            
            # Évaluer
            if "error" not in result["generation"]:
                response_text = result["generation"]["response"]
                eval_scores = evaluator.calculate_overall_score(response_text, test_case["query"])
                
                test_results.append({
                    "prompt_style": style,
                    "style_name": PROMPT_STYLES[style]['name'],
                    "response": response_text[:200] + "..." if len(response_text) > 200 else response_text,
                    "evaluation": eval_scores,
                    "status": "success"
                })
                
                print(f"✓ Score: {eval_scores['overall']:.2f}")
            else:
                print(f"❌ Erreur: {result['generation']['error']}")
                test_results.append({
                    "prompt_style": style,
                    "style_name": PROMPT_STYLES[style]['name'],
                    "status": "error",
                    "error": result['generation']['error']
                })
        
        except Exception as e:
            print(f"❌ Exception: {str(e)}")
            test_results.append({
                "prompt_style": style,
                "status": "exception",
                "error": str(e)
            })
    
    # Résumé du test
    print(f"\n  📊 RÉSUMÉ TEST {test_idx}:")
    print(f"  {'-'*76}")
    
    valid_results = [r for r in test_results if r["status"] == "success"]
    if valid_results:
        scores = [r["evaluation"]["overall"] for r in valid_results]
        names = [r["style_name"] for r in valid_results]
        
        best_idx = np.argmax(scores)
        worst_idx = np.argmin(scores)
        
        print(f"  Meilleur:  {names[best_idx]:30s} | Score: {scores[best_idx]:.3f}")
        print(f"  Pire:      {names[worst_idx]:30s} | Score: {scores[worst_idx]:.3f}")
        print(f"  Moyenne:   {np.mean(scores):.3f}")
        
        # Classement
        print(f"\n  Classement:")
        sorted_results = sorted(enumerate(valid_results), 
                               key=lambda x: x[1]["evaluation"]["overall"], 
                               reverse=True)
        for rank, (orig_idx, result) in enumerate(sorted_results, 1):
            print(f"    {rank}. {result['style_name']:30s} {result['evaluation']['overall']:.3f}")
    
    comparison_results.append({
        "test_case": test_case,
        "results": test_results
    })

# ============================================================================
# 4. RÉSUMÉ GLOBAL
# ============================================================================

print("\n" + "="*80)
print("📈 RÉSUMÉ GLOBAL")
print("="*80)

# Calculer les scores moyens par style
style_scores = {style: [] for style in prompt_styles}

for test_res in comparison_results:
    for result in test_res["results"]:
        if result["status"] == "success":
            style = result["prompt_style"]
            score = result["evaluation"]["overall"]
            style_scores[style].append(score)

print("\nPerformance moyenne par prompt style:")
print(f"{'Style':<30} {'Score Moy':<12} {'Nb Tests':<10}")
print("-" * 52)

for style in prompt_styles:
    if style_scores[style]:
        avg = np.mean(style_scores[style])
        count = len(style_scores[style])
        print(f"{PROMPT_STYLES[style]['name']:<30} {avg:>10.3f}   {count:>8}")

# ============================================================================
# 5. SAUVEGARDE
# ============================================================================

output = {
    "timestamp": datetime.now().isoformat(),
    "test_summary": {
        "total_tests": len(test_cases),
        "prompt_styles_tested": prompt_styles,
        "average_scores_by_style": {
            style: float(np.mean(style_scores[style])) if style_scores[style] else 0.0
            for style in prompt_styles
        }
    },
    "detailed_results": comparison_results
}

with open('prompt_comparison_results.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

print(f"\n✓ Résultats détaillés sauvegardés: prompt_comparison_results.json")

print("\n" + "="*80)
print("✅ COMPARAISON COMPLÈTE!")
print("="*80)
