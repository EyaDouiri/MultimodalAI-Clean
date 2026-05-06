"""
retriever.py - Alia Agent
Charge l'index FAISS + chunks et récupère les passages
les plus pertinents pour un produit ou une question donnée.
"""

import json
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional
try:
    from sentence_transformers import SentenceTransformer
    import faiss
    EMBEDDING_BACKEND_OK = True
except Exception as exc:
    SentenceTransformer = None
    faiss = None
    EMBEDDING_BACKEND_OK = False
    print(f"[Retriever] Backend embeddings indisponible, fallback lexical actif: {exc}")


# ── Config (adapte les chemins à ton projet) ──────────────────────────────────
EMBEDDING_MODEL = "all-mpnet-base-v2"
PROJECT_ROOT = Path(__file__).resolve().parent
CHUNKS_PATH = PROJECT_ROOT / "data/processed/chunks_structure_based_v4.json"
EMBEDDINGS_PATH = PROJECT_ROOT / "vectorial_db/embeddings/embeddings_768d_mpnet.npy"
FAISS_INDEX_PATH = PROJECT_ROOT / "vectorial_db/indexes/rag_index_768d_mpnet.faiss"
# ─────────────────────────────────────────────────────────────────────────────


class AliasRetriever:
    """
    Wrapper FAISS pour Alia.
    - Recherche sémantique dans les chunks
    - Filtre optionnel par nom de produit (pour le Module 1 : on veut 
      uniquement les chunks du produit en cours de formation)
    """

    def __init__(self):
        print("[Retriever] Chargement chunks...")
        if CHUNKS_PATH.exists():
            with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
                self.chunks: List[Dict] = json.load(f)
        else:
            self.chunks = []
            print(f"[Retriever] Fichier chunks introuvable: {CHUNKS_PATH}. Mode degrade sans base documentaire.")
        self.model = None
        self.index = None
        self.use_embeddings = False

        if EMBEDDING_BACKEND_OK and self.chunks and FAISS_INDEX_PATH.exists():
            try:
                print("[Retriever] Chargement modèle d'embedding...")
                self.model = SentenceTransformer(EMBEDDING_MODEL)
                print("[Retriever] Chargement index FAISS...")
                self.index = faiss.read_index(str(FAISS_INDEX_PATH))
                self.use_embeddings = True
                print(f"[Retriever] Prêt (semantic) — {len(self.chunks)} chunks, index {self.index.ntotal} vecteurs")
            except Exception as exc:
                self.use_embeddings = False
                print(f"[Retriever] Echec semantic retrieval, fallback lexical actif: {exc}")
        else:
            print(f"[Retriever] Prêt (lexical) — {len(self.chunks)} chunks")

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
        if self.use_embeddings and self.model is not None and self.index is not None:
            query_emb = self.model.encode(query, convert_to_numpy=True).astype(np.float32)
            k_search = k * 6 if product_filter else k
            distances, indices = self.index.search(np.array([query_emb]), k=k_search)

            results = []
            for dist, idx in zip(distances[0], indices[0]):
                if idx < 0 or idx >= len(self.chunks):
                    continue
                chunk = self.chunks[idx].copy()
                chunk["score"] = float(dist)
                if product_filter and chunk.get("product_name", "").strip() != product_filter.strip():
                    continue
                results.append(chunk)
                if len(results) >= k:
                    break
            return results

        # Fallback lexical: scoring par recouvrement de mots
        query_terms = {t for t in query.lower().split() if len(t) > 2}
        candidates = self.chunks
        if product_filter:
            candidates = [
                c for c in candidates
                if c.get("product_name", "").strip() == product_filter.strip()
            ]

        scored = []
        for chunk in candidates:
            text = (chunk.get("text") or "").lower()
            overlap = sum(1 for term in query_terms if term in text)
            if overlap == 0 and query_terms:
                continue
            enriched = chunk.copy()
            enriched["score"] = float(overlap)
            scored.append(enriched)

        scored.sort(key=lambda c: c.get("score", 0), reverse=True)
        return scored[:k]

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
