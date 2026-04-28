# Pipeline RAG + LLM - Guide Complet

## 📋 Vue d'Ensemble

Ce projet implémente un **système RAG (Retrieval-Augmented Generation)** complet avec:
- **Phase Retrieval**: Récupération sémantique via embeddings (all-mpnet-base-v2 768D)
- **Phase LLM**: Génération de réponses via Ollama (Llama 2 / Meditron)
- **Prompt Engineering**: Comparaison de 4 styles de prompts
- **Apprentissage Adaptatif**: Formation personnalisée selon niveau utilisateur

---

## 🔧 Architecture Technique

### 1. Retrieval Backend (V4)
```
Données sources (220 produits)
  ↓
Chunking structure-based (440 chunks)
  ├─ clinical_profile (indications + mots-clés)
  └─ pharmacology_profile (composition + mécanisme)
  ↓
Embedding (all-mpnet-base-v2, 768D, normalisé)
  ↓
FAISS Index (Cosinus Similarity)
  ↓
Retrieval Top-5
```

**Performance**:
- Distance moyenne: 1.127 (L2) / 0.437 (Cosinus)
- Latence: ~54ms par requête
- Throughput: 18.5 requêtes/sec

### 2. LLM Generation (Ollama)
```
Query
  ↓
Embedding + Retrieval (top-5 chunks)
  ↓
Context Formatting
  ↓
Prompt Selection (4 styles)
  ↓
Ollama Generation (Llama 2 / Meditron)
  ↓
Post-processing & Evaluation
```

### 3. Adaptive Learning
```
User Profile
  ↓
Détection de niveau (Novice → Expert)
  ↓
Selection prompt template adapté
  ↓
Response adaptation (vocabulaire, structure)
  ↓
Learning path personnalisé
```

---

## 📦 Fichiers Système

### Configuration
- **`config_llm.py`** - Configuration Ollama, prompts, user levels

### Pipelines
- **`rag_llm_pipeline.py`** - Pipeline complet RAG + LLM
- **`prompt_comparison.py`** - Comparaison des styles de prompts
- **`adaptive_learning_system.py`** - Système d'apprentissage adaptatif

### Données Retrieval V4
- **`chunks_structure_based_v4.json`** (440 chunks)
- **`embeddings_768d_mpnet.npy`** (440×768 vecteurs)
- **`rag_index_768d_mpnet.faiss`** (Index FAISS)

### Résultats
- **`rag_llm_results.json`** - Résultats tests RAG + LLM
- **`prompt_comparison_results.json`** - Comparaison prompts
- **`adaptive_learning_profiles.json`** - Profils utilisateurs

---

## 🚀 Guide de Démarrage

### Étape 1: Préparer Ollama

```bash
# Installer Ollama (si nécessaire)
# https://ollama.ai

# Lancer le service Ollama
ollama serve

# Dans un autre terminal, télécharger les modèles
ollama pull llama2
ollama pull meditron

# Vérifier qu'il y a un modèle disponible
ollama list
```

**Output attendu**:
```
NAME              ID              SIZE    MODIFIED
llama2:latest     46dc1cc1bda2    3.8 GB  2 minutes ago
meditron:latest   7b8d8a1b3c5d    7.0 GB  5 minutes ago
```

### Étape 2: Exécuter les Tests

#### Test 1: Pipeline RAG Basique
```bash
python rag_llm_pipeline.py
```

**Sortie**:
```
✓ 440 chunks chargés
✓ Embeddings chargés: (440, 768)
✓ Modèle embedding chargé
✓ Ollama connecté
✓ Modèle LLM utilisé: llama2:latest

🔍 Traitement Query: 'Quel produit pour renforcer l'immunité?'

1️⃣  RETRIEVAL (k=5)...
✓ 5 documents récupérés
  - [0.721] LV Vitamine A (Complément alimentaire)
  - [0.680] MULTIBON IMMUNITÉ (Complément alimentaire)
  ...

2️⃣  GÉNÉRATION LLM...
✓ Réponse générée (2.3s)

3️⃣  RÉPONSE GÉNÉRÉE:
Pour renforcer votre immunité, je vous recommande...
```

#### Test 2: Comparaison Styles de Prompts
```bash
python prompt_comparison.py
```

**Sortie**:
```
🔬 TESTS DE COMPARAISON - 3 REQUÊTES, 4 PROMPT STYLES

TEST 1: Immunité générale
  [1] Simple RAG... ✓ Score: 0.68
  [2] Pédagogique Adaptatif... ✓ Score: 0.82
  [3] Chain-of-Thought... ✓ Score: 0.75
  [4] Few-Shot Learning... ✓ Score: 0.71

📊 RÉSUMÉ:
  Meilleur:  Pédagogique Adaptatif | Score: 0.82
  Pire:      Simple RAG              | Score: 0.68
  Moyenne:   0.74

Classement:
  1. Pédagogique Adaptatif    0.82
  2. Chain-of-Thought         0.75
  3. Few-Shot Learning        0.71
  4. Simple RAG               0.68
```

#### Test 3: Apprentissage Adaptatif
```bash
python adaptive_learning_system.py
```

**Sortie**:
```
👤 delegate_001 (Level: novice)
   Niveau: novice
   Score: 12/100
   Description: Nouveau délégué sans connaissance pharmaceutique
   Structure de réponse: intro_simple → points_clés → conseil_pratique

📈 Progression de delegate_001:
  Bonne réponse sur les vitamines... 🎖️  Progression utilisateur: novice → intermediate
    Score: 17/100 | Niveau: intermediate | Précision: 100%
```

---

## 📊 4 Styles de Prompts

