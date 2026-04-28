"""
benchmark.py - Alia Benchmark v1
Compare : 4 LLMs × 4 techniques de prompt × 7 scénarios
Métriques : Faithfulness | Pedagogical Quality | Tone | Boundary | Fluency

Usage :
    python benchmark.py

Résultats :
    - tableau console (meilleur LLM + meilleure technique)
    - benchmark_results.json (détail complet)
    - benchmark_summary.csv (tableau exportable)
"""

import os
import json
import csv
import time
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════

# Modèles à comparer (tous actifs sur Groq en avril 2026)
MODELS = {
    "llama-3.1-8b":       "llama-3.1-8b-instant",           # rapide, léger
    "llama-3.3-70b":      "llama-3.3-70b-versatile",        # puissant
    "llama-4-scout":      "meta-llama/llama-4-scout-17b-16e-instruct",  # multimodal, récent
    "qwen3-32b":          "qwen/qwen3-32b",                  # fort en instruction-following
}

# Modèle juge (le plus fort — ne pas changer)
JUDGE_MODEL = "llama-3.3-70b-versatile"

# Produit de test
PRODUCT_NAME = "FONGIDERM Antifongique Crème"

# Contexte RAG simulé (ce que le retriever donnerait normalement)
PRODUCT_CONTEXT = """
[Chunk 1 — Profil clinique]
Produit : FONGIDERM Antifongique Crème
Forme : Crème topique en tube de 30g
Principe actif : Bifonazole 1%
Indications : Mycoses cutanées superficielles (pied d'athlète, intertrigo, teigne, pityriasis versicolor)
Posologie : 1 application par jour pendant 2 à 4 semaines selon localisation
Contre-indications : Hypersensibilité au bifonazole ou excipients
Effets indésirables : Légère irritation locale possible en début de traitement

[Chunk 2 — Profil pharmacologique]
Mécanisme d'action : Inhibition de la synthèse de l'ergostérol (composant membranaire des champignons)
Spectre : Dermatophytes, levures (Candida), Malassezia furfur
Résultat visible : Amélioration en 48-72h, guérison complète en 2-4 semaines
Avantage différenciant : Une seule application quotidienne (observance optimale vs concurrents 2x/jour)
Conservation : À température ambiante, à l'abri de la lumière
"""

# ══════════════════════════════════════════════════════════════════════════════
# SCÉNARIOS DE TEST (7 cas réels Module 1)
# ══════════════════════════════════════════════════════════════════════════════

SCENARIOS = [
    {
        "id": "S1",
        "name": "Premier contact — délégué débutant",
        "delegue_message": "Bonjour, je commence ma formation aujourd'hui.",
        "conversation_history": "",
        "niveau": "débutant",
        "expected_behavior": "Accueil chaleureux, présentation du produit claire et adaptée débutant, pas de jargon excessif",
    },
    {
        "id": "S2",
        "name": "Question sur le mécanisme d'action",
        "delegue_message": "Comment ça marche exactement le FONGIDERM ?",
        "conversation_history": "Alia : Bienvenue ! Aujourd'hui on travaille sur FONGIDERM.\nDélégué : Ok je suis prêt.",
        "niveau": "débutant",
        "expected_behavior": "Expliquer le mécanisme (ergostérol) de façon simple, analogie possible, pas de récitation brute",
    },
    {
        "id": "S3",
        "name": "Réponse incomplète du délégué",
        "delegue_message": "FONGIDERM c'est pour les infections de la peau je crois.",
        "conversation_history": "Alia : Peux-tu me décrire FONGIDERM avec tes propres mots ?\nDélégué : FONGIDERM c'est pour les infections de la peau je crois.",
        "niveau": "débutant",
        "expected_behavior": "Valider ce qui est juste, compléter ce qui manque (mycoses spécifiquement, pas toutes infections), poser une question de suivi",
    },
    {
        "id": "S4",
        "name": "Message hors-sujet / social",
        "delegue_message": "Tu es vraiment sympa comme formatrice Alia !",
        "conversation_history": "Alia : Parle-moi de FONGIDERM.\nDélégué : Tu es vraiment sympa comme formatrice Alia !",
        "niveau": "débutant",
        "expected_behavior": "Réponse courte et légère, rebondir naturellement sur la formation sans être robotique",
    },
    {
        "id": "S5",
        "name": "Question hors périmètre M1 (pitch commercial)",
        "delegue_message": "Comment je vends FONGIDERM à un médecin ?",
        "conversation_history": "Alia : On travaille sur la connaissance produit aujourd'hui.\nDélégué : Comment je vends FONGIDERM à un médecin ?",
        "niveau": "débutant",
        "expected_behavior": "Expliquer que l'argumentation c'est le Module 2, rester sur M1, sans frustrer le délégué",
    },
    {
        "id": "S6",
        "name": "Délégué intermédiaire — question pointue",
        "delegue_message": "Quelle est la différence entre FONGIDERM et les autres antifongiques topiques ?",
        "conversation_history": "Alia : Tu connais déjà les bases, allons plus loin.\nDélégué : Quelle est la différence entre FONGIDERM et les autres antifongiques topiques ?",
        "niveau": "intermédiaire",
        "expected_behavior": "Mentionner l'avantage 1x/jour vs 2x/jour concurrents, spectre large, sans inventer des données absentes du contexte",
    },
    {
        "id": "S7",
        "name": "Délégué dit avoir tout compris",
        "delegue_message": "Ok j'ai tout compris, on peut passer à la suite ?",
        "conversation_history": "Alia : Voici les points clés de FONGIDERM.\nDélégué : Ok j'ai tout compris, on peut passer à la suite ?",
        "niveau": "débutant",
        "expected_behavior": "Vérifier la compréhension avec une petite question avant de valider, ne pas accepter passivement",
    },
]

