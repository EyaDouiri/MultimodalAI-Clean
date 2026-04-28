"""
SMART CHUNKING V4 - STRUCTURE-BASED (2 chunks par produit)
Approche: 
  - Chunk 1: Indications cliniques + Keywords pharma
  - Chunk 2: Composition + Description mécanisme
Source: medicaments_clean_enrichis_pharmacologie.json (SANS boilerplate)
"""

import json
import re

print("=" * 80)
print("🔨 SMART CHUNKING V4 - STRUCTURE-BASED (2 chunks/produit)")
print("=" * 80)

# Charger les données enrichies
print("\n📂 Chargement medicaments_clean_enrichis_pharmacologie.json...")
with open("medicaments_clean_enrichis_pharmacologie.json", "r", encoding="utf-8") as f:
    products = json.load(f)
print(f"✓ {len(products)} produits chargés")

# Patterns de boilerplate à supprimer
BOILERPLATE_PATTERNS = [
    r"Préparation topique dermatologique destinée usage cutané.*?selon le type de soin\.",
    r"Préparation pharmaceutique sirupeuse destinée.*?post-ouverture\.",
    r"Complément nutritionnel.*?variation métabolique genetic.*?\.",
    r"Agents actifs combinés agissent via.*?selon formulation\.",
    r"Tolérance excellente.*?effets indésirables rares et mineurs\.",
    r"Combine action antitussive.*?et possibles agents mucolytiques\.",
]

def clean_description(text):
    """Supprime boilerplate et nettoie les caractères"""
    if not isinstance(text, str):
        return ""
    # Supprimer boilerplate patterns
    for pattern in BOILERPLATE_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.DOTALL)
    # Nettoyer les espaces multiples et les retours à ligne excessifs
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

chunks = []
chunk_id = 0

for product_idx, product in enumerate(products):
    if not product or "nom" not in product:
        continue
    
    nom = product.get("nom", "Unknown")
    classe = product.get("classe_therapeutique", "N/A")
    keywords = product.get("mots_cles_pharmacologiques", [])
    keywords_str = " ".join(keywords) if keywords else ""
    
    # ===== CHUNK 1: Indications + Keywords (Profil clinique) =====
    indications = " ".join(product.get("Indications", []))
    contre_indications = " ".join(product.get("contre_indications", []))
    effets_secondaires_rares = " ".join(product.get("effets_secondaires_rares", []))
    
    chunk_1_text = f"""PRODUIT: {nom}
CLASSE: {classe}

INDICATIONS CLINIQUES:
{indications}

CONTRE-INDICATIONS:
{contre_indications}

EFFETS SECONDAIRES RARES:
{effets_secondaires_rares}

MOTS-CLÉS PHARMACOLOGIQUES:
{keywords_str}"""
    
    if len(chunk_1_text.strip()) > 50:
        chunks.append({
            "id": chunk_id,
            "product_id": product_idx,
            "product_name": nom,
            "chunk_type": "clinical_profile",
            "classe": classe,
            "text": chunk_1_text.strip()
        })
        chunk_id += 1
    
    # ===== CHUNK 2: Composition + Description (Profil chimique) =====
    composition = " ".join(product.get("Composition", []))
    description_raw = product.get("description_pharmacologique", "")
    
    if isinstance(description_raw, list):
        description_raw = " ".join(description_raw)
    
    description_clean = clean_description(description_raw)
    
    mecanisme = " ".join(product.get("mecanisme_action_resume", []))
    precautions = " ".join(product.get("precautions", []))
    
    chunk_2_text = f"""PRODUIT: {nom}

COMPOSITION:
{composition}

MÉCANISME D'ACTION:
{mecanisme}

PRÉCAUTIONS:
{precautions}

DESCRIPTION PHARMACOLOGIQUE:
{description_clean}"""
    
    if len(chunk_2_text.strip()) > 50:
        chunks.append({
            "id": chunk_id,
            "product_id": product_idx,
            "product_name": nom,
            "chunk_type": "pharmacology_profile",
            "classe": classe,
            "text": chunk_2_text.strip()
        })
        chunk_id += 1

print(f"\n✅ Chunking structure-based complet:")
print(f"   - {len(products)} produits en entrée")
print(f"   - {len(chunks)} chunks générés ({len(chunks) // len([p for p in products if p and 'nom' in p])} avg/produit)")
print(f"   - Types: {len([c for c in chunks if c['chunk_type'] == 'clinical_profile'])} clinical + {len([c for c in chunks if c['chunk_type'] == 'pharmacology_profile'])} pharmacology")

# Exemples
if len(chunks) >= 2:
    print(f"\n📌 Exemple (Produit: {chunks[0]['product_name']}):")
    print(f"   Chunk 1 type: {chunks[0]['chunk_type']}")
    print(f"   Chunk 1 size: {len(chunks[0]['text'])} chars")
    if len(chunks) > 1:
        print(f"   Chunk 2 type: {chunks[1]['chunk_type']}")
        print(f"   Chunk 2 size: {len(chunks[1]['text'])} chars")

# Sauvegarder
output_file = "chunks_structure_based_v4.json"
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(chunks, f, ensure_ascii=False, indent=2)

print(f"\n💾 Sauvegardé: {output_file}")
print("\n✅ CHUNKING V4 COMPLET!")
print(f"\n📊 Statistiques:")
print(f"   Chunks total: {len(chunks)}")
print(f"   Chunks/produit: ~{len(chunks) // len([p for p in products if p and 'nom' in p])}")
print(f"   Taille moyenne chunk: {sum(len(c['text']) for c in chunks) // len(chunks)} caractères")