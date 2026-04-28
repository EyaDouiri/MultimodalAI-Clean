"""
avatar_server.py — Alia Web Server
Sert l'interface HTML, expose les endpoints pour l'agent et le chat.
Lance automatiquement l'agent en background.

Usage : python avatar_server.py
Ouvre : http://localhost:9000
"""

import os
import sys
import json
import time
import threading
import glob
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# ── État global avatar ────────────────────────────────────────────────────────
_avatar_state = {"state": "idle", "text": "", "persona": "ALIA", "sim_mode": ""}
_avatar_lock  = threading.Lock()

# ── Agent (initialisé en background) ─────────────────────────────────────────
_agent        = None
_agent_ready  = False
_agent_error  = None

# ── Répertoire base ───────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent

# ════════════════════════════════════════════════════════════════════════════
# INIT AGENT
# ════════════════════════════════════════════════════════════════════════════

def _init_agent():
    global _agent, _agent_ready, _agent_error
    try:
        # Ajouter le dossier courant au path pour importer agent.py
        if str(BASE_DIR) not in sys.path:
            sys.path.insert(0, str(BASE_DIR))

        from agent import AliaAgent
        print("[Server] Chargement de l'agent Alia...")
        # mode_voix=False : pas de thread micro/barge-in côté serveur
        # Le micro est géré par le navigateur (dashboard.html → /api/transcribe)
        _agent = AliaAgent(mode_voix=False)
        _agent.web_mode = True   # Désactive TTS dans _output() — géré par _speak_response()
        _agent_ready = True
        print("[Server] ✅ Agent Alia prêt")

        # Message d'ouverture
        opening = _agent.start_session()
        _agent._add("alia", opening)
        _push_message("alia", opening, _agent._get_persona_label())
        _speak_response(opening, "alia")

    except Exception as e:
        _agent_error = str(e)
        print(f"[Server] ❌ Erreur agent : {e}")
        import traceback; traceback.print_exc()


# ════════════════════════════════════════════════════════════════════════════
# MESSAGES BUFFER (pour le frontend)
# ════════════════════════════════════════════════════════════════════════════

_messages = []   # [{role, content, persona, ts}]
_msg_lock = threading.Lock()

def _push_message(role: str, content: str, persona: str = "Alia"):
    with _msg_lock:
        _messages.append({
            "role":    role,
            "content": content,
            "persona": persona,
            "ts":      time.time()
        })
        # Garder max 200 messages
        if len(_messages) > 200:
            _messages.pop(0)


def _persona_for(role: str) -> str:
    if role == "doctor":     return "DR. KARIM"
    if role == "pharmacien": return "MME SONIA"
    return "ALIA"

def _speak_response(text: str, voice_role: str = "alia"):
    """TTS unique avec synchronisation lèvres + traduction multilingue."""
    def _do():
        if not _agent:
            return
        try:
            from agent import clean_for_tts
            clean_text = clean_for_tts(text)
        except Exception:
            import re as _rx
            t2 = _rx.sub(r'\*\*([^*]+)\*\*', r'\1', text)
            t2 = _rx.sub(r'\*([^*]+)\*', r'\1', t2)
            t2 = _rx.sub(r'#{1,6}\s+', '', t2)
            clean_text = t2.replace('*','').replace('`','').strip()

        if not clean_text:
            return

        # ── Traduction : si le délégué parle une autre langue, Alia répond dans cette langue
        lang = "fr"
        if hasattr(_agent, 'voice') and _agent.voice and hasattr(_agent.voice, 'delegue_lang'):
            lang = _agent.voice.delegue_lang or "fr"
        if lang != "fr":
            try:
                from deep_translator import GoogleTranslator
                clean_text = GoogleTranslator(source="fr", target=lang).translate(clean_text)
                print(f"[TTS] Traduit fr→{lang}: {clean_text[:60]}...")
            except Exception as e:
                print(f"[TTS] Traduction échouée ({e}) — lecture en FR")

        persona = _persona_for(voice_role)

        # ① Lèvres ouvertes AVANT le son ─────────────────────────────
        with _avatar_lock:
            _avatar_state.update({"state": "speaking", "text": clean_text[:120],
                                   "persona": persona, "ts": time.time()})

        try:
            _agent._speak_sim_only(clean_text, blocking=True, voice_role=voice_role)
        finally:
            # ② Lèvres fermées après fin réelle ──────────────────────
            with _avatar_lock:
                _avatar_state.update({"state": "idle", "text": "", "persona": "ALIA",
                                       "ts": time.time()})

    threading.Thread(target=_do, daemon=True).start()


