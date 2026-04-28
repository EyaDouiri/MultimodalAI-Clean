#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TEST RUNNER - Pipeline RAG Complet
===================================
Exécute l'intégration complète : Retrieval V4 + LLM Generation
avec évaluation de tous les styles de prompts
"""

import json
import sys
import os
from io import TextIOWrapper

# Force UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout = TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import numpy as np
import faiss
from pathlib import Path
from datetime import datetime
from sentence_transformers import SentenceTransformer
from typing import Dict, List, Any

# Configuration des chemins
ROOT = Path(__file__).parent.parent
DATA_PROCESSED = ROOT / "data" / "processed"
VECTORIAL_EMBEDDINGS = ROOT / "vectorial_db" / "embeddings"
VECTORIAL_INDEXES = ROOT / "vectorial_db" / "indexes"
GENERATION_CONFIG = ROOT / "generation" / "config"
TESTS_RESULTS = ROOT / "tests" / "results"

# Ajouter les chemins
sys.path.insert(0, str(GENERATION_CONFIG))

from config_llm import OllamaConnection, PromptManager, USER_LEVELS

print("="*80)
print("🧪 TEST RUNNER - PIPELINE RAG COMPLET")
print("="*80)

# ============================================================================
# PHASE 1: CHARGEMENT DONNÉES
# ============================================================================
print("\n📦 PHASE 1: Chargement des données...")

# Chunks
chunks_path = DATA_PROCESSED / "chunks_structure_based_v4.json"
with open(chunks_path, 'r', encoding='utf-8') as f:
    chunks = json.load(f)
print(f"  ✓ {len(chunks)} chunks chargés")

# Embeddings
embeddings_path = VECTORIAL_EMBEDDINGS / "embeddings_768d_mpnet.npy"
embeddings = np.load(embeddings_path)
print(f"  ✓ Embeddings: {embeddings.shape}")

# Index FAISS
index_path = VECTORIAL_INDEXES / "rag_index_768d_mpnet.faiss"
index = faiss.IndexFlatIP(embeddings.shape[1])
index.add(embeddings.astype(np.float32))
print(f"  ✓ Index FAISS créé (Cosinus similarity)")

# Modèle embedding
model_embedding = SentenceTransformer("all-mpnet-base-v2")
print(f"  ✓ Modèle embedding chargé")

# Test queries
queries_path = DATA_PROCESSED / "queries_100_comprehensive.json"
with open(queries_path, 'r', encoding='utf-8') as f:
    queries_data = json.load(f)
    # Les queries sont dans une clé 'queries'
    all_queries = queries_data.get("queries", queries_data) if isinstance(queries_data, dict) else queries_data
print(f"  ✓ {len(all_queries)} queries disponibles")

# ============================================================================
# PHASE 2: TEST CONNEXION OLLAMA
# ============================================================================
print("\n🤖 PHASE 2: Vérification Ollama...")

ollama = OllamaConnection()
if not ollama.check_connection():
    print("  ⚠️  ERREUR: Ollama non accessible")
    sys.exit(1)

available_models = ollama.list_available_models()
print(f"  ✓ Models disponibles: {', '.join(available_models)}")

# ============================================================================
# PHASE 3: TESTS RETRIEVAL-GENERATION
# ============================================================================
print("\n🔍 PHASE 3: Tests Retrieval + Generation...")
print("-" * 80)

# Sélectionner 10 queries pour test complet
test_queries = all_queries[:10]

prompt_manager = PromptManager()
results = {
    "timestamp": datetime.now().isoformat(),
    "total_tests": len(test_queries) * 4,  # 4 prompt styles
    "test_queries": len(test_queries),
    "prompt_styles": ["simple", "pedagogical", "cot", "fewshot"],
    "results_by_query": []
}

for q_idx, query_obj in enumerate(test_queries, 1):
    # Gérer à la fois les strings et les objects
    if isinstance(query_obj, str):
        query = query_obj
    elif isinstance(query_obj, dict):
        query = query_obj.get("query", str(query_obj))
    else:
        query = str(query_obj)
    
    print(f"\n📌 Query {q_idx}/{len(test_queries)}: {query[:60]}...")
    
    # RETRIEVAL
    query_embedding = model_embedding.encode(query, convert_to_tensor=False)
    query_embedding = query_embedding / np.linalg.norm(query_embedding)
    
    distances, indices = index.search(
        np.array([query_embedding], dtype=np.float32),
        k=5
    )
    
    retrieved_docs = [chunks[idx] for idx in indices[0]]
    context = "\n---\n".join([
        f"Doc {i+1}: {doc.get('clinical_profile', '') + ' ' + doc.get('pharmacology_profile', '')}"
        for i, doc in enumerate(retrieved_docs)
    ])
    
    query_result = {
        "query_idx": q_idx,
        "query": query,
        "retrieved_count": len(retrieved_docs),
        "retrieval_distance_mean": float(distances[0].mean()),
        "generations": []
    }
    
    # TEST TOUS LES STYLES
    for style in ["simple", "pedagogical", "cot", "fewshot"]:
        print(f"  → Testing style: {style}...", end=" ")
        
        try:
            # Sélectionner la bonne méthode selon le style
            if style == "simple":
                prompt = prompt_manager.get_prompt_simple(context=context, query=query)
            elif style == "pedagogical":
                prompt = prompt_manager.get_prompt_pedagogical(
                    context=context, query=query, user_level="intermediate"
                )
            elif style == "cot":
                prompt = prompt_manager.get_prompt_cot(context=context, query=query)
            elif style == "fewshot":
                prompt = prompt_manager.get_prompt_few_shot(context=context, query=query)
            
            response = ollama.generate(
                model="llama2:latest",
                prompt=prompt,
                stream=False
            )
            
            # Gérer la réponse (peut être dict ou string)
            if isinstance(response, dict):
                response_text = response.get("response", str(response))
            else:
                response_text = str(response)
            
            generation_result = {
                "style": style,
                "token_count": len(response_text.split()),
                "response_length": len(response_text),
                "response_preview": response_text[:150] + "..." if len(response_text) > 150 else response_text,
                "success": True
            }
            
            query_result["generations"].append(generation_result)
            print("✓")
            
        except Exception as e:
            print(f"✗ ({str(e)[:30]})")
            query_result["generations"].append({
                "style": style,
                "success": False,
                "error": str(e)[:100]
            })
    
    results["results_by_query"].append(query_result)

# ============================================================================
# PHASE 4: RÉSUMÉ ET EXPORT
# ============================================================================
print("\n" + "="*80)
print("📊 RÉSUMÉ DES TESTS")
print("="*80)

successful_gens = sum(
    1 for r in results["results_by_query"]
    for g in r["generations"]
    if g.get("success", False)
)

total_gens = sum(
    len(r["generations"]) for r in results["results_by_query"]
)

results["summary"] = {
    "successful_generations": successful_gens,
    "total_generations": total_gens,
    "success_rate": f"{(successful_gens/total_gens*100):.1f}%" if total_gens > 0 else "N/A",
    "avg_retrieval_distance": f"{np.mean([r['retrieval_distance_mean'] for r in results['results_by_query']]):.3f}"
}

print(f"\n✓ Tests réussis: {successful_gens}/{total_gens}")
print(f"✓ Recherche moyenne: {results['summary']['avg_retrieval_distance']}")

# Sauvegarder les résultats
output_file = TESTS_RESULTS / f"complete_rag_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print(f"\n💾 Résultats sauvegardés: {output_file}")

# Afficher statistiques par style
print("\n" + "="*80)
print("📈 STATISTIQUES PAR STYLE DE PROMPT")
print("="*80)

style_stats = {}
for result in results["results_by_query"]:
    for gen in result["generations"]:
        style = gen["style"]
        if style not in style_stats:
            style_stats[style] = {"success": 0, "total": 0}
        style_stats[style]["total"] += 1
        if gen.get("success", False):
            style_stats[style]["success"] += 1

for style, stats in style_stats.items():
    rate = (stats["success"] / stats["total"] * 100) if stats["total"] > 0 else 0
    print(f"  {style:15} → {stats['success']}/{stats['total']} ✓ ({rate:.0f}%)")

print("\n✅ Test runner terminé")
