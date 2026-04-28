#!/usr/bin/env python3
import requests

try:
    r = requests.get('http://localhost:11434/api/tags', timeout=5)
    models = r.json()
    print("✓ Ollama CONNECTÉ")
    model_list = [m["name"] for m in models.get("models", [])]
    print(f"✓ Modèles disponibles: {model_list}")
    
    # Vérifier les modèles attendus
    has_llama = any('llama' in m.lower() for m in model_list)
    print(f"✓ Llama disponible: {has_llama}")
    
except Exception as e:
    print(f"❌ Erreur connexion Ollama: {e}")