### 1️⃣ Simple RAG
**Utilisation**: Tests basiques, requêtes directes
```
Structure: Context + Question → Réponse
Temps: ~2-3s
Score éval moyen: 0.65
```

### 2️⃣ Pédagogique Adaptatif (RECOMMANDÉ)
**Utilisation**: Formation délégués avec adaptation au niveau
```
Structure: Context → Formation structurée → Étapes → Résumé
Temps: ~3-5s
Score éval moyen: 0.82
Avantages: Meilleur score, plus pertinent, adapté niveau
```

### 3️⃣ Chain-of-Thought
**Utilisation**: Questions complexes, analyses
```
Structure: Thinking steps → Analyse → Conclusion
Temps: ~4-6s
Score éval moyen: 0.75
Avantages: Transparent, explicite
```

### 4️⃣ Few-Shot Learning
**Utilisation**: Patterns de réponse standardisés
```
Structure: Examples → Pattern learning → Réponse
Temps: ~3-4s
Score éval moyen: 0.71
Avantages: Cohérent, reproductible
```

---

## 👥 Niveaux Utilisateur

### Level 1: Novice
- **Caractéristiques**: Pas de connaissance pharmaceutique
- **Structure réponse**: Simple, points clés, pratique
- **Vocabulaire**: Très simple (pas de jargon)
- **Focus**: Indications simples, contre-indications critiques
- **Progression cible**: 10 interactions → Level 2

### Level 2: Intermediate
- **Caractéristiques**: Expérience basique
- **Structure réponse**: Introduction, détails, conseils
- **Vocabulaire**: Standard avec explications
- **Focus**: Indications, effets secondaires, utilisation
- **Progression cible**: 15 interactions → Level 3

### Level 3: Advanced
- **Caractéristiques**: Expérimenté
- **Structure réponse**: Analyses détaillées, mécanismes
- **Vocabulaire**: Spécialisée
- **Focus**: Mécanisme d'action, compositions, comparaisons
- **Progression cible**: 20 interactions → Level 4

### Level 4: Expert
- **Caractéristiques**: Pharmacien/scientifique
- **Structure réponse**: Scientifique, études, limitations
- **Vocabulaire**: Hautement spécialisée
- **Focus**: Pharmacologie détaillée, interactions complexes
- **Progression cible**: Continu

---

## 📈 Métriques d'Évaluation

```python
# Chaque réponse évaluée sur 5 critères (poids):

relevance      = 0.25  # Pertinence par rapport requête
clarity        = 0.20  # Clarté et facilité lecture
completeness   = 0.20  # Couverture des sujets
length_score   = 0.15  # Longueur appropriée (100-300 mots)
structure      = 0.20  # Organisation et structure

overall_score = (relevance*0.25 + clarity*0.20 + 
                 completeness*0.20 + length_score*0.15 + 
                 structure*0.20)

# Score global: 0.0 (mauvais) à 1.0 (excellent)
```

---

## 🔄 Workflow Complet

```
1. Utilisateur pose une question
   ↓
2. Détection du niveau utilisateur (profil ou auto-détection)
   ↓
3. Embedding de la requête
   ↓
4. Retrieval top-5 chunks pertinents
   ↓
5. Sélection du style de prompt adapté au niveau
   ↓
6. Génération via Ollama LLM
   ↓
7. Évaluation de la qualité
   ↓
8. Retour utilisateur + mise à jour profil
   ↓
9. Adaptation future basée sur progression
```

---

## 🔗 Intégrations Futures

### Phase Finale: Multilingue
```python
# Ajouter traduction automatique des réponses
from transformers import pipeline

translator = pipeline("translation_fr_to_en", model="Helsinki-NLP/opus-mt-fr-en")
response_en = translator(response_fr)[0]['translation_text']
```

### Évaluation Utilisateur
```python
# Feedback utilisateur simple
rating = input("Notez la réponse (1-5): ")
feedback = input("Commentaires: ")

# Ajuster le score utilisateur et le profil
user.update_score(points_from_rating, "user_feedback")
```

### Stockage Conversations
```python
# Sauvegarder les conversations pour suivi
conversation = {
    "user_id": user_id,
    "timestamp": datetime.now(),
    "query": query,
    "response": response,
    "evaluation": evaluation_scores,
    "user_feedback": feedback
}
```

---

## ⚡ Performance & Optimisations

### Benchmark Actuel
```
Retrieval: ~50-100ms
LLM Generation: 2-5 secondes
Total latency: 2.5-5.5s par requête
Throughput: 0.18-0.4 requêtes/seconde
```

### Optimisations Possibles
1. **Caching**: Stocker les réponses fréquentes
2. **Compression**: Réduire taille chunks
3. **Quantization**: Réduire dimensions embeddings (384D au lieu de 768D)
4. **GPU**: Utiliser GPU locale pour LLM (Ollama GPU mode)

---

## 💡 Prochaines Étapes

### Court terme
- [x] Valider Retrieval V4
- [x] Intégrer Ollama
- [x] Implémenter 4 styles de prompts
- [ ] Décider du style optimal pour production

### Moyen terme
- [ ] Tester avec **deuxième BD** (même technique)
- [ ] Comparer performance BD1 vs BD2
- [ ] Fine-tuner modèle LLM sur domaine pharmaceutique

### Long terme
- [ ] Ajouter support multilingue
- [ ] Implémenter retours utilisateurs
- [ ] Créer tableau de bord analytics
- [ ] Déployer en production

---

## 📚 Documentation Complète

Voir `rapport_rag_pipeline.tex` pour:
- Architecture détaillée
- Comparaison V2 vs V4
- Formules mathématiques
- Résultats complets
- Notations et conventions

---

**Version**: 1.0 - Phase LLM & Prompt Engineering
**Date**: Mars 2026
