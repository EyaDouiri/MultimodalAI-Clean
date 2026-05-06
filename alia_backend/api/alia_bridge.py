"""
alia_bridge.py
==============
Pont entre Django et agent.py : démarre l'agent en mémoire par user_id,
appelle start_simulation / respond / commandes sans middleware de session.
"""
import logging
import sys
import threading
from typing import Any, Dict, Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

_agents: dict = {}
_locks: dict = {}
_global_lock = threading.Lock()

FLASK_BASE = getattr(
    settings,
    "ALIA_FLASK_URL",
    getattr(settings, "ALIA_AVATAR_SERVER", "http://127.0.0.1:9000"),
)


def _ensure_path():
    path = getattr(settings, "ALIA_PROJECT_PATH", "") or ""
    if path and path not in sys.path:
        sys.path.insert(0, path)


def _flask_available(timeout: float = 0.8) -> bool:
    base = str(FLASK_BASE).rstrip("/")
    try:
        r = requests.get(f"{base}/api/status", timeout=timeout)
        return r.status_code == 200
    except requests.RequestException:
        return False


def get_agent(user_id: int, mode_voix: bool = False):
    with _global_lock:
        if user_id not in _locks:
            _locks[user_id] = threading.Lock()

    with _locks[user_id]:
        if user_id not in _agents:
            _ensure_path()
            from agent import AliaAgent

            agent = AliaAgent(mode_voix=mode_voix)
            _agents[user_id] = agent
        return _agents[user_id]


def release_agent(user_id: int):
    with _global_lock:
        if user_id in _agents:
            try:
                _agents[user_id].save_and_close()
            except Exception:
                logger.exception("release_agent save_and_close")
            del _agents[user_id]
        if user_id in _locks:
            del _locks[user_id]


def agent_exists(user_id: int) -> bool:
    return user_id in _agents


def get_agent_status() -> Dict[str, Any]:
    if _flask_available():
        return {"ok": True, "backend": "flask", "detail": FLASK_BASE}
    try:
        _ensure_path()
        from agent import AliaAgent  # noqa: F401

        return {"ok": True, "backend": "local", "detail": "agent importable"}
    except Exception as e:
        return {"ok": False, "backend": "none", "error": str(e)}


def start_simulation(
    user_id: int, mode: str = "training", interlocuteur: str = "medecin"
) -> Dict[str, Any]:
    if _flask_available():
        try:
            base = str(FLASK_BASE).rstrip("/")
            r = requests.post(
                f"{base}/api/chat",
                json={
                    "message": "sim" if mode != "exam" else "exam",
                    "user_id": user_id,
                    "interlocuteur": interlocuteur,
                },
                timeout=120,
            )
            if r.ok:
                data = r.json() if r.content else {}
                return {
                    "ok": True,
                    "backend": "flask",
                    "intro": data.get("response", ""),
                }
        except requests.RequestException as e:
            logger.warning("Flask start failed, fallback local: %s", e)

    try:
        agent = get_agent(user_id, mode_voix=False)
        agent.web_mode = True
        iloc = (interlocuteur or "medecin").lower()
        if iloc not in ("medecin", "pharmacien"):
            iloc = "medecin"
        exam = str(mode).lower() == "exam"

        if agent.simulation_active:
            return {"ok": True, "backend": "local", "note": "simulation_deja_active"}

        agent.start_simulation(
            camera_index=0, exam_mode=exam, interlocuteur=iloc
        )
        intro = ""
        for turn in reversed(agent.conversation_history):
            if turn.get("role") == "alia":
                intro = turn.get("content", "") or ""
                break
        return {"ok": True, "backend": "local", "intro": intro}
    except Exception as e:
        logger.exception("start_simulation local")
        return {"ok": False, "error": str(e)}