# ════════════════════════════════════════════════════════════════════════════
# ROUTES — FICHIERS STATIQUES
# ════════════════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    """Sert l'interface principale."""
    p = BASE_DIR / "dashboard.html"
    if p.exists():
        return send_file(str(p))
    return "<h2>dashboard.html introuvable — mets-le dans le même dossier.</h2>", 404


@app.route("/alia_avatar.html")
def avatar_page():
    p = BASE_DIR / "alia_avatar.html"
    if p.exists():
        return send_file(str(p))
    return "alia_avatar.html introuvable", 404


@app.route("/<path:filename>")
def static_files(filename):
    """Sert les fichiers statiques (GLB, assets...)."""
    p = BASE_DIR / filename
    if p.exists() and p.is_file():
        return send_file(str(p))
    return f"{filename} introuvable", 404


# ════════════════════════════════════════════════════════════════════════════
# API — AVATAR STATE (utilisé par agent.py pour piloter l'avatar)
# ════════════════════════════════════════════════════════════════════════════

@app.route("/api/avatar/state", methods=["POST"])
def set_avatar_state():
    data = request.get_json(force=True, silent=True) or {}
    with _avatar_lock:
        _avatar_state.update({
            "state":    data.get("state", "idle"),
            "text":     data.get("text", ""),
            "persona":  data.get("persona", "ALIA"),
            "sim_mode": data.get("sim_mode", ""),
            "ts":       time.time(),
        })
    return jsonify({"ok": True})


@app.route("/api/avatar/last", methods=["GET"])
def get_avatar_state():
    with _avatar_lock:
        return jsonify(dict(_avatar_state))


# ════════════════════════════════════════════════════════════════════════════
# API — CHAT
# ════════════════════════════════════════════════════════════════════════════

@app.route("/api/status", methods=["GET"])
def api_status():
    if not _agent_ready:
        err = _agent_error or "Chargement en cours..."
        return jsonify({"ready": False, "error": err})
    return jsonify({
        "ready":     True,
        "delegue":   _agent.profile.name,
        "niveau":    _agent.profile.niveau,
        "mode":      _agent.mode,
        "product":   _agent.current_product,
        "sim":       _agent.simulation_active,
        "exam":      _agent.exam_mode,
        "mode_voix": _agent.mode_voix,
    })


@app.route("/api/messages", methods=["GET"])
def api_messages():
    since = float(request.args.get("since", 0))
    with _msg_lock:
        msgs = [m for m in _messages if m["ts"] > since]
    return jsonify(msgs)


