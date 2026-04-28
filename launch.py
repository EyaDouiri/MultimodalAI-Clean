"""
launch.py — Lance le serveur Alia et ouvre le navigateur automatiquement.
Usage : python launch.py
"""
import subprocess, sys, time, webbrowser, threading
from pathlib import Path

def open_browser():
    time.sleep(2.5)
    webbrowser.open("http://localhost:9000")

print("=" * 50)
print("  ALIA — Lancement interface web")
print("=" * 50)
print()
print("  1. Installation dépendances...")

# Install flask if needed
subprocess.run([sys.executable, "-m", "pip", "install", "flask", "flask-cors", "-q"])
print("  2. Démarrage serveur sur http://localhost:9000")
print("  (le navigateur s'ouvre dans 2.5 secondes)")
print()

threading.Thread(target=open_browser, daemon=True).start()

# Lance le serveur comme un processus séparé
server_process = subprocess.Popen(
    [sys.executable, "avatar_server.py"],
    cwd=str(Path(__file__).parent)
)

# Garder le processus actif
try:
    server_process.wait()
except KeyboardInterrupt:
    server_process.terminate()
    server_process.wait(timeout=5)