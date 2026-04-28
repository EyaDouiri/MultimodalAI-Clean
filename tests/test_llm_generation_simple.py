#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test simple génération LLM"""

import json
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from config_llm import OllamaConnection, PromptManager
from datetime import datetime

print("="*80)
print("🧪 TEST SIMPLE GÉNÉRATION LLM")
print("="*80)

# Charge données
print("\n1️⃣  Chargement données...")
with open('chunks_structure_based_v4.json', encoding='utf-8') as f:
    chunks = json.load(f)
embeddings = np.load('embeddings_768d_mpnet.npy')
index = faiss.IndexFlatIP(embeddings.shape[1])
index.add(embeddings.astype(np.float32))
model = SentenceTransformer('all-mpnet-base-v2')
print(f"✓ {len(chunks)} chunks, index prêt")

# Connexion Ollama
print("\n2️⃣  Connexion Ollama...")
ollama = OllamaConnection()
available_models = ollama.list_available_models()
llm_model = [m for m in available_models if 'llama' in m.lower()][0]
print(f"✓ Modèle: {llm_model}")

# Une requête de test
query = "Quel produit pour renforcer l'immunité?"
print(f"\n3️⃣  Requête: '{query}'")

# Retrieval
query_emb = model.encode(query, convert_to_numpy=True).astype(np.float32)
scores, indices = index.search(np.array([query_emb]), k=3)

print(f"\n4️⃣  Résultats retrieval:")
context = "Contexte basé sur retrieval:\n"
for score, idx in zip(scores[0], indices[0]):
    chunk = chunks[idx]
    print(f"  [{score:.3f}] {chunk['product_name']}")
    context += f"\n{chunk['text'][:200]}...\n"

# Génération
print(f"\n5️⃣  Génération LLM (30 sec timeout)...")

prompt_manager = PromptManager()
prompt = prompt_manager.get_prompt_pedagogical(context, query, "intermediate")

print(f"  Prompt (100 chars): {prompt[:100]}...")

try:
    # Appel Ollama (timeout 120s intégré)
    response = ollama.generate(
        model=llm_model.split(":")[0],
        prompt=prompt,
        stream=False
    )
    
    if "error" in response:
        print(f"❌ Erreur Ollama: {response['error']}")
    else:
        ans = response.get("response", "")
        print(f"\n✓ Génération réussie ({len(ans)} chars)")
        print(f"  Réponse:\n{ans[:300]}...\n")
        
        # Sauvegarde
        result = {
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "retrieved_products": [chunks[int(idx)]['product_name'] for idx in indices[0]],
            "response": ans,
            "model": llm_model
        }
        with open('test_llm_simple_result.json', 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print("✓ Résultat sauvegardé: test_llm_simple_result.json")
        
except Exception as e:
    print(f"❌ Exception: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)
