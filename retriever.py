"""
retriever.py - Alia Agent
Charge l'index FAISS + chunks et récupère les passages
les plus pertinents pour un produit ou une question donnée.
"""

import json
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional
from sentence_transformers import SentenceTransformer
import faiss


# ── Config (adapte les chemins à ton projet) ──────────────────────────────────
EMBEDDING_MODEL   = "all-mpnet-base-v2"
CHUNKS_PATH       = Path("data/processed/chunks_structure_based_v4.json")
EMBEDDINGS_PATH   = Path("vectorial_db/embeddings/embeddings_768d_mpnet.npy")
FAISS_INDEX_PATH  = Path("vectorial_db/indexes/rag_index_768d_mpnet.faiss")
# ─────────────────────────────────────────────────────────────────────────────


class AliasRetriever:
    """
    Wrapper FAISS pour Alia.
    - Recherche sémantique dans les chunks
    - Filtre optionnel par nom de produit (pour le Module 1 : on veut 
      uniquement les chunks du produit en cours de formation)
    """

    def __init__(self):
        print("[Retriever] Chargement modèle d'embedding...")
        self.model = SentenceTransformer(EMBEDDING_MODEL)

        print("[Retriever] Chargement chunks...")
        with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
            self.chunks: List[Dict] = json.load(f)

        print("[Retriever] Chargement index FAISS...")
        self.index = faiss.read_index(str(FAISS_INDEX_PATH))

        print(f"[Retriever] Prêt — {len(self.chunks)} chunks, index {self.index.ntotal} vecteurs")

    def search(
        self,
        query: str,
        k: int = 4,
        product_filter: Optional[str] = None
    ) -> List[Dict]:
        """
        Recherche les k chunks les plus proches de la query.
        
        Args:
            query          : question ou sujet à rechercher
            k              : nombre de chunks à retourner
            product_filter : si fourni, ne retourne que les chunks de ce produit
                             (utilisé dans Module 1 pour rester focalisé)
        
        Returns:
            Liste de chunks triés par pertinence, chacun avec 'score' ajouté
        """
        # Encoder la query
        query_emb = self.model.encode(query, convert_to_numpy=True).astype(np.float32)

        # Si filtre produit : chercher plus large puis filtrer
        k_search = k * 6 if product_filter else k
        distances, indices = self.index.search(np.array([query_emb]), k=k_search)

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx < 0 or idx >= len(self.chunks):
                continue
            chunk = self.chunks[idx].copy()
            chunk["score"] = float(dist)

            # Filtre par produit si demandé
            if product_filter:
                if chunk.get("product_name", "").strip() != product_filter.strip():
                    continue

            results.append(chunk)
            if len(results) >= k:
                break

        return results

    def get_product_chunks(self, product_name: str) -> List[Dict]:
        """
        Retourne TOUS les chunks d'un produit donné.
        Utile pour le Module 1 : on veut tout le contenu du produit.
        """
        return [
            c for c in self.chunks
            if c.get("product_name", "").strip() == product_name.strip()
        ]

    def format_context(self, chunks: List[Dict]) -> str:
        """
        Formate les chunks récupérés en un bloc de contexte
        prêt à être injecté dans le prompt du LLM.
        """
        sections = []
        for chunk in chunks:
            chunk_type = chunk.get("chunk_type", "unknown")
            label = "PROFIL CLINIQUE" if chunk_type == "clinical_profile" else "PROFIL PHARMACOLOGIQUE"
            sections.append(f"[{label}]\n{chunk['text']}")
        return "\n\n---\n\n".join(sections)


# --- Test rapide ---
if __name__ == "__main__":
    retriever = AliasRetriever()

    product = "Pédiakids Varispray"
    print(f"\n=== Chunks directs pour : {product} ===")
    chunks = retriever.get_product_chunks(product)
    print(f"Trouvé : {len(chunks)} chunks")
    for c in chunks:
        print(f"  - [{c['chunk_type']}] {len(c['text'])} chars")

    print(f"\n=== Recherche sémantique filtrée : {product} ===")
    results = retriever.search(
        query="indications et utilisation du produit",
        k=2,
        product_filter=product
    )
    for r in results:
        print(f"  Score: {r['score']:.3f} | Type: {r['chunk_type']}")
        print(f"  Extrait: {r['text'][:200]}...")
        print()

    print("\n=== Contexte formaté pour le prompt ===")
    context = retriever.format_context(chunks)
    print(context[:600], "...")