# ══════════════════════════════════════════════════════════════════════════════
# TECHNIQUES DE PROMPT
# ══════════════════════════════════════════════════════════════════════════════

def build_prompt_zero_shot(scenario: dict) -> tuple[str, str]:
    """Technique 1 : Zero-shot — instruction seule, pas d'exemples."""
    system = f"""Tu es Alia, une formatrice pharmaceutique intelligente.
Tu formes le délégué sur le produit {PRODUCT_NAME}.
Niveau du délégué : {scenario['niveau']}.
Contexte produit :
{PRODUCT_CONTEXT}
Réponds de façon naturelle et pédagogique."""

    user = f"""Historique :
{scenario['conversation_history'] or 'Début de session.'}

Message du délégué : {scenario['delegue_message']}"""

    return system, user


def build_prompt_few_shot(scenario: dict) -> tuple[str, str]:
    """Technique 2 : Few-shot — exemples de bons échanges."""
    system = f"""Tu es Alia, une formatrice pharmaceutique intelligente.
Tu formes le délégué sur le produit {PRODUCT_NAME}.
Niveau du délégué : {scenario['niveau']}.
Contexte produit :
{PRODUCT_CONTEXT}

Voici des exemples de la façon dont tu dois répondre :

---
EXEMPLE 1 — Délégué dit quelque chose d'incomplet :
Délégué : "C'est une crème pour la peau."
Alia : "C'est un bon début ! Plus précisément, FONGIDERM cible les mycoses cutanées — pas toutes les infections de peau. La différence est importante : le bifonazole s'attaque spécifiquement aux champignons en bloquant leur membrane. Est-ce que tu sais quels types de mycoses sont concernés ?"

EXEMPLE 2 — Délégué hors-sujet :
Délégué : "Tu es sympa toi !"
Alia : "Merci ! Bon, revenons à ce qui compte — dis-moi, comment tu expliquerais l'avantage de FONGIDERM en une phrase ?"

EXEMPLE 3 — Délégué demande quelque chose hors M1 :
Délégué : "Comment je convaincs un médecin ?"
Alia : "Bonne question, et ça arrive en Module 2 ! Pour l'instant on construit les fondations — si tu ne maîtrises pas le produit, le pitch ne tiendra pas. Dis-moi : combien de fois par jour applique-t-on FONGIDERM ?"

EXEMPLE 4 — Délégué a bien répondu :
Délégué : "Le bifonazole bloque la synthèse de l'ergostérol."
Alia : "Parfait, c'est exactement ça. Et concrètement pour le patient, ça veut dire quoi ? Quel résultat il va voir et en combien de temps ?"
---

Réponds toujours : valide ce qui est juste → complète ce qui manque → pose une question de suivi."""

    user = f"""Historique :
{scenario['conversation_history'] or 'Début de session.'}

Message du délégué : {scenario['delegue_message']}"""

    return system, user


