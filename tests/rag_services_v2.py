"""
RAG SERVICES V2 - Retrieval filtré par catégorie et assignation
Filtrage intelligent: delegate category + assigned products + top_k=3
"""

import json
import numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer
import faiss

from config import (
    EMBEDDING_MODEL,
    CHUNKS_METADATA_PATH,
)

PROJECT_ROOT = Path(__file__).parent
CHUNKS_SPECIFIC_METADATA_PATH = PROJECT_ROOT / "chunks_specific_metadata.json"
EMBEDDINGS_SPECIFIC_PATH = PROJECT_ROOT / "embeddings_specific.npy"
FAISS_INDEX_SPECIFIC_PATH = PROJECT_ROOT / "rag_index_specific.faiss"

# ============================================================================
# RAG SERVICE V2 - Avec filtrage
# ============================================================================

class RAGServiceV2:
    def __init__(self, delegate_category=None, assigned_products=None):
        """
        Initialiser le service RAG V2 avec filtrage
        
        Args:
            delegate_category: Catégorie du délégué (ex: "Complément alimentaire", "Soin")
            assigned_products: Liste de noms de produits assignés au délégué
        """
        self.delegate_category = delegate_category
        self.assigned_products = assigned_products or []
        self.model = SentenceTransformer(EMBEDDING_MODEL)
        self.chunks = None
        self.embeddings = None
        self.faiss_index = None
        
        self._load_data()
    
    def _load_data(self):
        """Charger les chunks spécifiques et embeddings"""
        print("📦 Chargement des données RAG V2...")
        
        # Charger metadata
        with open(CHUNKS_SPECIFIC_METADATA_PATH, 'r', encoding='utf-8') as f:
            self.chunks = json.load(f)
        
        print(f"✓ {len(self.chunks)} chunks chargés")
        
        # Charger embeddings
        if EMBEDDINGS_SPECIFIC_PATH.exists():
            self.embeddings = np.load(EMBEDDINGS_SPECIFIC_PATH)
            print(f"✓ Embeddings chargés (shape: {self.embeddings.shape})")
        else:
            raise FileNotFoundError(f"Embeddings non trouvés: {EMBEDDINGS_SPECIFIC_PATH}")
        
        # Charger FAISS index
        if FAISS_INDEX_SPECIFIC_PATH.exists():
            self.faiss_index = faiss.read_index(str(FAISS_INDEX_SPECIFIC_PATH))
            print(f"✓ Index FAISS chargé ({FAISS_INDEX_SPECIFIC_PATH})")
        else:
            raise FileNotFoundError(f"Index FAISS non trouvé: {FAISS_INDEX_SPECIFIC_PATH}")
    
    def _apply_filters(self, chunk_indices):
        """
        Filtre les indices de chunks selon les critères du délégué
        
        Args:
            chunk_indices: Indices bruts retournés par FAISS
        
        Returns:
            Indices filtrés
        """
        filtered = []
        
        for idx in chunk_indices:
            if idx >= len(self.chunks):
                continue
            
            chunk = self.chunks[idx]
            category = chunk.get("category", "")
            product_name = chunk.get("product_name", "")
            
            # Filtre 1: Si delegate_category est spécifié, le chunk doit matcher
            if self.delegate_category:
                # Normaliser les comparaisons (minuscules)
                chunk_cat = category.lower().strip()
                delegate_cat = self.delegate_category.lower().strip()
                
                if chunk_cat != delegate_cat:
                    continue
            
            # Filtre 2: Si assigned_products est spécifié, le produit doit y être
            if self.assigned_products:
                if product_name not in self.assigned_products:
                    continue
            
            filtered.append(idx)
        
        return filtered
    
    def retrieve_by_similarity(self, query, top_k=3, use_filters=True):
        """
        Récupérer les chunks les plus similaires avec filtrage optionnel
        
        Args:
            query: La question du délégué
            top_k: Nombre de résultats à retourner (défaut: 3)
            use_filters: Appliquer les filtres de catégorie/assignment (défaut: True)
        
        Returns:
            Liste de dicts avec: chunk, product_name, category, distance, rank
        """
        
        # Encoder la requête
        query_embedding = self.model.encode([query], convert_to_numpy=True)
        query_embedding = query_embedding.astype(np.float32)
        
        # Recherche initiale: récupérer davantage pour compenser le filtrage
        # Si on filtre, on demande plus de résultats initialement
        initial_k = top_k * 10 if use_filters else top_k
        initial_k = min(initial_k, len(self.chunks))
        
        distances, indices = self.faiss_index.search(query_embedding, initial_k)
        
        # Aplatir les résultats (batch_size=1)
        distances = distances[0]
        indices = indices[0]
        
        # Créer un mapping: index → distance
        idx_to_distance = {int(idx): float(dist) for idx, dist in zip(indices, distances)}
        
        # Appliquer les filtres
        if use_filters:
            filtered_indices = self._apply_filters(indices)
        else:
            filtered_indices = list(indices)
        
        # Récupérer les top_k filtrés
        results = []
        for rank, chunk_idx in enumerate(filtered_indices[:top_k]):
            chunk = self.chunks[int(chunk_idx)]
            distance = idx_to_distance.get(int(chunk_idx), 0.0)
            
            results.append({
                "rank": rank + 1,
                "product_name": chunk.get("product_name", "Unknown"),
                "category": chunk.get("category", "Unknown"),
                "chunk_type": chunk.get("chunk_type", "unknown"),
                "distance": distance,
                "similarity_score": 1 / (1 + distance),  # Convertir distance en score
                "chunk_text": chunk.get("text", "")[:300] + "...",  # Premiers 300 chars
                "full_chunk_text": chunk.get("text", ""),
                "chunk_id": chunk.get("chunk_id", "")
            })
        
        return results
    
    def get_stats(self):
        """Retourner les statistiques du RAG Service"""
        from collections import Counter
        
        categories = Counter(c.get("category", "Unknown") for c in self.chunks)
        chunk_types = Counter(c.get("chunk_type", "unknown") for c in self.chunks)
        
        return {
            "total_chunks": len(self.chunks),
            "total_embeddings": len(self.embeddings),
            "embedding_dimension": self.embeddings.shape[1],
            "categories": dict(categories),
            "chunk_types": dict(chunk_types),
            "delegate_category_filter": self.delegate_category,
            "assigned_products_filter": self.assigned_products,
            "active_filters": bool(self.delegate_category or self.assigned_products)
        }


