#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TEST COMPARATIF COMPLET: L2 vs COSINUS SIMILARITY
================================================
- 100 requêtes diversifiées
- Comparaison L2 (IndexFlatL2) vs Cosinus (IndexFlatIP)
- Calcul des métriques: MRR, Precision@5, Recall@5, NDCG
- Analyse détaillée des performances
"""

import json
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
import time
from collections import defaultdict

print("="*80)
print("🔍 TEST COMPARATIF COMPLET: L2 vs COSINUS")
print("="*80)

# ============================================================================
# 1. CHARGEMENT DES DONNÉES
# ============================================================================
print("\n📦 Chargement des données...")

with open('chunks_structure_based_v4.json', 'r', encoding='utf-8') as f:
    chunks = json.load(f)
print(f"✓ {len(chunks)} chunks chargés")

with open('queries_100_comprehensive.json', 'r', encoding='utf-8') as f:
    query_data = json.load(f)
queries = query_data['queries']
print(f"✓ {len(queries)} requêtes chargées")

# ============================================================================
# 2. CHARGEMENT DES EMBEDDINGS
# ============================================================================
print("\n🧠 Chargement des embeddings...")
embeddings = np.load('embeddings_768d_mpnet.npy')
print(f"✓ Embeddings chargés: {embeddings.shape}")
print(f"  Type: {embeddings.dtype}")

# Vérifier la normalisation
norms = np.linalg.norm(embeddings, axis=1)
print(f"  Norms: min={norms.min():.6f}, max={norms.max():.6f}, mean={norms.mean():.6f}")

# ============================================================================
# 3. CRÉATION DES INDEXES FAISS
# ============================================================================
print("\n📇 Création des indexes FAISS...")

# Index L2 (Euclidean distance)
EMBEDDING_DIM = embeddings.shape[1]
index_l2 = faiss.IndexFlatL2(EMBEDDING_DIM)
index_l2.add(embeddings.astype(np.float32))
print(f"✓ Index L2 créé avec {index_l2.ntotal} vecteurs")

# Index Cosinus (Inner Product avec embeddings normalisés)
# Les embeddings sont déjà normalisés (norme = 1.0)
# Inner Product équivaut à Cosinus similarity pour embeddings normalisés
index_cosine = faiss.IndexFlatIP(EMBEDDING_DIM)
index_cosine.add(embeddings.astype(np.float32))
print(f"✓ Index Cosinus créé avec {index_cosine.ntotal} vecteurs")

# ============================================================================
# 4. CHARGEMENT DU MODÈLE EMBEDDING
# ============================================================================
print("\n💻 Chargement du modèle...")
model = SentenceTransformer("all-mpnet-base-v2")
print("✓ Modèle chargé: all-mpnet-base-v2")

# ============================================================================
# 5. FONCTIONS D'ÉVALUATION
# ============================================================================

def calculate_mrr(retrieved_indices, relevant_indices):
    """Mean Reciprocal Rank"""
    if len(relevant_indices) == 0:
        return 0.0
    for rank, idx in enumerate(retrieved_indices, 1):
        if idx in relevant_indices:
            return 1.0 / rank
    return 0.0

def calculate_precision_at_k(retrieved_indices, relevant_indices, k=5):
    """Precision@K"""
    if len(relevant_indices) == 0:
        return 0.0
    retrieved_at_k = retrieved_indices[:k]
    hits = len([idx for idx in retrieved_at_k if idx in relevant_indices])
    return hits / k

def calculate_recall_at_k(retrieved_indices, relevant_indices, k=5):
    """Recall@K"""
    if len(relevant_indices) == 0:
        return 0.0
    retrieved_at_k = retrieved_indices[:k]
    hits = len([idx for idx in retrieved_at_k if idx in relevant_indices])
    return hits / len(relevant_indices)

def calculate_dcg(relevances):
    """Discounted Cumulative Gain"""
    dcg = 0.0
    for i, rel in enumerate(relevances, 1):
        dcg += rel / np.log2(i + 1)
    return dcg

def calculate_ndcg(retrieved_indices, relevant_indices, k=5):
    """Normalized Discounted Cumulative Gain"""
    # Calculer DCG
    retrieved_at_k = retrieved_indices[:k]
    relevances = [1.0 if idx in relevant_indices else 0.0 for idx in retrieved_at_k]
    dcg = calculate_dcg(relevances)
    
    # Calculer IDCG (oracle parfait)
    ideal_relevances = [1.0] * min(len(relevant_indices), k)
    idcg = calculate_dcg(ideal_relevances)
    
    if idcg == 0:
        return 0.0
    return dcg / idcg

def find_relevant_by_keywords(query_text, chunks, top_match=5):
    """
    Heuristique simple: trouver les chunks qui contiennent les mots-clés de la requête
    """
    query_words = set(query_text.lower().split())
    scores = []
    for i, chunk in enumerate(chunks):
        text = (chunk.get('clinical_profile', '') + ' ' + 
                chunk.get('pharmacology_profile', '')).lower()
        matches = sum(1 for word in query_words if word in text)
        if matches > 0:
            scores.append((i, matches))
    
    # Trier par nombre de matches
    scores.sort(key=lambda x: x[1], reverse=True)
    relevant_indices = set([idx for idx, _ in scores[:top_match]])
    return relevant_indices

# ============================================================================
# 6. TEST COMPARATIF
# ============================================================================
print("\n" + "="*80)
print("🧪 TEST COMPARATIF - 100 REQUÊTES")
print("="*80)

results_l2 = []
results_cosine = []
comparison = []

start_time = time.time()

for i, query_obj in enumerate(queries, 1):
    query_text = query_obj['query']
    category = query_obj['category']
    
    # Encoder la requête
    query_emb = model.encode(query_text, convert_to_numpy=True).astype(np.float32)
    
    # Rechercher L2
    distances_l2, indices_l2 = index_l2.search(np.array([query_emb]), k=5)
    distances_l2 = distances_l2[0]
    indices_l2 = indices_l2[0]
    
    # Rechercher Cosinus (transformer distances en scores [0, 1])
    scores_cosine, indices_cosine = index_cosine.search(np.array([query_emb]), k=5)
    scores_cosine = scores_cosine[0]
    indices_cosine = indices_cosine[0]
    
    # Trouver ground truth (articles pertinents selon les keywords)
    relevant_indices = find_relevant_by_keywords(query_text, chunks, top_match=5)
    
    # Calculer les métriques L2
    mrr_l2 = calculate_mrr(indices_l2, relevant_indices)
    prec_l2 = calculate_precision_at_k(indices_l2, relevant_indices, k=5)
    recall_l2 = calculate_recall_at_k(indices_l2, relevant_indices, k=5)
    ndcg_l2 = calculate_ndcg(indices_l2, relevant_indices, k=5)
    
    # Calculer les métriques Cosinus
    mrr_cosine = calculate_mrr(indices_cosine, relevant_indices)
    prec_cosine = calculate_precision_at_k(indices_cosine, relevant_indices, k=5)
    recall_cosine = calculate_recall_at_k(indices_cosine, relevant_indices, k=5)
    ndcg_cosine = calculate_ndcg(indices_cosine, relevant_indices, k=5)
    
    # Stocker les résultats
    result_l2 = {
        'query_id': i,
        'query': query_text,
        'category': category,
        'distances': distances_l2.tolist(),
        'product_names': [chunks[idx]['product_name'] for idx in indices_l2],
        'mrr': mrr_l2,
        'precision_at_5': prec_l2,
        'recall_at_5': recall_l2,
        'ndcg': ndcg_l2,
        'avg_distance': float(distances_l2.mean())
    }
    results_l2.append(result_l2)
    
    result_cosine = {
        'query_id': i,
        'query': query_text,
        'category': category,
        'scores': scores_cosine.tolist(),
        'product_names': [chunks[idx]['product_name'] for idx in indices_cosine],
        'mrr': mrr_cosine,
        'precision_at_5': prec_cosine,
        'recall_at_5': recall_cosine,
        'ndcg': ndcg_cosine,
        'avg_score': float(scores_cosine.mean())
    }
    results_cosine.append(result_cosine)
    
    # Comparer
    same_order = list(indices_l2) == list(indices_cosine)
    best_metric_l2 = (mrr_l2 + prec_l2 + recall_l2 + ndcg_l2) / 4
    best_metric_cosine = (mrr_cosine + prec_cosine + recall_cosine + ndcg_cosine) / 4
    
    comp = {
        'query_id': i,
        'query': query_text,
        'category': category,
        'same_order': same_order,
        'avg_metric_l2': best_metric_l2,
        'avg_metric_cosine': best_metric_cosine,
        'better': 'L2' if best_metric_l2 > best_metric_cosine else 'Cosinus' if best_metric_cosine > best_metric_l2 else 'Égal'
    }
    comparison.append(comp)
    
    # Affichage de la progression (tous les 10 requêtes)
    if i % 10 == 0:
        elapsed = time.time() - start_time
        print(f"✓ {i}/100 requêtes traitées ({elapsed:.1f}s)")

elapsed_total = time.time() - start_time

# ============================================================================
# 7. ANALYSE AGRÉGÉE
# ============================================================================
print("\n" + "="*80)
print("📊 ANALYSE AGRÉGÉE")
print("="*80)

# Métriques L2
mrr_l2_avg = np.mean([r['mrr'] for r in results_l2])
prec_l2_avg = np.mean([r['precision_at_5'] for r in results_l2])
recall_l2_avg = np.mean([r['recall_at_5'] for r in results_l2])
ndcg_l2_avg = np.mean([r['ndcg'] for r in results_l2])
dist_l2_avg = np.mean([r['avg_distance'] for r in results_l2])

# Métriques Cosinus
mrr_cosine_avg = np.mean([r['mrr'] for r in results_cosine])
prec_cosine_avg = np.mean([r['precision_at_5'] for r in results_cosine])
recall_cosine_avg = np.mean([r['recall_at_5'] for r in results_cosine])
ndcg_cosine_avg = np.mean([r['ndcg'] for r in results_cosine])
score_cosine_avg = np.mean([r['avg_score'] for r in results_cosine])

print("\n🔴 MÉTRIQUES L2 (Euclidean Distance):")
print(f"   MRR:           {mrr_l2_avg:.4f}")
print(f"   Precision@5:   {prec_l2_avg:.4f}")
print(f"   Recall@5:      {recall_l2_avg:.4f}")
print(f"   NDCG:          {ndcg_l2_avg:.4f}")
print(f"   Distance moy:  {dist_l2_avg:.4f}")

print("\n🔵 MÉTRIQUES COSINUS (Inner Product):")
print(f"   MRR:           {mrr_cosine_avg:.4f}")
print(f"   Precision@5:   {prec_cosine_avg:.4f}")
print(f"   Recall@5:      {recall_cosine_avg:.4f}")
print(f"   NDCG:          {ndcg_cosine_avg:.4f}")
print(f"   Score moyen:   {score_cosine_avg:.4f}")

# Comparaison
print("\n⚖️  COMPARAISON:")
same_order_count = sum(1 for c in comparison if c['same_order'])
print(f"   Requêtes avec même top-1: {same_order_count}/100 ({same_order_count}%)")

winner_counts = defaultdict(int)
for c in comparison:
    winner_counts[c['better']] += 1

print(f"   L2 meilleur:   {winner_counts['L2']}/100")
print(f"   Cosinus meilleur: {winner_counts['Cosinus']}/100")
print(f"   Égal:          {winner_counts['Égal']}/100")

# Analyse par catégorie
print("\n📚 ANALYSE PAR CATÉGORIE:")
categories = defaultdict(lambda: {'l2': [], 'cosine': []})
for r in results_l2:
    categories[r['category']]['l2'].append(r['ndcg'])
for r in results_cosine:
    categories[r['category']]['cosine'].append(r['ndcg'])

for cat in sorted(categories.keys()):
    ndcg_l2 = np.mean(categories[cat]['l2'])
    ndcg_cosine = np.mean(categories[cat]['cosine'])
    print(f"   {cat:30s}: L2={ndcg_l2:.4f}, Cosinus={ndcg_cosine:.4f}")

# ============================================================================
# 8. SAUVEGARDE DES RÉSULTATS DÉTAILLÉS
# ============================================================================
print("\n💾 Sauvegarde des résultats détaillés...")

all_results = {
    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
    'total_queries': 100,
    'elapsed_time_seconds': elapsed_total,
    'summary': {
        'l2': {
            'mrr': mrr_l2_avg,
            'precision_at_5': prec_l2_avg,
            'recall_at_5': recall_l2_avg,
            'ndcg': ndcg_l2_avg,
            'avg_distance': dist_l2_avg
        },
        'cosinus': {
            'mrr': mrr_cosine_avg,
            'precision_at_5': prec_cosine_avg,
            'recall_at_5': recall_cosine_avg,
            'ndcg': ndcg_cosine_avg,
            'avg_score': score_cosine_avg
        },
        'comparison': {
            'same_order_count': same_order_count,
            'l2_better': winner_counts['L2'],
            'cosinus_better': winner_counts['Cosinus'],
            'equal': winner_counts['Égal'],
            'recommendation': 'Cosinus' if winner_counts['Cosinus'] > winner_counts['L2'] else 'L2' if winner_counts['L2'] > winner_counts['Cosinus'] else 'Équivalent'
        }
    },
    'detailed_results': {
        'l2': results_l2,
        'cosinus': results_cosine,
        'comparison': comparison
    }
}

with open('test_results_l2_vs_cosine_100queries.json', 'w', encoding='utf-8') as f:
    json.dump(all_results, f, indent=2, ensure_ascii=False)

print(f"✓ Résultats sauvegardés: test_results_l2_vs_cosine_100queries.json")

# ============================================================================
# 9. RÉSUMÉ FINAL
# ============================================================================
print("\n" + "="*80)
print("✅ TEST COMPLET!")
print("="*80)
print(f"\n⏱️  Temps total: {elapsed_total:.1f}s pour 100 requêtes")
print(f"\n🏆 RECOMMANDATION: {all_results['summary']['comparison']['recommendation']}")
print(f"\n📊 Score global L2:      {(mrr_l2_avg + prec_l2_avg + recall_l2_avg + ndcg_l2_avg)/4:.4f}")
print(f"   Score global Cosinus: {(mrr_cosine_avg + prec_cosine_avg + recall_cosine_avg + ndcg_cosine_avg)/4:.4f}")
print("\n" + "="*80)
