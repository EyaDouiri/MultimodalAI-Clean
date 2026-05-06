#!/usr/bin/env python
"""
load_medicaments.py — Charge les médicaments depuis medicaments_clean.json vers SQLite
Usage: python load_medicaments.py
"""

import os
import sys
import json
import django
from pathlib import Path

# ── Setup Django ──────────────────────────────────────────────────────────────
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alia_backend.settings')
django.setup()

from api.models import Medicament

JSON_FILE = Path(__file__).parent.parent / 'data' / 'raw' / 'medicaments_clean.json'

def load_medicaments():
    """Charge les médicaments depuis le JSON."""
    if not JSON_FILE.exists():
        print(f"❌ Fichier non trouvé : {JSON_FILE}")
        return

    with open(JSON_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if not isinstance(data, list):
        print("❌ Format JSON invalide — doit être un array")
        return

    created_count = 0
    updated_count = 0
    error_count = 0

    for item in data:
        try:
            nom = item.get('nom', '').strip()
            if not nom:
                print(f"⚠️  Skipped: nom vide")
                error_count += 1
                continue

            # ── Mapper les champs ──
            forme = item.get('Forme / Présentation', '').strip()
            classe_therapeutique = item.get('classe_therapeutique', '').strip()
            
            # Indications peut être list ou string
            indications = item.get('Indications', [])
            if isinstance(indications, list):
                indications = ' | '.join(indications)
            indications = str(indications).strip()

            # Contre-indications
            contre_indications = item.get('contre_indications', [])
            if isinstance(contre_indications, list):
                contre_indications = ' | '.join(contre_indications)
            contre_indications = str(contre_indications).strip()

            # Mécanisme d'action
            mecanisme_action = item.get('mecanisme_action_resume', [])
            if isinstance(mecanisme_action, list):
                mecanisme_action = ' | '.join(mecanisme_action)
            mecanisme_action = str(mecanisme_action).strip()

            # Effets secondaires
            effets_communs = item.get('effets_secondaires_communs', [])
            if isinstance(effets_communs, list):
                effets_communs = ' | '.join(effets_communs)
            effets_indesirables = str(effets_communs).strip()

            # Créer ou updater
            med, created = Medicament.objects.update_or_create(
                nom=nom,
                defaults={
                    'forme': forme,
                    'classe_therapeutique': classe_therapeutique,
                    'indications': indications,
                    'contre_indications': contre_indications,
                    'mecanisme_action': mecanisme_action,
                    'effets_indesirables': effets_indesirables,
                }
            )

            if created:
                print(f"✅ Créé: {nom}")
                created_count += 1
            else:
                print(f"🔄 Mis à jour: {nom}")
                updated_count += 1

        except Exception as e:
            print(f"❌ Erreur pour {item.get('nom', 'UNKNOWN')}: {e}")
            error_count += 1

    print(f"\n{'='*60}")
    print(f"✅ Créés: {created_count}")
    print(f"🔄 Mis à jour: {updated_count}")
    print(f"❌ Erreurs: {error_count}")
    print(f"{'='*60}")


if __name__ == '__main__':
    load_medicaments()