@app.route("/api/chat", methods=["POST"])
def api_chat():
    if not _agent_ready:
        return jsonify({"error": "Agent non prêt"}), 503

    data    = request.get_json(force=True, silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"error": "Message vide"}), 400

    _push_message("delegue", message, _agent.profile.name)

    # Commandes
    COMMANDS = {
        "eval":     ["eval", "évalue", "évaluation"],
        "next":     ["next", "suivant", "avancer"],
        "sim":      ["sim", "simulation", "simuler"],
        "stop_sim": ["stop_sim", "stop sim", "arrêter simulation", "fin simulation"],
        "exam":     ["exam", "examen", "test final"],
        "save":     ["save", "sauvegarder"],
        "status":   ["status", "statut"],
        "history":  ["history", "historique"],
    }
    msg_lower = message.lower().strip()
    cmd = None
    for c, variants in COMMANDS.items():
        if any(v in msg_lower for v in variants):
            cmd = c; break

    try:
        # Interrompre TTS en cours avant toute action
        if _agent._speak_sim_only and hasattr(_agent, '_tts_stop'):
            pass  # sera géré par flag
        # Forcer l'arrêt du TTS edge-tts si en cours via pygame
        try:
            import pygame as _pg
            if _pg.mixer.get_init() and _pg.mixer.music.get_busy():
                _pg.mixer.music.stop()
        except Exception:
            pass

        if cmd == "eval":
            response = _agent.trigger_eval()
        elif cmd == "next":
            response = _agent.trigger_next()
        elif cmd == "sim":
            # Arrêter Alia immédiatement
            if _agent.voice:
                _agent.voice.interrupt()
            time.sleep(0.1)
            # Lancer simulation en thread (elle est bloquante)
            interlocuteur = data.get("interlocuteur", "medecin")  # Par défaut médecin
            if interlocuteur not in ["medecin", "pharmacien"]:
                interlocuteur = "medecin"
            def _start_sim():
                _agent.start_simulation(exam_mode=False, interlocuteur=interlocuteur)
            threading.Thread(target=_start_sim, daemon=True).start()
            role_name = "Dr. Karim" if interlocuteur == "medecin" else "Mme Sonia"
            response = f"Simulation démarrée avec {role_name}. Parle-lui !"
        elif cmd == "stop_sim":
            # Couper le TTS immédiatement
            try:
                import pygame as _pg2
                if _pg2.mixer.get_init() and _pg2.mixer.music.get_busy():
                    _pg2.mixer.music.stop()
            except Exception:
                pass
            with _avatar_lock:
                _avatar_state.update({"state": "idle", "text": "", "persona": "ALIA", "ts": time.time()})
            response = _agent.stop_simulation()
            if not response or response == "[Simulation] Aucune simulation active.":
                response = "Aucune simulation active."
            elif "Terminée" in response or "terminée" in response:
                response = "Simulation terminée. Bilan envoyé."
        elif cmd == "exam":
            # Arrêter Alia immédiatement
            if _agent.voice:
                _agent.voice.interrupt()
            time.sleep(0.1)
            interlocuteur = data.get("interlocuteur", "medecin")  # Par défaut médecin
            if interlocuteur not in ["medecin", "pharmacien"]:
                interlocuteur = "medecin"
            def _start_exam():
                _agent.start_simulation(exam_mode=True, interlocuteur=interlocuteur)
            threading.Thread(target=_start_exam, daemon=True).start()
            response = "Mode examen démarré. Alia ne te corrigera pas — bonne chance !"
        elif cmd == "save":
            _agent.save_and_close()
            response = "Session sauvegardée ✓"
        else:
            response = _agent.respond(message)

        # Détecter le persona pour la voix
        persona_label = _agent._get_persona_label()
        voice_role    = _agent._get_voice_role()

        if "[Alia - hors rôle]" in response:
            response      = response.replace("[Alia - hors rôle]", "").strip()
            persona_label = "Alia"
            voice_role    = "alia"

        _push_message("alia", response, persona_label)

        # TTS async
        _speak_response(response, voice_role)

        return jsonify({
            "response": response,
            "persona":  persona_label,
            "mode":     _agent.mode,
            "sim":      _agent.simulation_active,
        })

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ════════════════════════════════════════════════════════════════════════════
# API — VOICE MODE
# ════════════════════════════════════════════════════════════════════════════

@app.route("/api/voice/toggle", methods=["POST"])
def api_voice_toggle():
    if not _agent_ready:
        return jsonify({"error": "Agent non prêt"}), 503
    data    = request.get_json(force=True, silent=True) or {}
    enabled = data.get("enabled", False)
    msg     = _agent.set_voice_mode(enabled)
    return jsonify({"ok": True, "message": msg, "mode_voix": _agent.mode_voix})


# ════════════════════════════════════════════════════════════════════════════
# API — HISTORIQUE SESSIONS
# ════════════════════════════════════════════════════════════════════════════

@app.route("/api/history", methods=["GET"])
def api_history():
    sessions_dir = BASE_DIR / "sessions"
    if not sessions_dir.exists():
        return jsonify([])

    sessions = []
    for f in sorted(sessions_dir.glob("*.json"), reverse=True)[:20]:
        try:
            with open(f, encoding="utf-8") as fh:
                data = json.load(fh)
            sessions.append({
                "file":    f.name,
                "date":    data.get("date", f.stem),
                "product": data.get("product_name", "?"),
                "score":   data.get("score", 0),
                "turns":   len(data.get("conversation", [])),
            })
        except Exception:
            pass
    return jsonify(sessions)


# ════════════════════════════════════════════════════════════════════════════
# API — STT (Speech-to-Text) via Whisper
# ════════════════════════════════════════════════════════════════════════════

