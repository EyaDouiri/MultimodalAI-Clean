"""
session.py - Alia Agent
Charge la session active et le profil du délégué connecté
depuis les fichiers CSV (provisoires, sera remplacé par Django API)
"""

import pandas as pd
import json
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class DelegueProfile:
    delegue_id: int
    name: str
    niveau: str                    # debutant | intermediaire | avance
    current_module: int
    assigned_products: List[str]
    product_scores: dict           # {product_name: score}
    score_module_1: int = 0

    def get_current_product(self) -> Optional[str]:
        """Retourne le produit en cours (premier avec score < 100)"""
        for product in self.assigned_products:
            score = self.product_scores.get(product, 0)
            if score < 100:
                return product
        return None

    def get_weak_products(self) -> List[str]:
        """Produits avec score < 50 = points faibles à renforcer"""
        return [p for p in self.assigned_products if self.product_scores.get(p, 0) < 50]

    def summary(self) -> str:
        lines = [
            f"Délégué    : {self.name} (ID: {self.delegue_id})",
            f"Niveau     : {self.niveau}",
            f"Module     : {self.current_module}",
            f"Produits   : {', '.join(self.assigned_products)}",
            f"Scores     : {self.product_scores}",
        ]
        current = self.get_current_product()
        if current:
            lines.append(f"En cours   : {current}")
        weak = self.get_weak_products()
        if weak:
            lines.append(f"Points faibles : {', '.join(weak)}")
        return "\n".join(lines)


def load_session(
    session_csv: str = "C:/Users/eyaen/Desktop/PI/data/raw/delegue_sessions.csv",
    assignments_csv: str = "C:/Users/eyaen/Desktop/PI/data/raw/product_assignments.csv"
) -> DelegueProfile:
    """
    Charge la session active et construit le profil du délégué connecté.
    Pour l'instant : prend le premier enregistrement (1 délégué actif).
    Plus tard : filtrer par token de session Django.
    """
    # --- Session ---
    df_session = pd.read_csv(session_csv)
    session = df_session.iloc[0]  # délégué connecté

    delegue_id   = int(session["delegue_id"])
    name         = session["delegue_name"]
    niveau       = session.get("niveau", "debutant")
    current_module = int(session.get("current_module", 1))
    score_m1     = int(session.get("score_module_1", 0))

    # --- Assignations produits ---
    df_assign = pd.read_csv(assignments_csv)
    row = df_assign[df_assign["delegue_id"] == delegue_id].iloc[0]

    products_raw = row["assigned_products"].split("|")
    scores_raw   = str(row["product_scores"]).split("|")

    assigned_products = [p.strip() for p in products_raw]
    product_scores = {}
    for i, product in enumerate(assigned_products):
        try:
            product_scores[product] = int(scores_raw[i])
        except (IndexError, ValueError):
            product_scores[product] = 0

    return DelegueProfile(
        delegue_id=delegue_id,
        name=name,
        niveau=niveau,
        current_module=current_module,
        assigned_products=assigned_products,
        product_scores=product_scores,
        score_module_1=score_m1,
    )


def load_product_data(
    product_name: str,
    medicaments_json: str = "medicaments_clean.json"
) -> Optional[dict]:
    """Charge les données complètes d'un produit depuis le JSON."""
    with open(medicaments_json, "r", encoding="utf-8") as f:
        products = json.load(f)

    for product in products:
        if product.get("nom", "").strip() == product_name.strip():
            return product
    return None


# --- Test rapide ---
if __name__ == "__main__":
    profile = load_session(
        session_csv="delegue_sessions.csv",
        assignments_csv="product_assignments.csv"
    )
    print("=" * 50)
    print("PROFIL DÉLÉGUÉ CHARGÉ")
    print("=" * 50)
    print(profile.summary())

    print("\n--- Test chargement produit ---")
    current = profile.get_current_product()
    if current:
        data = load_product_data(current)
        if data:
            print(f"Produit chargé : {data['nom']}")
            print(f"Classe         : {data.get('classe_therapeutique', 'N/A')}")
            print(f"Indications    : {data.get('Indications', [])}")