def build_prompt_role_persona(scenario: dict) -> tuple[str, str]:
    """Technique 3 : Role + Persona — identité forte d'Alia."""
    system = f"""Tu es Alia — formatrice pharmaceutique senior avec 10 ans d'expérience terrain.
Ton caractère : directe, bienveillante, jamais condescendante. Tu ne récites pas, tu formes.
Ta méthode : tu écoutes ce que le délégué dit, tu pars de là, tu construis.
Tu ne donnes jamais toutes les réponses d'un coup — tu avances par petites étapes.
Tu adaptes ton langage au niveau du délégué ({scenario['niveau']}).

Produit en formation : {PRODUCT_NAME}
Contexte scientifique disponible :
{PRODUCT_CONTEXT}

Règles absolues :
- Tu ne re-salues JAMAIS si la conversation a déjà commencé.
- Tu restes dans le Module 1 (connaissance produit) — pas de pitch, pas de simulation.
- Si le délégué dit qu'il a tout compris, tu vérifies avec une question avant de valider."""

    user = f"""Historique de la conversation :
{scenario['conversation_history'] or 'Première prise de contact.'}

Le délégué dit : {scenario['delegue_message']}

Réponds en tant qu'Alia."""

    return system, user


def build_prompt_cot(scenario: dict) -> tuple[str, str]:
    """Technique 4 : Chain-of-Thought — raisonnement structuré avant réponse."""
    system = f"""Tu es Alia, une formatrice pharmaceutique intelligente.
Produit : {PRODUCT_NAME} | Niveau délégué : {scenario['niveau']}
Contexte :
{PRODUCT_CONTEXT}

Avant de répondre, raisonne en 3 étapes (garde-les pour toi, n'affiche PAS ce raisonnement) :
1. DIAGNOSTIC : Qu'est-ce que le délégué comprend / ne comprend pas d'après son message ?
2. STRATÉGIE : Que dois-je valider, corriger, ou approfondir ? Quel est l'objectif de ma réponse ?
3. FORMAT : Quel ton adopter selon le niveau et le contexte de la conversation ?

Ensuite génère UNIQUEMENT ta réponse finale — naturelle, sans montrer les étapes.
La réponse doit : valider → corriger/compléter → avancer avec une question ou un point nouveau."""

    user = f"""Historique :
{scenario['conversation_history'] or 'Début de session.'}

Message du délégué : {scenario['delegue_message']}"""

    return system, user


PROMPT_TECHNIQUES = {
    "zero_shot":    build_prompt_zero_shot,
    "few_shot":     build_prompt_few_shot,
    "role_persona": build_prompt_role_persona,
    "cot":          build_prompt_cot,
}

# ══════════════════════════════════════════════════════════════════════════════
# APPEL LLM
# ══════════════════════════════════════════════════════════════════════════════

def call_groq(model_id: str, system: str, user: str, max_tokens: int = 500) -> tuple[str, float]:
    """Appelle Groq et retourne (réponse, latence_secondes)."""
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.4,
    }

    start = time.time()
    try:
        response = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=40)
        response.raise_for_status()
        latency = time.time() - start
        return response.json()["choices"][0]["message"]["content"].strip(), round(latency, 2)
    except requests.exceptions.Timeout:
        return "[TIMEOUT]", 40.0
    except Exception as e:
        return f"[ERREUR] {str(e)}", 0.0

# ══════════════════════════════════════════════════════════════════════════════
# JUGE LLM
# ══════════════════════════════════════════════════════════════════════════════

JUDGE_PROMPT = """Tu es un expert en évaluation de systèmes d'IA pédagogiques pour la formation pharmaceutique.
Évalue la réponse d'Alia selon ces 5 critères, chacun noté de 0 à 10 :

1. FAITHFULNESS (0-10) : La réponse est-elle fidèle aux informations du contexte produit ? Pas d'inventions ?
2. PEDAGOGICAL_QUALITY (0-10) : Est-ce que ça forme vraiment ? Alia enseigne-t-elle ou récite-t-elle ?
3. TONE_CONSISTENCY (0-10) : Alia reste-t-elle naturelle, bienveillante, non-robotique ?
4. BOUNDARY_RESPECT (0-10) : Reste-t-elle dans le périmètre Module 1 (connaissance produit, pas pitch) ?
5. FLUENCY (0-10) : La réponse est-elle fluide, naturelle, sans répétitions ni formules génériques ?

Réponds UNIQUEMENT en JSON valide, sans aucun texte avant ou après :
{
  "faithfulness": <score>,
  "pedagogical_quality": <score>,
  "tone_consistency": <score>,
  "boundary_respect": <score>,
  "fluency": <score>,
  "justification": "<1 phrase expliquant le score global>"
}"""

