# 📁 Structure Organisée du Projet RAG

## Arborescence

```
c:\Users\eyaen\Desktop\PI\
│
├── 🔧 Configuration & Documentation (racine)
│   ├── requirements.txt                    # Dépendances Python
│   ├── README_LLM.md                      # Guide LLM & prompts
│   ├── rapport_rag_pipeline.tex           # Rapport technique (LaTeX)
│   ├── EXECUTION_GUIDE.md                 # Guide d'exécution
│   ├── RAG_PIPELINE_V4_DOCUMENTATION.md   # Doc retrieval V4
│   └── rag_llm_pipeline.py                # 🔴 PIPELINE PRINCIPAL
│
├── 📊 data/                               # Données source et traitées
│   ├── raw/                               # Données brutes (source)
│   │   ├── medicaments_clean.json
│   │   └── medicaments_clean_enrichis_pharmacologie.json
│   └── processed/                         # Données traitées
│       ├── chunks_structure_based_v4.json (440 chunks)
│       └── queries_100_comprehensive.json (100 queries)
│
├── 🎯 vectorial_db/                      # Embeddings & FAISS
│   ├── embeddings/                        # Vecteurs d'embedding
│   │   ├── embeddings_768d_mpnet.npy     (440×768 vectors)
│   │   └── embeddings_768d_mpnet_bd2.npy (alternative)
│   └── indexes/                           # Index FAISS
│       └── rag_index_768d_mpnet.faiss    (IndexFlatIP)
│
├── 🔍 retrieval/                         # Système de recherche
│   ├── chunking/                          # Logique de chunking
│   │   └── chunking_structure_based_v4.py
│   ├── embedding/                         # Génération embeddings
│   │   └── pipeline_embeddings_768d.py
│   └── search/                            # Moteur de recherche
│       └── (future search implementations)
│
├── 🤖 generation/                        # Système LLM
│   ├── config/                            # Configuration Ollama
│   │   └── config_llm.py                  # 🔴 Config LLM (imports here)
│   ├── prompts/                           # Templates de prompts
│   │   └── (future prompt templates)
│   └── models/                            # Wrappers modèles
│       └── (future model implementations)
│
└── 🧪 tests/                             # Tests et évaluation
    ├── run_complete_rag.py                # 🔴 TEST RUNNER PRINCIPAL
    ├── prompt_comparison.py               # Comparaison styles
    ├── adaptive_learning_system.py        # Système adaptatif
    ├── test_*.py                          # Autres tests
    ├── logs/                              # Logs d'exécution
    └── results/                           # Résultats de tests
        ├── complete_rag_test_*.json       # Résultats tests complets
        ├── prompt_comparison_results.json
        ├── adaptive_learning_profiles.json
        └── test_*.json                    # Autres résultats
```

## Commandes Principales

### ✅ Test du Pipeline RAG Complet
```bash
cd c:\Users\eyaen\Desktop\PI
python tests/run_complete_rag.py
```

### ✅ Comparaison des Styles de Prompts
```bash
python tests/prompt_comparison.py
```

### ✅ Pipeline RAG Complet (ancienne approche)
```bash
python rag_llm_pipeline.py
```

## Fichiers Critiques

| Fichier | Rôle | État |
|---------|------|------|
| `rag_llm_pipeline.py` | Pipeline RAG principal | ✅ Utilisable |
| `tests/run_complete_rag.py` | Test runner unifié | ✅ Créé |
| `generation/config/config_llm.py` | Configuration Ollama | ✅ En place |
| `data/processed/chunks_structure_based_v4.json` | 440 chunks V4 | ✅ Moved |
| `vectorial_db/indexes/rag_index_768d_mpnet.faiss` | Index FAISS | ✅ Moved |

## Chemins Importants

```python
# Données
DATA_PROCESSED = ROOT / "data" / "processed"
VECTORIAL_EMBEDDINGS = ROOT / "vectorial_db" / "embeddings"
VECTORIAL_INDEXES = ROOT / "vectorial_db" / "indexes"
GENERATION_CONFIG = ROOT / "generation" / "config"
TESTS_RESULTS = ROOT / "tests" / "results"
```

## Améliorations Réalisées

✅ **Organisation Modulaire**
- Séparation claire: data / vectorial_db / retrieval / generation / tests
- Facile à maintenir et étendre

✅ **Chemins Relatifs**
- Tous les imports utilisent `Path()` pour compatibilité cross-platform
- Fonctionnent depuis n'importe quel répertoire

✅ **Test Runner Unifié**
- `tests/run_complete_rag.py` orchestre tout le pipeline
- Évalue tous les styles de prompts en une seule exécution

✅ **Importation Robuste**
- `sys.path.insert()` pour chercher `config_llm` dans le bon dossier
- Pas de hardcoding de chemins

## Prochaines Étapes

1. **Exécuter le test complet**: `python tests/run_complete_rag.py`
2. **Analyser les résultats**: Regarder `tests/results/complete_rag_test_*.json`
3. **Optimiser les prompts**: Modifier les templates dans `generation/config/config_llm.py`
4. **Évaluer les modèles**: Ajouter des métriques dans `tests/run_complete_rag.py`