# ============================================================================
# COMPATIBILITY WITH EXISTING CODE
# ============================================================================

class RAGService:
    """
    Wrapper pour compatibilité avec le code existant
    Par défaut, utilise RAGServiceV2 sans filtres
    """
    def __init__(self, use_faiss=True, use_pinecone=False):
        self._service_v2 = RAGServiceV2()
    
    def retrieve_by_similarity(self, query, top_k=None):
        """Récupérer sans filtres (compatibilité ancienne API)"""
        if top_k is None:
            top_k = 5  # Ancien défaut
        return self._service_v2.retrieve_by_similarity(query, top_k=top_k, use_filters=False)


# ============================================================================
# TESTING FUNCTIONS
# ============================================================================

def test_with_filters():
    """Tester la retrieval avec filtres"""
    print("\n" + "=" * 80)
    print("🧪 TEST - Retrieval avec filtres")
    print("=" * 80)
    
    # Test 1: Sans filtres
    print("\n\n[TEST 1] Retrieval SANS filtres (top_k=3)")
    print("-" * 80)
    service = RAGServiceV2()
    results = service.retrieve_by_similarity("carence en fer", top_k=3, use_filters=False)
    
    print(f"\nRésultats pour 'carence en fer':")
    for r in results:
        print(f"\n  [{r['rank']}] {r['product_name']} (score: {r['similarity_score']:.4f})")
        print(f"       Catégorie: {r['category']}")
        print(f"       Type: {r['chunk_type']}")
        print(f"       Texte: {r['chunk_text']}")
    
    # Test 2: Avec filtre catégorie
    print("\n\n[TEST 2] Retrieval AVEC filtre catégorie")
    print("-" * 80)
    print("Filtre: delegate_category='Complément alimentaire'")
    
    service_filtered = RAGServiceV2(delegate_category="Complément alimentaire")
    results_filtered = service_filtered.retrieve_by_similarity("carence en fer", top_k=3, use_filters=True)
    
    print(f"\nRésultats filtrés:")
    for r in results_filtered:
        print(f"\n  [{r['rank']}] {r['product_name']} (score: {r['similarity_score']:.4f})")
        print(f"       Catégorie: {r['category']}")
        print(f"       Texte: {r['chunk_text']}")
    
    # Test 3: Stats
    print("\n\n[TEST 3] Statistiques")
    print("-" * 80)
    stats = service.get_stats()
    print(f"\n  Total chunks: {stats['total_chunks']}")
    print(f"  Total embeddings: {stats['total_embeddings']}")
    print(f"  Embedding dimension: {stats['embedding_dimension']}")
    print(f"\n  Catégories couvertes:")
    for cat, count in sorted(stats['categories'].items(), key=lambda x: -x[1])[:5]:
        print(f"    {cat}: {count}")
    print(f"\n  Types de chunks:")
    for ctype, count in stats['chunk_types'].items():
        print(f"    {ctype}: {count}")


if __name__ == "__main__":
    test_with_filters()