def judge_response(
    scenario: dict,
    alia_response: str,
    technique: str,
) -> dict:
    """Fait noter la réponse d'Alia par le juge."""

    user_prompt = f"""CONTEXTE PRODUIT :
{PRODUCT_CONTEXT}

SCÉNARIO : {scenario['name']}
COMPORTEMENT ATTENDU : {scenario['expected_behavior']}

MESSAGE DU DÉLÉGUÉ : {scenario['delegue_message']}

RÉPONSE D'ALIA (technique: {technique}) :
{alia_response}

Évalue cette réponse."""

    response, _ = call_groq(JUDGE_MODEL, JUDGE_PROMPT, user_prompt, max_tokens=300)

    try:
        # Nettoyage robuste — gère tous les formats de sortie LLM
        clean = response.strip()

        # Cas 1 : blocs ```json ... ``` ou ``` ... ```
        if "```" in clean:
            parts = clean.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                if part.startswith("{"):
                    clean = part
                    break

        # Cas 2 : texte avant/après le JSON — extraire juste le bloc {}
        start = clean.find("{")
        end   = clean.rfind("}") + 1
        if start != -1 and end > start:
            clean = clean[start:end]

        scores = json.loads(clean.strip())
        scores["total"] = round(
            (scores.get("faithfulness", 0) +
             scores.get("pedagogical_quality", 0) +
             scores.get("tone_consistency", 0) +
             scores.get("boundary_respect", 0) +
             scores.get("fluency", 0)) / 5, 2
        )
        return scores
    except Exception:
        return {
            "faithfulness": 0,
            "pedagogical_quality": 0,
            "tone_consistency": 0,
            "boundary_respect": 0,
            "fluency": 0,
            "total": 0,
            "justification": f"Erreur parsing juge : {response[:100]}",
        }