@app.route("/api/transcribe", methods=["POST"])
def api_transcribe():
    """Reçoit audio du navigateur (webm/wav), transcrit via Whisper."""
    print("[API] POST /api/transcribe")

    if not _agent_ready:
        return jsonify({"error": "Agent not ready"}), 503

    # Initialiser Whisper à la volée si nécessaire (même sans mode_voix activé)
    whisper_model = None
    if _agent.voice and _agent.voice._whisper:
        whisper_model = _agent.voice._whisper
    else:
        try:
            import whisper as _whisper
            whisper_model = _whisper.load_model("small")
            # Mettre en cache sur l'agent pour la prochaine fois
            if not _agent.voice:
                from voice import VoiceEngine
                _agent.voice = VoiceEngine.__new__(VoiceEngine)
                _agent.voice._whisper = whisper_model
                _agent.voice.delegue_lang = None  # Will be detected from audio
                _agent.voice.is_speaking = False
                # Ajouter les méthodes de traduction nécessaires
                _agent.voice._to_french = lambda text, lang: text if lang == "fr" else text
                _agent.voice._from_french = lambda text, lang: text
            else:
                _agent.voice._whisper = whisper_model
        except Exception as e:
            print(f"[API] Whisper unavailable: {e}")
            return jsonify({"error": "Whisper non disponible"}), 503

    if not request.files or "audio" not in request.files:
        print("[API] No audio file in request")
        return jsonify({"error": "No audio file"}), 400

    audio_file = request.files["audio"]

    raw_path = None
    wav_path = None
    try:
        import tempfile

        # 1. Sauvegarder le fichier envoyé par le navigateur
        fname   = audio_file.filename or "audio.wav"
        is_webm = fname.endswith(".webm") or fname.endswith(".weba")
        
        with tempfile.NamedTemporaryFile(suffix=".webm" if is_webm else ".wav", delete=False) as tmp:
            audio_file.save(tmp.name)
            raw_path = tmp.name

        file_size = os.path.getsize(raw_path)
        print(f"[API] Reçu {fname} — {file_size} octets")

        if file_size < 800:
            return jsonify({"error": "Audio trop court, parle plus longtemps"}), 400

        # 2. Décoder le WAV avec numpy — SANS ffmpeg
        wav_path = raw_path  # pour le finally
        audio_np = None
        try:
            import wave, io, numpy as np
            with wave.open(raw_path, 'rb') as wf:
                n_frames  = wf.getnframes()
                framerate = wf.getframerate()
                sampwidth = wf.getsampwidth()
                raw_pcm   = wf.readframes(n_frames)
            dtype = np.int16 if sampwidth == 2 else np.int8
            audio_np = np.frombuffer(raw_pcm, dtype=dtype).astype(np.float32) / (32768.0 if sampwidth == 2 else 128.0)
            # Resample si pas 16kHz
            if framerate != 16000 and framerate > 0:
                ratio   = 16000 / framerate
                new_len = int(len(audio_np) * ratio)
                indices = np.linspace(0, len(audio_np) - 1, new_len)
                audio_np = np.interp(indices, np.arange(len(audio_np)), audio_np).astype(np.float32)
            print(f"[API] WAV décodé: {len(audio_np)} samples @ 16kHz (sr original: {framerate}Hz)")
        except Exception as decode_err:
            print(f"[API] Décodage WAV échoué ({decode_err}) — Whisper essaie le fichier brut")

        # 3. Transcription Whisper — array numpy si dispo, sinon fichier (AUTO-DETECT LANGUAGE)
        if audio_np is not None:
            print("[API] Transcription Whisper (array numpy — sans ffmpeg)...")
            result = whisper_model.transcribe(audio_np, fp16=False)  # Auto-detect language
        else:
            print(f"[API] Transcription Whisper depuis fichier {wav_path}...")
            result = whisper_model.transcribe(wav_path, fp16=False)  # Auto-detect language
        text   = result["text"].strip()
        lang   = result.get("language", "fr")
        print(f"[API] Transcription : '{text}' ({lang})")

        if not text:
            return jsonify({"error": "Aucun texte détecté", "ok": False}), 400

        # PERSIST detected language for voice response
        if hasattr(_agent, 'voice') and _agent.voice:
            _agent.voice.delegue_lang = lang
            print(f"[API] ✓ Langue détectée persisted: {lang}")

        # 3. Traduction FR si besoin
        text_fr = text
        if hasattr(_agent, 'voice') and _agent.voice and lang != "fr":
            text_fr = _agent.voice._to_french(text, lang)

        return jsonify({"text": text_fr, "lang": lang, "ok": True})

    except Exception as e:
        print(f"[API] Erreur transcription : {e}")
        import traceback; traceback.print_exc()
        return jsonify({"error": str(e), "ok": False}), 400

    finally:
        if raw_path and os.path.exists(raw_path):
            try: os.remove(raw_path)
            except: pass
        if wav_path and wav_path != raw_path and os.path.exists(wav_path):
            try: os.remove(wav_path)
            except: pass


# ════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import webbrowser

    print("=" * 60)
    print("  ALIA — Serveur Web")
    print("=" * 60)
    print(f"  Répertoire : {BASE_DIR}")
    print(f"  URL        : http://localhost:9000")
    print("=" * 60)

    # Lancer l'agent en background
    threading.Thread(target=_init_agent, daemon=True).start()

    # Ouvrir le navigateur après 1.5s
    def _open():
        time.sleep(1.5)
        webbrowser.open("http://localhost:9000")
    threading.Thread(target=_open, daemon=True).start()

    app.run(host="0.0.0.0", port=9000, debug=False, threaded=True)