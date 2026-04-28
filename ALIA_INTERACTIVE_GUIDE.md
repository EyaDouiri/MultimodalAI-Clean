# 🤖 ALIA Interactive Chat - Guide de Démarrage

## Qu'est-ce que c'est ?

**Alia** est un système conversationnel adaptatif qui :
- 🧪 **Teste le niveau** du délégué avec des questions
- 📈 **Auto-évalue** progressivement ses réponses
- 🎓 **Propose des formations adaptées** selon le niveau
- 🔄 **Compare 2 LLM** (llama2 vs meditron) en temps réel
- 💾 **Génère un rapport** de comparaison

## Médicaments à Maîtriser

- **med1** : Médicament 1 (niveau débutant)
- **med2** : Médicament 2 (niveau intermédiaire)  
- **med3** : Médicament 3 (niveau avancé)

## Démarrer Alia

### Prérequis
1. **Ollama doit tourner** → `ollama serve` dans un autre terminal
2. **Les modèles doivent être disponibles** : `ollama list`
   - llama2:latest ✓
   - meditron:latest ✓

### Lancer le chat

```bash
# Depuis le répertoire PI
cd "c:\Users\eyaen\Desktop\PI"

# Activer l'environnement virtuel
.\alia_venv\Scripts\activate.ps1

# Lancer Alia
python alia_interactive_chat.py
```

## Utilisation

### Premier Message (Initialiser le Test)

Tapez simplement :
```
Salut
```

Alia commencera à tester votre niveau progressivement.

### Répondre aux Questions

Alia posera des questions comme :
- "Quel est le rôle principal du med1?"
- "A quel type de patient prescrirais-tu med2?"
- "Explique les interactions possibles du med3."

Répondez normalement. Alia évaluera avec **llama2** et **meditron** en parallèle.

### Commandes Spéciales

| Commande | Effet |
|----------|-------|
| `salir` | Terminer le chat et générer le rapport |
| `reset` | Recommencer avec un nouveau profil |
| `nivel` | Voir votre niveau et progrès actuels |

## Résultats

Pour chaque question :
1. **Réponse llama2** → S'affiche d'abord
2. **Réponse meditron** → S'affiche ensuite
3. Vous voyez les **deux évaluations en temps réel**
4. Votre niveau s'ajuste automatiquement

## Rapport Final

À la fin, un fichier JSON est généré dans `tests/results/` :
```
alia_comparison_llama2_vs_meditron_YYYYMMDD_HHMMSS.json
```

Contient :
- Tous les échanges
- Comparaison des deux LLM
- Progès pour chaque médicament
- Niveau final détecté

## Workflow Recommandé

1. ✅ Vérifier qu'Ollama tourne
2. ✅ Lancer `alia_interactive_chat.py`
3. ✅ Commencer par "Salut"
4. ✅ Répondre naturellement aux questions
5. ✅ Observez les deux LLM évaluer votre réponse
6. ✅ Continuez 5-10 tours
7. ✅ Tapez `salir` pour terminer
8. ✅ Analyser le rapport de comparaison

## Métriques de Comparaison

Le système évalue :
- ✓ **Exactitude médicale**
- ✓ **Pertinence de la réponse**
- ✓ **Complétude de l'explication**
- ✓ **Clarté de la communication**
- ✓ **Qualité pédagogique**

## Exemple d'Interaction

```
[NOVICE] Turno 1 - med1: Salut

▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌
📤 Evaluando con llama2:latest...
📤 Evaluando con meditron:latest...

────────────────────────────────────────
🤖 llama2:latest:
────────────────────────────────────────
[Évaluation d'Alia avec llama2]

────────────────────────────────────────
🤖 meditron:latest:
────────────────────────────────────────
[Évaluation d'Alia avec meditron]

📊 Nivel actual: novice (42%)
Progreso: med1=10%, med2=0%, med3=0%

[NOVICE] Turno 2 - med2: ...
```

## Notes Importantes

- Chaque réponse est évaluée par **DEUX LLM en parallèle**
- Le niveau s'ajuste automatiquement selon votre performance
- Les questions deviennent plus complexes au fur et à mesure
- Vous pouvez revoir votre niveau avec `nivel`

---

**Prêt à commencer ? Lancez Alia ! 🚀**