def send_message(
    message: str, interlocuteur: str = "medecin", user_id: int = 0
) -> Dict[str, Any]:
    _ = interlocuteur  # persona déjà fixée par start_simulation (M3)

    if _flask_available():
        try:
            base = str(FLASK_BASE).rstrip("/")
            r = requests.post(
                f"{base}/api/chat",
                json={"message": message, "user_id": user_id},
                timeout=120,
            )
            if r.ok:
                data = r.json() if r.content else {}
                return {
                    "response": data.get("response", ""),
                    "persona": data.get("persona", "Alia"),
                    "mode": data.get("mode", "training"),
                }
        except requests.RequestException as e:
            logger.warning("Flask chat failed, fallback local: %s", e)

    try:
        _ensure_path()
        from agent import _is_command

        agent = get_agent(user_id, mode_voix=False)
        agent.web_mode = True
        cmd: Optional[str] = _is_command(message)

        if cmd == "quit":
            release_agent(user_id)
            return {"response": "Session terminée.", "persona": "Alia"}

        if cmd == "eval":
            text = agent.trigger_eval()
            return {"response": text, "persona": "Alia"}

        if cmd == "next":
            text = agent.trigger_next()
            return {"response": text, "persona": "Alia"}

        if cmd == "sim":
            agent.start_simulation(camera_index=0, exam_mode=False, interlocuteur="medecin")
            text = ""
            for turn in reversed(agent.conversation_history):
                if turn.get("role") == "alia":
                    text = turn.get("content", "") or ""
                    break
            return {"response": text, "persona": "Alia"}

        if cmd == "exam":
            agent.start_simulation(camera_index=0, exam_mode=True, interlocuteur="medecin")
            text = ""
            for turn in reversed(agent.conversation_history):
                if turn.get("role") == "alia":
                    text = turn.get("content", "") or ""
                    break
            return {"response": text, "persona": "Alia"}

        if cmd == "stop_sim":
            text = agent.stop_simulation()
            return {"response": text, "persona": "Alia"}

        if cmd == "save":
            agent.save_and_close()
            release_agent(user_id)
            return {"response": "Session sauvegardée.", "persona": "Alia"}

        if cmd == "status":
            agent.print_status()
            return {"response": "Statut écrit dans les logs serveur.", "persona": "Alia"}

        if cmd == "history":
            return {"response": "Historique disponible dans l’interface ou les fichiers session.", "persona": "Alia"}

        response = agent.respond(message.strip())
        if "[Alia - hors rôle]" in response:
            persona = "Alia"
            response = response.replace("[Alia - hors rôle]", "").strip()
        else:
            persona = agent._get_persona_label()

        mode_label = "exam" if getattr(agent, "exam_mode", False) else "training"
        return {
            "response": response,
            "persona": persona,
            "mode": mode_label,
        }
    except Exception as e:
        logger.exception("send_message")
        return {"error": str(e)}


def stop_simulation(user_id: int) -> Dict[str, Any]:
    if _flask_available():
        try:
            base = str(FLASK_BASE).rstrip("/")
            r = requests.post(
                f"{base}/api/chat",
                json={"message": "stop_sim", "user_id": user_id},
                timeout=120,
            )
            if r.ok:
                data = r.json() if r.content else {}
                return {"response": data.get("response", "")}
        except requests.RequestException as e:
            logger.warning("Flask stop failed, fallback local: %s", e)

    try:
        agent = get_agent(user_id, mode_voix=False)
        agent.web_mode = True
        text = agent.stop_simulation()
        return {"response": text}
    except Exception as e:
        logger.exception("stop_simulation")
        return {"error": str(e)}


def run_command(user_id: int, command: str) -> Dict[str, Any]:
    cmd = (command or "").lower().strip()
    if _flask_available():
        try:
            base = str(FLASK_BASE).rstrip("/")
            r = requests.post(
                f"{base}/api/chat",
                json={"message": cmd, "user_id": user_id},
                timeout=120,
            )
            if r.ok:
                data = r.json() if r.content else {}
                return {"response": data.get("response", ""), "command": cmd}
        except requests.RequestException as e:
            logger.warning("Flask command failed, fallback local: %s", e)

    try:
        agent = get_agent(user_id, mode_voix=False)
        agent.web_mode = True
        if cmd == "eval":
            return {"response": agent.trigger_eval(), "command": cmd}
        if cmd == "next":
            return {"response": agent.trigger_next(), "command": cmd}
        if cmd == "save":
            agent.save_and_close()
            release_agent(user_id)
            return {"response": "Session sauvegardée.", "command": cmd}
        return {"error": f"Commande inconnue: {cmd}"}
    except Exception as e:
        logger.exception("run_command")
        return {"error": str(e)}