# ══════════════════════════════════════════════════════════════════════════════
# BENCHMARK PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def run_benchmark():
    if not GROQ_API_KEY:
        print("[ERREUR] GROQ_API_KEY manquant dans .env")
        return

    print("\n" + "=" * 70)
    print("   ALIA BENCHMARK — LLMs × Techniques de prompt")
    print(f"   {len(MODELS)} modèles × {len(PROMPT_TECHNIQUES)} techniques × {len(SCENARIOS)} scénarios")
    total_calls = len(MODELS) * len(PROMPT_TECHNIQUES) * len(SCENARIOS)
    judge_calls = len(MODELS) * len(PROMPT_TECHNIQUES) * len(SCENARIOS)
    print(f"   Total appels Groq : {total_calls} (génération) + {judge_calls} (juge) = {total_calls + judge_calls}")
    print(f"   Durée estimée : ~{(total_calls + judge_calls) * 3 // 60 + 1}-{(total_calls + judge_calls) * 5 // 60 + 2} minutes")
    print("=" * 70 + "\n")

    all_results = []

    # Agrégats pour le résumé final
    # structure : scores_agg[model_name][technique] = liste de totaux
    scores_agg = {m: {t: [] for t in PROMPT_TECHNIQUES} for m in MODELS}
    latency_agg = {m: {t: [] for t in PROMPT_TECHNIQUES} for m in MODELS}

    total_done = 0

    for scenario in SCENARIOS:
        print(f"\n{'─' * 70}")
        print(f"📋 Scénario {scenario['id']} : {scenario['name']}")
        print(f"   Délégué : \"{scenario['delegue_message']}\"")
        print(f"{'─' * 70}")

        for model_label, model_id in MODELS.items():
            for technique_name, build_fn in PROMPT_TECHNIQUES.items():
                total_done += 1
                progress = f"[{total_done}/{total_calls}]"
                print(f"\n  {progress} {model_label} × {technique_name} ... ", end="", flush=True)

                # 1. Construire le prompt
                system, user = build_fn(scenario)

                # 2. Générer la réponse
                alia_response, latency = call_groq(model_id, system, user)

                if "[ERREUR]" in alia_response or "[TIMEOUT]" in alia_response:
                    print(f"❌ {alia_response}")
                    continue

                # 3. Faire noter par le juge
                scores = judge_response(scenario, alia_response, technique_name)

                print(f"✓ score={scores['total']}/10 | latence={latency}s")

                # 4. Stocker le résultat
                result = {
                    "scenario_id":   scenario["id"],
                    "scenario_name": scenario["name"],
                    "model":         model_label,
                    "technique":     technique_name,
                    "latency_s":     latency,
                    "alia_response": alia_response,
                    "scores":        scores,
                }
                all_results.append(result)
                scores_agg[model_label][technique_name].append(scores["total"])
                latency_agg[model_label][technique_name].append(latency)

                # Pause pour éviter rate limit Groq (429)
                time.sleep(2)

    # ── Sauvegarder les résultats détaillés ───────────────────────────────────
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = f"benchmark_results_{timestamp}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\n\n[Benchmark] Résultats détaillés → {json_path}")

    # ── Tableau de synthèse console ───────────────────────────────────────────
    print("\n" + "=" * 70)
    print("   RÉSULTATS — Score moyen / 10 par modèle × technique")
    print("=" * 70)

    # Header
    tech_labels = list(PROMPT_TECHNIQUES.keys())
    col_w = 14
    header = f"{'Modèle':<16}" + "".join(f"{t[:col_w]:>{col_w}}" for t in tech_labels) + f"{'MOYENNE':>{col_w}}"
    print(header)
    print("─" * len(header))

    best_score = 0
    best_combo = ("", "")
    model_averages = {}

    for model_label in MODELS:
        row_scores = []
        row = f"{model_label:<16}"
        for technique in tech_labels:
            vals = scores_agg[model_label][technique]
            avg = round(sum(vals) / len(vals), 2) if vals else 0.0
            row_scores.append(avg)
            row += f"{avg:>{col_w}.2f}"
            if avg > best_score:
                best_score = avg
                best_combo = (model_label, technique)
        model_avg = round(sum(row_scores) / len(row_scores), 2) if row_scores else 0
        model_averages[model_label] = model_avg
        row += f"{model_avg:>{col_w}.2f}"
        print(row)

    print("─" * len(header))

    # Meilleur modèle global
    best_model = max(model_averages, key=model_averages.get)
    print(f"\n🏆 Meilleur modèle global    : {best_model} (score moyen : {model_averages[best_model]}/10)")
    print(f"🎯 Meilleure combinaison     : {best_combo[0]} × {best_combo[1]} (score : {best_score}/10)")

    # Tableau latence
    print("\n" + "=" * 70)
    print("   LATENCE MOYENNE (secondes)")
    print("=" * 70)
    print(header.replace("Score moyen", "Latence moy"))
    print("─" * len(header))

    for model_label in MODELS:
        row = f"{model_label:<16}"
        lats = []
        for technique in tech_labels:
            vals = latency_agg[model_label][technique]
            avg_lat = round(sum(vals) / len(vals), 2) if vals else 0.0
            lats.append(avg_lat)
            row += f"{avg_lat:>{col_w}.2f}"
        row += f"{round(sum(lats)/len(lats), 2):>{col_w}.2f}"
        print(row)

    # ── Sauvegarder le CSV de synthèse ────────────────────────────────────────
    csv_path = f"benchmark_summary_{timestamp}.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "scenario_id", "scenario_name", "model", "technique", "latency_s",
            "faithfulness", "pedagogical_quality", "tone_consistency",
            "boundary_respect", "fluency", "total", "justification"
        ])
        for r in all_results:
            s = r["scores"]
            writer.writerow([
                r["scenario_id"], r["scenario_name"], r["model"], r["technique"],
                r["latency_s"],
                s.get("faithfulness", 0), s.get("pedagogical_quality", 0),
                s.get("tone_consistency", 0), s.get("boundary_respect", 0),
                s.get("fluency", 0), s.get("total", 0),
                s.get("justification", ""),
            ])
    print(f"\n[Benchmark] Tableau CSV → {csv_path}")
    print("\n✅ Benchmark terminé !\n")


if __name__ == "__main__":
    run_benchmark()