"""
RAG PIPELINE V4 - Embeddings 768D avec all-mpnet-base-v2
Modèle: all-mpnet-base-v2 (768 dimensions)
Source chunks: chunks_structure_based_v4.json
"""

import json
import numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer
import faiss
import time

PROJECT_ROOT = Path(__file__).parent

# Configuration
EMBEDDING_MODEL = "all-mpnet-base-v2"
EMBEDDING_DIMENSION = 768
CHUNKS_PATH = PROJECT_ROOT / "chunks_structure_based_v4.json"
EMBEDDINGS_PATH = PROJECT_ROOT / "embeddings_768d_mpnet.npy"
FAISS_INDEX_PATH = PROJECT_ROOT / "rag_index_768d_mpnet.faiss"

print("=" * 80)
print("🔨 RAG PIPELINE V4 - EMBEDDINGS 768D (all-mpnet-base-v2)")
print("=" * 80)

# ===== 1. Charger les chunks =====
print(f"\n📦 Chargement des chunks...")
start_time = time.time()
with open(CHUNKS_PATH, 'r', encoding='utf-8') as f:
    chunks = json.load(f)
load_time = time.time() - start_time
print(f"✓ {len(chunks)} chunks chargés en {load_time:.2f}s")

# ===== 2. Charger le modèle =====
print(f"\n🧠 Chargement du modèle: {EMBEDDING_MODEL}")
print(f"   Dimensions: {EMBEDDING_DIMENSION}")
start_time = time.time()
model = SentenceTransformer(EMBEDDING_MODEL)
model_load_time = time.time() - start_time
print(f"✓ Modèle chargé en {model_load_time:.2f}s")

# ===== 3. Générer les embeddings =====
print(f"\n⚡ Génération des embeddings...")
texts = [chunk["text"] for chunk in chunks]

start_time = time.time()
embeddings = model.encode(texts, batch_size=32, show_progress_bar=True, 
                          convert_to_numpy=True)
encode_time = time.time() - start_time

print(f"✓ {len(embeddings)} embeddings générés en {encode_time:.2f}s")
print(f"✓ Shape: {embeddings.shape}")
print(f"✓ Temps/chunk: {encode_time/len(chunks)*1000:.1f}ms")

# Statistiques
mean_norm = np.mean(np.linalg.norm(embeddings, axis=1))
std_norm = np.std(np.linalg.norm(embeddings, axis=1))
print(f"✓ Norme moyenne: {mean_norm:.4f} ± {std_norm:.4f}")

# ===== 4. Sauvegarder les embeddings =====
print(f"\n💾 Sauvegarde des embeddings...")
embeddings_fp32 = embeddings.astype(np.float32)
np.save(EMBEDDINGS_PATH, embeddings_fp32)
print(f"✓ Sauvegardé: {EMBEDDINGS_PATH}")
print(f"✓ Taille: {EMBEDDINGS_PATH.stat().st_size / 1024 / 1024:.1f} MB")

# ===== 5. Créer l'index FAISS =====
print(f"\n🏗️  Création de l'index FAISS (IndexFlatL2)...")
start_time = time.time()
index = faiss.IndexFlatL2(EMBEDDING_DIMENSION)
index.add(embeddings_fp32)
faiss_time = time.time() - start_time
print(f"✓ Index créé en {faiss_time:.2f}s avec {index.ntotal} vecteurs")

# ===== 6. Sauvegarder l'index =====
print(f"\n💾 Sauvegarde de l'index FAISS...")
faiss.write_index(index, str(FAISS_INDEX_PATH))
print(f"✓ Sauvegardé: {FAISS_INDEX_PATH}")
print(f"✓ Taille: {FAISS_INDEX_PATH.stat().st_size / 1024 / 1024:.1f} MB")

# ===== 7. Test rapide =====
print(f"\n🧪 Test de similarité sur 3 requêtes...")
test_queries = [
    "vitamines pour la fatigue",
    "traitement de la douleur",
    "antibiotiques et infection"
]

for query in test_queries:
    query_emb = model.encode(query, convert_to_numpy=True).astype(np.float32)
    distances, indices = index.search(np.array([query_emb]), k=3)
    
    print(f"\n   Query: '{query}'")
    for rank, (idx, dist) in enumerate(zip(indices[0], distances[0]), 1):
        product = chunks[idx]['product_name']
        chunk_type = chunks[idx]['chunk_type']
        print(f"      {rank}. [{dist:.3f}] {product} ({chunk_type})")

# ===== Résumé final =====
print(f"\n" + "=" * 80)
print("✅ RAG PIPELINE V4 COMPLET!")
print("=" * 80)
print(f"\n📊 Résumé:")
print(f"   Modèle: {EMBEDDING_MODEL}")
print(f"   Dimensions: {EMBEDDING_DIMENSION}")
print(f"   Chunks: {len(chunks)}")
print(f"   Index: FAISS IndexFlatL2 (Distance L2/Euclidienne)")
print(f"\n📁 Fichiers générés:")
print(f"   ✓ {EMBEDDINGS_PATH.name}")
print(f"   ✓ {FAISS_INDEX_PATH.name}")
print(f"   ✓ {CHUNKS_PATH.name}")
print(f"\n⏱️  Performance:")
print(f"   Load chunks: {load_time:.2f}s")
print(f"   Load model: {model_load_time:.2f}s")
print(f"   Encode: {encode_time:.2f}s ({encode_time/len(chunks)*1000:.1f}ms/chunk)")
print(f"   Build FAISS: {faiss_time:.2f}s")
print(f"   TOTAL: {load_time + model_load_time + encode_time + faiss_time:.2f}s")