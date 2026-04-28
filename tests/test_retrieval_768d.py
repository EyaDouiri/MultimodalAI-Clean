"""
TEST RETRIEVAL V4 - Validation du RAG avec modèle 768D
Teste la récupération sémantique sur plusieurs requêtes
"""

import json
import numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer
import faiss

PROJECT_ROOT = Path(__file__).parent

# Configuration (match avec pipeline)
EMBEDDING_MODEL = "all-mpnet-base-v2"
CHUNKS_PATH = PROJECT_ROOT / "chunks_structure_based_v4.json"
EMBEDDINGS_PATH = PROJECT_ROOT / "embeddings_768d_mpnet.npy"
FAISS_INDEX_PATH = PROJECT_ROOT / "rag_index_768d_mpnet.faiss"

print("=" * 80)
print("🔍 TEST RETRIEVAL V4 - Validation RAG 768D")
print("=" * 80)

# ===== 1. Charger les données =====
print(f"\n📦 Chargement des données...")
with open(CHUNKS_PATH, 'r', encoding='utf-8') as f:
    chunks = json.load(f)
print(f"✓ {len(chunks)} chunks chargés")

print(f"\n🧠 Chargement du modèle: {EMBEDDING_MODEL}")
model = SentenceTransformer(EMBEDDING_MODEL)
print(f"✓ Modèle chargé")

print(f"\n🔮 Chargement de l'index FAISS...")
index = faiss.read_index(str(FAISS_INDEX_PATH))
print(f"✓ Index chargé ({index.ntotal} vecteurs)")

# ===== 2. Requêtes de test =====
test_queries = [
    ("Pédiakids APITOU", "Devrait retourner des produits avec vitamines"),
    ("douleur et inflammation", "Devrait retourner des produits antalgiques"),
    ("traitement du diabète", "Devrait retourner LV Diabemin"),
    ("soins peau sensible", "Devrait retourner des produits dermatologiques"),
    ("maux de gorge", "Devrait retourner des sirops pour toux"),
    ("fer et anémie", "Devrait retourner des compléments fer"),
    ("immunité et infection", "Devrait retourner des immunostimulants"),
    ("fatigue", "Devrait retourner des produits GI"),
]

print(f"\n" + "=" * 80)
print(f"🧪 TEST RETRIEVAL - {len(test_queries)} requêtes")
print("=" * 80)

results_summary = []

for query_idx, (query, expected) in enumerate(test_queries, 1):
    print(f"\n[Query {query_idx}] {query}")
    print(f"    → {expected}")
    print("    " + "-" * 70)
    
    # Encoder la requête
    query_emb = model.encode(query, convert_to_numpy=True).astype(np.float32)
    
    # Rechercher top-5
    distances, indices = index.search(np.array([query_emb]), k=5)
    
    print(f"    Top-5 résultats:")
    query_results = []
    for rank, (idx, distance) in enumerate(zip(indices[0], distances[0]), 1):
        chunk = chunks[idx]
        product_name = chunk['product_name']
        chunk_type = chunk['chunk_type']
        classe = chunk.get('classe', 'Unknown')
        
        # Affiche plus compacte
        print(f"      {rank}. [{distance:.4f}] {product_name}")
        print(f"         └─ {chunk_type} ({classe})")
        
        query_results.append({
            "rank": rank,
            "distance": float(distance),
            "product": product_name,
            "type": chunk_type,
            "classe": classe
        })
    
    results_summary.append({
        "query": query,
        "results": query_results
    })

# ===== 3. Rapport d'analyse =====
print(f"\n" + "=" * 80)
print("📊 ANALYSE DES RÉSULTATS")
print("=" * 80)

# Distance moyennes par query
print(f"\n📈 Distance moyenne (L2 Euclidienne):")
for i, (query, expected) in enumerate(test_queries):
    avg_dist = np.mean([r["distance"] for r in results_summary[i]["results"]])
    print(f"   {query}: {avg_dist:.4f}")

# Types de chunks trouvés
all_types = {}
for result in results_summary:
    for r in result["results"]:
        chunk_type = r["type"]
        all_types[chunk_type] = all_types.get(chunk_type, 0) + 1

print(f"\n🎯 Distribution des types de chunks trouvés (Top-5 sur {len(test_queries)} queries):")
for chunk_type, count in sorted(all_types.items(), key=lambda x: x[1], reverse=True):
    print(f"   {chunk_type}: {count} ({count / (5 * len(test_queries)) * 100:.1f}%)")

# Classes trouvées
all_classes = {}
for result in results_summary:
    for r in result["results"]:
        classe = r["classe"]
        all_classes[classe] = all_classes.get(classe, 0) + 1

print(f"\n📦 Distribution par classe thérapeutique:")
for classe, count in sorted(all_classes.items(), key=lambda x: x[1], reverse=True):
    print(f"   {classe}: {count}")

# ===== 4. Sauvegarder les résultats =====
output_file = PROJECT_ROOT / "test_results_768d.json"
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump({
        "model": EMBEDDING_MODEL,
        "dimensions": 768,
        "total_queries": len(test_queries),
        "total_chunks": len(chunks),
        "results": results_summary
    }, f, ensure_ascii=False, indent=2)

print(f"\n💾 Résultats sauvegardés: {output_file}")

print(f"\n" + "=" * 80)
print("✅ TEST COMPLET!")
print("=" * 80)
