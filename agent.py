"""
agent.py - Alia Agent v12  *** VERSION FINALE ***
═══════════════════════════════════════════════════════════════════════════════
Nouveautés v12 :
  - Auto-évaluation pendant la sim (mode training) : Alia commente le contenu
    ET les signaux comportementaux tour par tour — de façon naturelle
  - Mode Exam complet avec note finale /100 combinant contenu + comportement + voix
  - _sim_history_to_text() séparé du reste de l'historique M1+M2
  - FER+ via VisionAnalyzer v4 (calibration initiale + gestes mains)
  - Barge-in avec délai initial 1.5s (évite que le son de l'enceinte déclenche)
  - clean_for_tts() : supprime tout le markdown avant lecture vocale

Commandes :
    eval, next, sim, exam, stop_sim, save, status, history, quit
═══════════════════════════════════════════════════════════════════════════════
"""
import os
import re
import sys
import time
import json
import requests
import threading
from typing import List, Optional, Dict
from dotenv import load_dotenv

# ── Envoyer l'état de l'avatar via HTTP à avatar_server ──────────────────────
def _send_avatar_state(speaking: bool, listening: bool, text: str = "",
                       persona: str = "", sim_mode: str = ""):
    """Envoie l'état courant à avatar_server.py via HTTP."""
    try:
        if speaking:
            state = "speaking"
        elif listening:
            state = "listening"
        else:
            state = "idle"
        payload = {"state": state, "text": text}
        if persona:   payload["persona"]  = persona
        if sim_mode:  payload["sim_mode"] = sim_mode
        requests.post("http://localhost:9000/api/avatar/state", json=payload, timeout=2.0)
    except Exception:
        pass

# ── Moteur voix ────────────────────────────────────────────────────────────────
try:
    from voice import VoiceEngine, SimpleTranslator
    VOICE_ENGINE_AVAILABLE = True
except ImportError:
    VOICE_ENGINE_AVAILABLE = False
    SimpleTranslator = None
    print("[Agent] ⚠️  voice.py non trouvé — mode voix désactivé")

# ── Vision — MoondreamCoach (Moondream API + MediaPipe) ────────────────────────
try:
    from Moondreamcoach import MoondreamCoach, format_vision_report
    VisionAnalyzer = MoondreamCoach   # alias pour compatibilité
    VISION_AVAILABLE = True
    print("[Agent] Vision : MoondreamCoach ✓")
except Exception as e:
    print(f"[Vision] ⚠️  MoondreamCoach import échoué : {e}")
    try:
        from VisionAnalyzer import VisionAnalyzer, format_vision_report
        VISION_AVAILABLE = True
        print("[Agent] Vision : VisionAnalyzer (fallback)")
    except ImportError:
        VISION_AVAILABLE = False
        print("[Agent] ⚠️  Aucun module vision disponible")

# ── Prosody ────────────────────────────────────────────────────────────────────
try:
    from voice_prosody import ProsodyAnalyzer
    PROSODY_AVAILABLE = True
except ImportError:
    PROSODY_AVAILABLE = False
    print("[Agent] ⚠️  voice_prosody.py non trouvé — analyse vocale désactivée")

from session import load_session, DelegueProfile
from retriever import AliasRetriever
from memory import (
    save_session, load_last_session, get_session_context,
    update_scores, compute_global_level, generate_global_evaluation,
    print_delegue_history, list_sessions,
)
from prompts import (
    prompt_introduction,
    prompt_followup_m1, prompt_evaluation_m1, prompt_evaluation_next_m1,
    prompt_intro_m2, prompt_followup_m2, prompt_evaluation_m2, prompt_evaluation_next_m2,
    prompt_intro_m3, prompt_followup_m3, prompt_bilan_m3, prompt_coach_feedback,
)

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL   = "llama-3.1-8b"
GROQ_API_URL = "https://api.cerebras.ai/v1/chat/completions"
MAX_TOKENS   = 600  # Court et précis — évite les réponses longues qui bouclent
TEMPERATURE  = 0.4

SESSION_CSV     = "C:/Users/eyaen/Desktop/PI/data/raw/delegue_sessions.csv"
ASSIGNMENTS_CSV = "C:/Users/eyaen/Desktop/PI/data/raw/product_assignments.csv"
WHISPER_MODEL   = "small"

VOICE_COMMANDS = {
    "eval":     ["eval", "évalue", "évaluation", "evaluate"],
    "next":     ["next", "suivant", "avancer"],
    "sim":      ["sim", "simulation", "simuler"],
    "stop_sim": ["stop sim", "stop_sim", "arrêter simulation", "terminer simulation", "fin simulation"],
    "exam":     ["exam", "examen", "test final"],
    "save":     ["save", "sauvegarder"],
    "status":   ["status", "statut"],
    "history":  ["history", "historique"],
    "quit":     ["quit", "quitter", "exit", "sortir"],
}


# ══════════════════════════════════════════════════════════════════════════════
# LLM
# ══════════════════════════════════════════════════════════════════════════════

def clean_for_tts(text: str) -> str:
    """Supprime tout le markdown — edge-tts lit les * et # mot à mot."""
    t = text
    t = re.sub(r'\[Alia[^\]]*\]', '', t, flags=re.IGNORECASE)
    t = re.sub(r'\*\*([^*]+)\*\*', r'\1', t)
    t = re.sub(r'\*([^*]+)\*',     r'\1', t)
    t = re.sub(r'__([^_]+)__',     r'\1', t)
    t = re.sub(r'_([^_]+)_',       r'\1', t)
    t = re.sub(r'^#{1,6}\s+', '', t, flags=re.MULTILINE)
    t = t.replace('*', '').replace('`', '')
    t = re.sub(r'^\s*[-•]\s+', '', t, flags=re.MULTILINE)
    t = re.sub(r'^\s*\d+\.\s+', '', t, flags=re.MULTILINE)
    t = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', t)
    t = re.sub(r'\n{3,}', '\n\n', t)
    t = re.sub(r'[ \t]{2,}', ' ', t)
    return t.strip()


def call_groq(system_prompt: str, user_message: str, max_tokens: int = MAX_TOKENS) -> str:
    if not GROQ_API_KEY:
        return "[ERREUR] GROQ_API_KEY manquant dans .env"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type":  "application/json",
    }
    payload = {
        "model":       GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_message},
        ],
        "max_tokens":  max_tokens,
        "temperature": TEMPERATURE,
    }
    try:
        resp = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except requests.exceptions.Timeout:
        return "[ERREUR] Timeout API."
    except requests.exceptions.HTTPError as e:
        return f"[ERREUR HTTP] {e.response.status_code}"
    except Exception as e:
        return f"[ERREUR] {str(e)}"


def _extract_score_from_text(text: str) -> Optional[int]:
    for p in [r"(\d{1,3})\s*/\s*100", r"score\s*[:\-–]\s*(\d{1,3})",
              r"(\d{1,3})\s*sur\s*100", r"note\s*[:\-–]\s*(\d{1,3})"]:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            s = int(m.group(1))
            if 0 <= s <= 100:
                return s
    return None


# ══════════════════════════════════════════════════════════════════════════════
# AGENT ALIA v12
# ══════════════════════════════════════════════════════════════════════════════

class AliaAgent:

    def __init__(self, mode_voix: bool = False, whisper_model: str = WHISPER_MODEL):
        print("\n" + "="*60)
        print("   ALIA — Agent de Formation Pharmaceutique v13")
        print(f"   Mode : {'🎤 Voix (VAD + barge-in)' if mode_voix else '⌨️  Écrit'}")
        print("   Modules 1 · 2 · 3  +  MoondreamCoach (objets + posture + regard)")
        print("="*60)

        self.mode_voix = mode_voix
        self.web_mode  = False   # True en mode serveur web — TTS géré par avatar_server
        self.voice: Optional[VoiceEngine] = None
        
        if mode_voix and VOICE_ENGINE_AVAILABLE:
            self.voice = VoiceEngine(whisper_model=whisper_model)
        elif mode_voix:
            print("[Agent] ⚠️  VoiceEngine non disponible → mode écrit")
            self.mode_voix = False
        elif not mode_voix and VOICE_ENGINE_AVAILABLE and SimpleTranslator:
            # Mode web: créer un SimpleTranslator pour la traduction multilingue SANS micro
            self.voice = SimpleTranslator()
            print("[Agent] 🌍 Traduction multilingue activée (SimpleTranslator)")

        print("\n[Alia] Chargement session...")
        self.profile: DelegueProfile = load_session(SESSION_CSV, ASSIGNMENTS_CSV)
        print(f"[Alia] Délégué : {self.profile.name} (niveau: {self.profile.niveau})")

        print("[Alia] Initialisation RAG...")
        self.retriever = AliasRetriever()
        print(f"[Alia] LLM : {GROQ_MODEL} (Groq)")

        # État conversation
        self.conversation_history: List[dict] = []
        self.current_product: Optional[str]   = self.profile.get_current_product()
        self.product_context: str             = ""
        self.mode                             = "m1_formation"
        self.eval_question_number             = 1
        self.scores_by_module: Dict[str, int] = {}
        self.previous_context: str            = ""

        # Vision
        self.vision_analyzer   = None
        self.simulation_active = False
        self.vision_report     = None
        self.exam_mode         = False

        # Scores simulation
        self._sim_content_scores: List[float] = []
        self._sim_turn_count   = 0
        self._sim_start_index  = 0   # index dans conversation_history où la sim commence

        # Prosody
        self.prosody_analyzer: Optional[ProsodyAnalyzer] = None
        self._last_audio_path: Optional[str] = None

        # Chargement produit
        if self.current_product:
            chunks = self.retriever.get_product_chunks(self.current_product)
            self.product_context = self.retriever.format_context(chunks)
            print(f"[Alia] Produit : {self.current_product} | {len(chunks)} chunks")
            self.previous_context = get_session_context(
                self.profile.delegue_id, self.current_product
            )
            if self.previous_context:
                print("[Alia] Contexte session précédente chargé ✓")
            print()
        else:
            print("[Alia] Tous les produits sont complétés !")

    # ══════════════════════════════════════════════════════════════════════════
    # UTILITAIRES
    # ══════════════════════════════════════════════════════════════════════════

    def _history_to_text(self) -> str:
        """Historique général (12 derniers tours tous modules)."""
        lines = []
        for turn in self.conversation_history[-12:]:
            role = "Alia" if turn["role"] == "alia" else self.profile.name
            lines.append(f"{role} : {turn['content']}")
        return "\n".join(lines)

    def _sim_history_to_text(self) -> str:
        """Historique UNIQUEMENT depuis le début de la simulation en cours."""
        sim_turns = self.conversation_history[self._sim_start_index:]
        lines = []
        for turn in sim_turns:
            role = "Alia" if turn["role"] == "alia" else self.profile.name
            lines.append(f"{role} : {turn['content']}")
        return "\n".join(lines)

    def _add(self, role: str, content: str):
        self.conversation_history.append({"role": role, "content": content})

    def _enrich_context(self, msg: str) -> str:
        if len(msg.split()) > 3:
            relevant = self.retriever.search(query=msg, k=2, product_filter=self.current_product)
            extra = self.retriever.format_context(relevant)
            if extra and extra not in self.product_context:
                return self.product_context + f"\n\n[Contexte additionnel]\n{extra}"
        return self.product_context

    def _enrich_system_with_memory(self, system: str) -> str:
        if self.previous_context:
            return system + f"\n\n{self.previous_context}"
        return system

    def _record_module_score(self, module_key: str, alia_response: str):
        score = _extract_score_from_text(alia_response)
        if score is None:
            score = 70
            print(f"[Memory] Score {module_key} non trouvé → défaut 70/100")
        else:
            print(f"[Memory] Score {module_key} : {score}/100")
        self.scores_by_module[module_key] = score

    def _get_voice_role(self) -> str:
        """Retourne le role vocal selon le persona actif."""
        if self.mode == "m3_medecin":    return "doctor"
        if self.mode == "m3_pharmacien": return "pharmacien"
        return "alia"

    def _output(self, text: str, blocking: bool = False, role_label: str = "Alia"):
        """
        Affiche + lit à voix haute avec la bonne voix par segment.
        En web_mode : affichage console uniquement — TTS géré par avatar_server._speak_response()
        """
        print(f"\n{role_label} : {text}\n")
        if self.web_mode:
            return   # Le serveur gère le TTS + avatar state
        tts_text = clean_for_tts(text)
        if not tts_text:
            return

        # Determine persona label for avatar
        def _persona_for_role(role_lbl: str) -> str:
            if "Karim" in role_lbl or role_lbl == "doctor":   return "DR. KARIM"
            if "Sonia" in role_lbl or role_lbl == "pharmacien": return "MME SONIA"
            return "ALIA"

        # Sim mode tag
        sim_tag = ""
        if self.simulation_active:
            sim_tag = "exam" if self.exam_mode else "training"

        # En simulation M3 : splitter la réponse en segments (personnage vs Alia)
        if self.simulation_active and self.mode in ("m3_medecin", "m3_pharmacien"):
            segments = self._split_response_segments(tts_text)
            for seg_text, seg_role in segments:
                if not seg_text.strip():
                    continue
                if self.mode_voix and self.voice:
                    # Mode voix : envoyer l'état avant (edge-tts est synchrone et rapide)
                    pname = _persona_for_role(seg_role)
                    _send_avatar_state(speaking=True, listening=False,
                                       text=seg_text[:120], persona=pname, sim_mode=sim_tag)
                    self.voice.speak(seg_text, role=seg_role, blocking=True)
                else:
                    # Mode écrit : _speak_sim_only gère lui-même speaking=True au bon moment
                    self._speak_sim_only(seg_text, blocking=True, voice_role=seg_role)
            _send_avatar_state(speaking=False, listening=True, persona="ALIA", sim_mode=sim_tag)
            return

        # Hors simulation
        voice_role = "alia"
        if "Karim" in role_label or role_label == "doctor":
            voice_role = "doctor"
        elif "Sonia" in role_label or role_label == "pharmacien":
            voice_role = "pharmacien"

        pname = _persona_for_role(role_label)
        if self.mode_voix and self.voice:
            _send_avatar_state(speaking=True, listening=False,
                               text=tts_text[:120], persona=pname, sim_mode=sim_tag)
            self.voice.speak(tts_text, role=voice_role, blocking=True)
            _send_avatar_state(speaking=False, listening=True, persona="ALIA")
        elif self.simulation_active:
            # _speak_sim_only envoie speaking=True juste avant lecture
            self._speak_sim_only(tts_text, blocking=True, voice_role=voice_role)
            _send_avatar_state(speaking=False, listening=True, persona="ALIA")
        else:
            if blocking:
                _send_avatar_state(speaking=False, listening=False, persona="ALIA")

    def _split_response_segments(self, text: str) -> list:
        """
        Découpe une réponse M3 en segments (texte, role_vocal).
        Gère les cas :
          - Réponse pure Dr. Karim / Mme Sonia
          - [Alia - hors rôle] ... (correction)
          - Mélange : personnage parle, puis Alia corrige
        Retourne : [(texte_segment, role_vocal), ...]
        """
        persona_role = "doctor" if self.mode == "m3_medecin" else "pharmacien"
        segments = []

        # Chercher les marqueurs [Alia - hors rôle]
        import re as _re
        # Pattern : tout ce qui est entre [Alia...] et la fin ou le prochain bloc
        pattern = _re.compile(
            r'(\[Alia[^\]]*\]\s*:?\s*)(.*?)(?=\[Alia|\Z)',
            _re.DOTALL | _re.IGNORECASE
        )
        alia_matches = list(pattern.finditer(text))

        if not alia_matches:
            # Pas de marqueur Alia → tout est lu par le personnage
            segments.append((text.strip(), persona_role))
            return segments

        # Trouver le texte AVANT le premier marqueur Alia → personnage
        first_match_start = alia_matches[0].start()
        if first_match_start > 0:
            persona_text = text[:first_match_start].strip()
            if persona_text:
                segments.append((persona_text, persona_role))

        # Chaque bloc [Alia...] → voix Alia
        for match in alia_matches:
            alia_text = match.group(2).strip()
            if alia_text:
                segments.append((alia_text, "alia"))

        return segments if segments else [(text.strip(), persona_role)]

    def _speak_sim_only(self, text: str, blocking: bool = False, voice_role: str = "alia"):
        """TTS edge-tts minimal pour simulation en mode écrit — sans barge-in.
        
        Fix timing : _send_avatar_state(speaking=True) est envoyé JUSTE AVANT
        la lecture audio (pas pendant la synthèse), et speaking=False JUSTE APRÈS
        la fin réelle de la lecture. Cela synchronise parfaitement lèvres ↔ son.
        """
        try:
            import edge_tts
        except ImportError:
            print("[TTS] ⚠️  edge-tts non installé → pip install edge-tts")
            return

        import tempfile as _tf, os as _os, uuid as _uuid

        # Voix selon la langue détectée du délégué
        _lang = "fr"
        if self.voice and hasattr(self.voice, 'delegue_lang'):
            _lang = self.voice.delegue_lang or "fr"
        elif hasattr(self, '_delegue_lang'):
            _lang = self._delegue_lang or "fr"

        VOICE_MAP_SIM = {
            "fr": {
                "alia":       "fr-FR-DeniseNeural",
                "doctor":     "fr-FR-HenriNeural",
                "pharmacien": "fr-BE-CharlineNeural",
            },
            "en": {
                "alia":       "en-US-JennyNeural",
                "doctor":     "en-US-GuyNeural",
                "pharmacien": "en-US-AriaNeural",
            },
            "ar": {
                "alia":       "ar-SA-ZariyahNeural",
                "doctor":     "ar-SA-HamedNeural",
                "pharmacien": "ar-SA-ZariyahNeural",
            },
        }
        lang_map = VOICE_MAP_SIM.get(_lang, VOICE_MAP_SIM["fr"])
        sim_voice = lang_map.get(voice_role, lang_map["alia"])

        # Persona pour l'avatar
        def _pname(role):
            if role == "doctor":     return "DR. KARIM"
            if role == "pharmacien": return "MME SONIA"
            return "ALIA"

        def _run():
            tmp = _os.path.join(_tf.gettempdir(), f"alia_sim_{_uuid.uuid4().hex[:6]}.mp3")
            try:
                # ── ÉTAPE 1 : Synthèse (silencieuse, avatar reste idle) ────────
                import asyncio

                async def _synth(txt: str, path: str):
                    communicate = edge_tts.Communicate(txt, sim_voice)
                    await communicate.save(path)

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(_synth(text, tmp))
                finally:
                    loop.close()
                    asyncio.set_event_loop(None)

                if not _os.path.exists(tmp) or _os.path.getsize(tmp) < 100:
                    print("[TTS] ⚠️  Fichier audio vide ou absent")
                    return

                # ── ÉTAPE 2 : Avatar speaking=True juste avant la lecture ─────
                _send_avatar_state(speaking=True, listening=False,
                                   text=text[:120], persona=_pname(voice_role))

                # ── ÉTAPE 3 : Lecture audio ──────────────────────────────────
                played = False

                # Tentative 1 : pygame
                try:
                    import pygame as pg
                    if not pg.get_init():
                        pg.init()
                    if not pg.mixer.get_init():
                        pg.mixer.pre_init(44100, -16, 2, 512)
                        pg.mixer.init()
                    pg.mixer.music.load(tmp)
                    pg.mixer.music.play()
                    while pg.mixer.music.get_busy():
                        time.sleep(0.05)
                    pg.mixer.music.unload()
                    played = True
                except Exception as e:
                    print(f"[TTS] pygame échoué ({e}), essai playsound...")

                # Tentative 2 : playsound
                if not played:
                    try:
                        import playsound
                        playsound.playsound(tmp)
                        played = True
                    except Exception as e:
                        print(f"[TTS] playsound échoué ({e}), essai subprocess...")

                # Tentative 3 : subprocess (Windows) / afplay (macOS)
                if not played:
                    try:
                        import subprocess, platform
                        if platform.system() == "Windows":
                            subprocess.run(
                                ["powershell", "-c", f'(New-Object Media.SoundPlayer "{tmp}").PlaySync()'],
                                check=True, timeout=30
                            )
                        elif platform.system() == "Darwin":
                            subprocess.run(["afplay", tmp], check=True, timeout=30)
                        else:
                            subprocess.run(["mpg123", "-q", tmp], check=True, timeout=30)
                        played = True
                    except Exception as e:
                        print(f"[TTS] ⚠️  Aucun lecteur audio disponible : {e}")

            except Exception as e:
                print(f"[TTS] ⚠️  Erreur synthèse : {e}")
            finally:
                try:
                    if _os.path.exists(tmp):
                        _os.remove(tmp)
                except Exception:
                    pass

        if blocking:
            _run()
            # Avatar reset est géré par l'appelant (_output)
        else:
            # Mode non-bloquant : reset avatar à la fin du thread
            def _run_and_reset():
                _run()
                _send_avatar_state(speaking=False, listening=True)
            threading.Thread(target=_run_and_reset, daemon=True).start()

    def _get_persona_label(self) -> str:
        if self.mode == "m3_medecin":    return "Dr. Karim"
        if self.mode == "m3_pharmacien": return "Mme Sonia"
        return "🤖 Alia"

    # ══════════════════════════════════════════════════════════════════════════
    # MODE VOIX
    # ══════════════════════════════════════════════════════════════════════════

    def set_voice_mode(self, enabled: bool) -> str:
        """Basculer le mode voix activé/désactivé."""
        if enabled and not self.mode_voix:
            if VOICE_ENGINE_AVAILABLE:
                self.mode_voix = True
                if not self.voice:
                    self.voice = VoiceEngine(whisper_model=WHISPER_MODEL)
                print("[Agent] Mode voix ACTIVÉ ✓")
                return "Mode voix activé. Je suis prête à écouter."
            else:
                return "⚠️  Module voix non disponible. Veuillez utiliser le mode écrit."
        elif not enabled and self.mode_voix:
            self.mode_voix = False
            print("[Agent] Mode voix DÉSACTIVÉ")
            return "Mode écrit activé."
        elif enabled:
            return "Mode voix déjà activé."
        else:
            return "Mode écrit déjà activé."

    # ══════════════════════════════════════════════════════════════════════════
    # SESSION
    # ══════════════════════════════════════════════════════════════════════════

    def start_session(self) -> str:
        if not self.current_product:
            return f"Bravo {self.profile.name} ! Tu as complété tous tes produits."
        system, user = prompt_introduction(
            delegue_name=self.profile.name, niveau=self.profile.niveau,
            product_name=self.current_product, context=self.product_context,
            assigned_products=self.profile.assigned_products,
        )
        system   = self._enrich_system_with_memory(system)
        response = call_groq(system, user)
        self._add("alia", response)
        return response

    # ══════════════════════════════════════════════════════════════════════════
    # RÉPONSE PRINCIPALE
    # ══════════════════════════════════════════════════════════════════════════

    def respond(self, delegue_message: str) -> str:
        self._add("delegue", delegue_message)
        ctx = self._enrich_context(delegue_message)

        if self.mode == "m1_formation":
            system, user = prompt_followup_m1(
                delegue_name=self.profile.name, niveau=self.profile.niveau,
                product_name=self.current_product, context=ctx,
                conversation_history=self._history_to_text(),
                delegue_message=delegue_message,
                assigned_products=self.profile.assigned_products,
            )
        elif self.mode == "m1_evaluation":
            self.mode = "m1_done"
            system, user = prompt_evaluation_next_m1(
                delegue_name=self.profile.name,
                product_name=self.current_product, context=self.product_context,
                conversation_history=self._history_to_text(),
                question_number=4, delegue_message=delegue_message,
                niveau=self.profile.niveau,
            )
        elif self.mode == "m2_formation":
            system, user = prompt_followup_m2(
                delegue_name=self.profile.name, niveau=self.profile.niveau,
                product_name=self.current_product, context=ctx,
                conversation_history=self._history_to_text(),
                delegue_message=delegue_message,
                assigned_products=self.profile.assigned_products,
            )
        elif self.mode == "m2_evaluation":
            self.mode = "m2_done"
            system, user = prompt_evaluation_next_m2(
                delegue_name=self.profile.name,
                product_name=self.current_product, context=self.product_context,
                conversation_history=self._history_to_text(),
                question_number=2, delegue_message=delegue_message,
                niveau=self.profile.niveau,
            )
        elif self.mode in ("m3_medecin", "m3_pharmacien"):
            interlocuteur = "medecin" if self.mode == "m3_medecin" else "pharmacien"
            self._sim_turn_count += 1

            # Snapshot vision
            vision_snap = {}
            if VISION_AVAILABLE and self.vision_analyzer:
                try:
                    vision_snap = self.vision_analyzer.get_snapshot(self._sim_turn_count)
                except Exception:
                    pass

            # Snapshot prosody
            prosody_snap = {}
            if PROSODY_AVAILABLE and self.prosody_analyzer:
                try:
                    prosody_snap = self.prosody_analyzer.get_snapshot()
                except Exception:
                    pass

            # ── Mode TRAINING : injecter le hint comportemental pour que Alia commente ──
            # ── Mode EXAMEN  : aucun hint, le personnage ne corrige JAMAIS ──────────────
            if not self.exam_mode:
                behavioral_hint = self._build_behavioral_hint(vision_snap, prosody_snap)
                if behavioral_hint:
                    delegue_message = delegue_message + (
                        f"\n\n[CONTEXTE COMPORTEMENTAL — pour Alia uniquement, ne pas lire mot pour mot]: "
                        f"{behavioral_hint}"
                    )

            # ── Alerte objet IMMÉDIATE — interrompt avant même d'appeler le LLM ────────
            # Si Moondream vient de détecter un objet, Alia le dit tout de suite
            if (not self.exam_mode and vision_snap.get("object_detected")
                    and vision_snap.get("object_desc")):
                obj_desc = vision_snap["object_desc"]
                # Mémoriser pour ne pas répéter au prochain tour si l'objet n'a pas changé
                if obj_desc != getattr(self, "_last_object_alert", ""):
                    self._last_object_alert = obj_desc
                    niveau = self.profile.niveau
                    if niveau == "debutant":
                        alert_msg = (
                            f"Attends — Moondream détecte que tu tiens quelque chose "
                            f"({obj_desc}). En visite médicale, les mains doivent être libres. "
                            f"Pose-le et recommençons ce tour."
                        )
                    else:
                        alert_msg = (
                            f"Stop. {obj_desc} — pas acceptable en visite. "
                            f"Les mains libres, c'est la base. On reprend."
                        )
                    # Parler immédiatement avec la voix Alia
                    self._add("alia", f"[Alia - hors rôle] {alert_msg}")
                    _send_avatar_state(speaking=True, listening=False,
                                       text=alert_msg[:120], persona="ALIA")
                    if self.mode_voix and self.voice:
                        self.voice.speak(alert_msg, role="alia", blocking=True)
                    else:
                        self._speak_sim_only(alert_msg, blocking=True, voice_role="alia")
                    _send_avatar_state(speaking=False, listening=True, persona="ALIA")
                    print(f"\n[Alia - ALERTE OBJET] : {alert_msg}\n")
            elif vision_snap.get("object_detected") is False:
                # Objet disparu → reset pour pouvoir alerter à nouveau si revient
                self._last_object_alert = ""

            system, user = prompt_followup_m3(
                delegue_name=self.profile.name, niveau=self.profile.niveau,
                product_name=self.current_product, context=ctx,
                conversation_history=self._sim_history_to_text(),
                delegue_message=delegue_message, interlocuteur=interlocuteur,
                assigned_products=self.profile.assigned_products,
                vision_snapshot=vision_snap,
                prosody_snapshot=prosody_snap,
                exam_mode=self.exam_mode,
            )
        else:
            system, user = prompt_followup_m1(
                delegue_name=self.profile.name, niveau=self.profile.niveau,
                product_name=self.current_product, context=ctx,
                conversation_history=self._history_to_text(),
                delegue_message=delegue_message,
                assigned_products=self.profile.assigned_products,
            )

        system   = self._enrich_system_with_memory(system)
        # En simulation M3 : max 350 tokens pour forcer des réponses courtes sans boucle
        if self.mode in ("m3_medecin", "m3_pharmacien") and self.simulation_active:
            response = call_groq(system, user, max_tokens=350)
        else:
            response = call_groq(system, user)
        self._add("alia", response)

        # Score contenu M3
        if self.mode in ("m3_medecin", "m3_pharmacien") and self.simulation_active:
            self._score_sim_turn(delegue_message, response)

        if self.mode == "m1_done":
            self._record_module_score("module_1", response)
        elif self.mode == "m2_done":
            self._record_module_score("module_2", response)

        return response

    # ══════════════════════════════════════════════════════════════════════════
    # ÉVALUATION
    # ══════════════════════════════════════════════════════════════════════════

    def trigger_eval(self) -> str:
        self.eval_question_number = 1
        if self.mode in ("m1_formation", "m1_done", "m1_ready"):
            self.mode = "m1_evaluation"
            system, user = prompt_evaluation_m1(
                delegue_name=self.profile.name, niveau=self.profile.niveau,
                product_name=self.current_product, context=self.product_context,
                conversation_history=self._history_to_text(),
            )
        elif self.mode in ("m2_formation", "m2_done", "m2_ready"):
            self.mode = "m2_evaluation"
            system, user = prompt_evaluation_m2(
                delegue_name=self.profile.name, niveau=self.profile.niveau,
                product_name=self.current_product, context=self.product_context,
                conversation_history=self._history_to_text(),
            )
        elif self.mode == "m3_medecin":
            system, user = prompt_bilan_m3(
                delegue_name=self.profile.name,
                product_name=self.current_product, context=self.product_context,
                conversation_history=self._sim_history_to_text(),
                interlocuteur="medecin",
            )
            self.mode = "m3_pharmacien"
        elif self.mode == "m3_pharmacien":
            system, user = prompt_bilan_m3(
                delegue_name=self.profile.name,
                product_name=self.current_product, context=self.product_context,
                conversation_history=self._sim_history_to_text(),
                interlocuteur="pharmacien",
            )
            self.mode = "done"
            system   = self._enrich_system_with_memory(system)
            response = call_groq(system, user)
            self._add("alia", response)
            self._trigger_global_evaluation()
            return response
        else:
            return f"[Alia] Pas d'évaluation en mode '{self.mode}'. Tape 'next' pour avancer."

        system   = self._enrich_system_with_memory(system)
        response = call_groq(system, user)
        self._add("alia", response)
        return response

    # ══════════════════════════════════════════════════════════════════════════
    # MODULE SUIVANT
    # ══════════════════════════════════════════════════════════════════════════

    def trigger_next(self) -> str:
        if self.mode in ("m1_formation", "m1_evaluation", "m1_done", "m1_ready"):
            self.mode = "m2_formation"
            system, user = prompt_intro_m2(
                delegue_name=self.profile.name, niveau=self.profile.niveau,
                product_name=self.current_product, context=self.product_context,
                assigned_products=self.profile.assigned_products,
            )
        elif self.mode in ("m2_formation", "m2_evaluation", "m2_done", "m2_ready"):
            self.mode = "m3_medecin"
            system, user = prompt_intro_m3(
                delegue_name=self.profile.name, niveau=self.profile.niveau,
                product_name=self.current_product, context=self.product_context,
                interlocuteur="medecin",
                assigned_products=self.profile.assigned_products,
            )
        elif self.mode == "m3_medecin":
            self.mode = "m3_pharmacien"
            system, user = prompt_intro_m3(
                delegue_name=self.profile.name, niveau=self.profile.niveau,
                product_name=self.current_product, context=self.product_context,
                interlocuteur="pharmacien",
                assigned_products=self.profile.assigned_products,
            )
        else:
            return f"[Alia] Mode '{self.mode}' — tape 'eval' ou 'quit'."

        system   = self._enrich_system_with_memory(system)
        response = call_groq(system, user)
        self._add("alia", response)
        return response

    # ══════════════════════════════════════════════════════════════════════════
    # SIMULATION
    # ══════════════════════════════════════════════════════════════════════════

    def start_simulation(self, camera_index: int = 0, exam_mode: bool = False, interlocuteur: Optional[str] = None):
        if self.simulation_active:
            print("[Simulation] Déjà active.")
            return

        # Choix médecin / pharmacien si non spécifié
        if interlocuteur is None:
            print("\n" + "─"*50)
            print("  Avec qui veux-tu simuler la visite ?")
            print("  [1] 👨‍⚕️  Dr. Karim   — médecin généraliste")
            print("  [2] 💊  Mme Sonia  — pharmacienne")
            print("─"*50)
            while True:
                choix = input("  Ton choix (1 ou 2) : ").strip()
                if choix == "1":
                    interlocuteur = "medecin"
                    break
                elif choix == "2":
                    interlocuteur = "pharmacien"
                    break
                else:
                    print("  Tape 1 ou 2.")
            print()

        # Vision — show_preview=False car la cam est affichée dans alia_avatar.html (PiP)
        if VISION_AVAILABLE:
            try:
                self.vision_analyzer = VisionAnalyzer(camera_index=camera_index, show_preview=False)
                self.vision_analyzer.start()
                print("[Simulation] 📷 Webcam active — analyse comportementale + calibration en cours")
                print("[Simulation]    (Flux vidéo visible dans l'interface avatar → PiP bas-droite)")
            except Exception as e:
                print(f"[Simulation] ⚠️  Webcam indisponible : {e}")

        self.simulation_active   = True
        self.exam_mode           = exam_mode
        self._sim_turn_count     = 0
        self._sim_content_scores = []
        self._sim_start_index    = len(self.conversation_history)

        # Forcer le bon mode selon le choix
        target_mode = "m3_medecin" if interlocuteur == "medecin" else "m3_pharmacien"
        self.mode = target_mode

        mode_label = "🎯 MODE EXAMEN — Alia joue le rôle SANS corriger. Note finale à la fin." \
            if exam_mode else "🎓 MODE TRAINING — Alia corrige en temps réel et te guide."
        print(f"\n{mode_label}")

        # Prosody
        if PROSODY_AVAILABLE:
            self.prosody_analyzer = ProsodyAnalyzer()
            print("[Simulation] 🎙️  Analyse prosodique (voix) activée")

        print("\n" + "─"*60)
        print("🎬 SIMULATION DÉMARRÉE")
        persona_label = "Dr. Karim (médecin)" if interlocuteur == "medecin" else "Mme Sonia (pharmacienne)"
        print(f"   Tu parles à : {persona_label}")
        if self.mode_voix:
            print("   🎤 Tu peux m'interrompre en commençant à parler.")
        if VISION_AVAILABLE and self.vision_analyzer:
            print("   📷 Ton comportement est analysé en temps réel.")
        print("   Tape/dis 'stop_sim' pour terminer et voir ton bilan.")
        print("─"*60 + "\n")

        # Intro M3
        system, user  = prompt_intro_m3(
            delegue_name=self.profile.name, niveau=self.profile.niveau,
            product_name=self.current_product, context=self.product_context,
            interlocuteur=interlocuteur, assigned_products=self.profile.assigned_products,
        )
        system   = self._enrich_system_with_memory(system)
        response = call_groq(system, user)
        self._add("alia", response)
        persona  = "Dr. Karim" if interlocuteur == "medecin" else "Mme Sonia"
        self._output(response, blocking=True, role_label=persona)

    def stop_simulation(self) -> str:
        if not self.simulation_active:
            return "[Simulation] Aucune simulation active."

        print("\n[Simulation] Fin — génération du bilan...")
        self.simulation_active = False

        # Score contenu
        content_score = None
        if self._sim_content_scores:
            content_score = (sum(self._sim_content_scores) / len(self._sim_content_scores)) * 10
        elif self.scores_by_module:
            content_score = sum(self.scores_by_module.values()) / len(self.scores_by_module)

        # Bilan prosodique
        prosody_report = None
        prosody_text   = ""
        if PROSODY_AVAILABLE and self.prosody_analyzer:
            try:
                prosody_report = self.prosody_analyzer.build_report()
                prosody_text   = self.prosody_analyzer.format_report_text(prosody_report)
                print(prosody_text)
            except Exception as e:
                print(f"[Simulation] Erreur bilan prosodique : {e}")

        # Bilan vision + feedback LLM
        if VISION_AVAILABLE and self.vision_analyzer:
            try:
                self.vision_report = self.vision_analyzer.stop()
                vision_text = format_vision_report(self.vision_report, content_score)
                print(vision_text)
                feedback = self._generate_combined_feedback(
                    self.vision_report, prosody_report, content_score
                )
                self._output(feedback, blocking=True)
                return vision_text
            except Exception as e:
                print(f"[Simulation] Erreur bilan vision : {e}")

        return "[Simulation] Terminée."

    def _score_sim_turn(self, delegue_msg: str, alia_response: str):
        """Score 0-10 de la qualité de réponse du délégué à l'objection."""
        hors_role = bool(re.search(r'\[Alia', alia_response, re.IGNORECASE))
        if hors_role:
            score = 3.0
        else:
            words = delegue_msg.split()
            score = 5.0
            if len(words) >= 15: score += 1.0
            if len(words) >= 30: score += 1.0
            good_kw = ["docteur", "efficace", "patient", "résultat", "48h",
                       "tolérance", "bénéfice", "solution", "option", "clinique",
                       "complémentaire", "compliance", "sécurité"]
            hits = sum(1 for k in good_kw if k.lower() in delegue_msg.lower())
            score = min(10.0, score + hits)
        self._sim_content_scores.append(score)

    def _generate_combined_feedback(self, vision_report, prosody_report, content_score) -> str:
        """
        Feedback formateur final — compatible MoondreamCoach ET VisionAnalyzer.
        Mode examen : note finale /100 détaillée.
        Mode training : bilan formatif.
        """
        sim_turns = self._sim_turn_count
        history   = self._sim_history_to_text()

        if sim_turns < 2 or len(history.split()) < 30:
            return (
                f"La simulation était trop courte pour un vrai bilan, {self.profile.name}. "
                f"Tu n'as eu que {sim_turns} tour(s). "
                "Il faut au minimum 3-4 échanges complets. "
                "Relance 'sim' et joue le jeu jusqu'au bout."
            )

        # ── Données vision (compatible MoondreamCoach + VisionAnalyzer) ────────
        eye_score    = getattr(vision_report, "eye_contact_score", 5.0)
        smile_score  = getattr(vision_report, "smile_score", 5.0)
        posture_score= getattr(vision_report, "posture_score", 5.0)
        gesture_score= getattr(vision_report, "gesture_score", 5.0)
        stress_score = getattr(vision_report, "stress_score", 7.0)
        behav_score  = getattr(vision_report, "behavioral_score", 5.0)
        eye_ratio    = getattr(vision_report, "eye_contact_ratio", 0.5)
        smile_ratio  = getattr(vision_report, "smile_ratio", 0.2)
        # stress_peaks / dominant_emotion n'existent pas dans MoondreamCoach → défauts sécurisés
        stress_peaks = getattr(vision_report, "stress_peaks", 0)
        dominant_emo = getattr(vision_report, "dominant_emotion", "non mesuré")

        # Objets détectés (MoondreamCoach uniquement)
        axes_history = getattr(vision_report, "axes_history", [])
        obj_detected = [a for a in axes_history if getattr(a, "object_detected", False)]
        obj_block = ""
        if obj_detected:
            obj_descs = list({getattr(a, "object_desc", "") for a in obj_detected if getattr(a, "object_desc", "")})
            obj_block = f"\n- Objets détectés ({len(obj_detected)}x) : {', '.join(obj_descs[:3])}"

        vision_summary = f"""ANALYSE VISUELLE (webcam) :
- Contact visuel     : {eye_score}/10 ({int(eye_ratio*100)}% du temps)
- Sourire            : {smile_score}/10 ({int(smile_ratio*100)}% du temps)
- Posture            : {posture_score}/10
- Gestes/mains       : {gesture_score}/10
- Sérénité           : {stress_score}/10{' (' + str(stress_peaks) + ' pics)' if stress_peaks else ''}
- Émotion dominante  : {dominant_emo}
- Score comportemental : {behav_score}/10{obj_block}"""

        # ── Données prosodiques ─────────────────────────────────────────────────
        prosody_summary = "(analyse vocale non disponible)"
        prosody_conf = 5
        if prosody_report and getattr(prosody_report, "total_turns", 0) > 0:
            prosody_conf = getattr(prosody_report, "avg_confidence_score", 5)
            prosody_summary = f"""ANALYSE VOCALE :
- Débit moyen      : {getattr(prosody_report, 'avg_wpm', 0):.0f} mots/min (idéal : 110-160)
- Hésitations      : {getattr(prosody_report, 'avg_hesitation_rate', 0):.1f}/min
- Score confiance  : {prosody_conf}/10
- Tours difficiles : {getattr(prosody_report, 'high_stress_turns', None) or 'aucun'}
- Tours solides    : {getattr(prosody_report, 'strong_turns', None) or 'aucun'}"""

        # ── Moments clés par tour ───────────────────────────────────────────────
        turn_moments = ""
        turn_snaps = getattr(vision_report, "turn_snapshots", [])
        if turn_snaps:
            lines = []
            for snap in turn_snaps:
                flags = []
                eye_r   = getattr(snap, "eye_contact_ratio", 1.0)
                smile_r = getattr(snap, "smile_ratio", 0.5)
                gest    = getattr(snap, "hand_gesture", "unknown")
                axes    = getattr(snap, "axes", None)
                if eye_r < 0.35:           flags.append(f"regard {int(eye_r*100)}%")
                if smile_r < 0.1:          flags.append("pas de sourire")
                if gest == "crossed":       flags.append("bras croisés")
                if axes and getattr(axes, "object_detected", False):
                    flags.append(f"🚨 {getattr(axes, 'object_desc', 'objet')}")
                status = " | ".join(flags) if flags else "RAS"
                lines.append(f"  Tour {snap.turn_number} : {status}")
            turn_moments = "MOMENTS CLÉS PAR TOUR :\n" + "\n".join(lines)

        # ── Score contenu ───────────────────────────────────────────────────────
        content_info = ""
        content_note = None
        if content_score is not None:
            c10 = round(content_score / 10, 1)
            content_note = c10
            content_info = f"SCORE GESTION OBJECTIONS : {c10}/10"

        # ── Note finale (mode examen uniquement) ────────────────────────────────
        note_finale_bloc = ""
        if self.exam_mode and content_note is not None:
            note_glob = round(
                behav_score * 0.35 +
                content_note * 0.45 +
                prosody_conf * 0.20,
                1
            )
            note_finale_bloc = f"""
NOTE FINALE CALCULÉE (mode examen) :
  Comportement (35%) : {behav_score}/10
  Contenu/objections (45%) : {content_note}/10
  Voix/fluidité (20%) : {prosody_conf}/10
  ─────────────────────
  TOTAL : {note_glob}/10  ({int(note_glob*10)}/100)"""

        mode_label = "MODE EXAMEN — inclus la note finale /100 calculée ci-dessus dans ton feedback." \
            if self.exam_mode else "MODE TRAINING — feedback formatif, pas de note finale chiffrée."

        # Bloc objets pour le prompt final
        obj_prompt_bloc = ""
        if obj_detected:
            obj_descs_u = list({getattr(a, "object_desc", "") for a in obj_detected if getattr(a, "object_desc", "")})
            obj_prompt_bloc = (
                f"\n\nOBJETS DÉTECTÉS PAR MOONDREAM PENDANT LA SIMULATION ({len(obj_detected)} fois) : "
                f"{', '.join(obj_descs_u[:3])}. "
                f"C'est une ERREUR GRAVE — un délégué médical n'a jamais d'objet en main pendant une visite. "
                f"Tu dois mentionner ça explicitement dans ton bilan."
            )

        system = f"""Tu es Alia, coach commerciale pharmaceutique EXIGEANTE.
Tu viens de terminer une simulation avec {self.profile.name} ({sim_turns} tours).

{vision_summary}

{prosody_summary}

{turn_moments}

{content_info}

{note_finale_bloc}
{obj_prompt_bloc}

{mode_label}

RÈGLES ABSOLUES :
1. HONNÊTETÉ TOTALE : si le délégué a mal répondu aux objections, dis-le clairement.
2. BASÉ SUR LES FAITS : cite uniquement ce qui s'est passé dans l'historique.
3. COMPORTEMENT + CONTENU LIÉS : relie les signaux non-verbaux au contenu.
   Ex: "Tu as décroché le regard quand Mme Sonia a objecté sur le prix — ça trahit un manque de préparation."
4. Si objet détecté → PREMIÈRE phrase du bilan, erreur grave, pas optionnel.
5. FORMAT : 6-8 phrases max. Pas de liste. Ton coach direct et bienveillant.
   PAS d'astérisques, PAS de titres markdown."""

        user = f"""HISTORIQUE COMPLET DE LA SIMULATION ({sim_turns} tours) :
{history}

Génère le bilan formateur de {self.profile.name}.
Structure EN PROSE :
1. Verdict : cette visite aurait-elle abouti ? Sois honnête.
2. Ce qui a bien fonctionné — cite un moment RÉEL + signal comportemental associé.
   Si RIEN n'a bien fonctionné → dis-le.
3. Ce qui a fragilisé la visite — moment RÉEL + signal non-verbal ou vocal.
4. {"Note finale : annonce la note /100 et explique ce qui a pesé dans chaque composante." if self.exam_mode else "Conseil concret et immédiatement actionnable."}
5. Phrase de clôture motivante mais réaliste."""

        return call_groq(system, user, max_tokens=500)

    def _build_behavioral_hint(self, vision_snap: dict, prosody_snap: dict) -> str:
        """
        Construit un hint comportemental structuré par axe, adapté au niveau.
        Priorité : OBJET > REGARD > POSTURE > VOIX
        Le LLM l'intègre naturellement dans sa réponse — pas lu mot pour mot.
        """
        niveau = self.profile.niveau
        hints  = []

        # Seuils adaptés au niveau
        eye_threshold   = {"debutant": 0.20, "intermediaire": 0.35, "avance": 0.50}.get(niveau, 0.35)
        stress_threshold= {"debutant": 45,   "intermediaire": 30,   "avance": 20  }.get(niveau, 30)
        doubt_threshold = {"debutant": 0.6,  "intermediaire": 0.45, "avance": 0.30}.get(niveau, 0.45)

        if vision_snap and vision_snap.get("face_detected"):
            # ── AXE 1 : OBJET (priorité absolue) ──────────────────────────────
            if vision_snap.get("object_detected") and vision_snap.get("object_desc"):
                obj = vision_snap["object_desc"]
                if niveau == "debutant":
                    hints.append(
                        f"[OBJET] Moondream a détecté : '{obj}'. "
                        f"Dis-lui gentiment de poser l'objet : 'Pour les visites, "
                        f"les mains libres c'est important — on peut reprendre ?'"
                    )
                else:
                    hints.append(
                        f"[OBJET CRITIQUE] '{obj}' détecté. "
                        f"Interromps le rôle et dis-lui clairement : "
                        f"'Enlève ça — un délégué ne tient jamais d'objet en visite.'"
                    )

            # ── AXE 2 : REGARD ────────────────────────────────────────────────
            if vision_snap.get("regard_desc") and not vision_snap.get("regard_ok", True):
                regard = vision_snap["regard_desc"]
                eye_pct = vision_snap.get("eye_contact_pct", 100)
                if niveau == "debutant":
                    hints.append(f"[REGARD] Regard insuffisant ({regard}) — encourage-le doucement à regarder la caméra")
                elif niveau == "intermediaire":
                    hints.append(f"[REGARD] {regard} — contact visuel {eye_pct}%, mentionne-le naturellement")
                else:
                    hints.append(f"[REGARD INSUFFISANT] {regard} — regard fuyant = signal de manque de confiance, exige la correction")
            elif vision_snap.get("eye_contact_pct", 100) < int(eye_threshold * 100):
                hints.append(f"[REGARD] Contact visuel faible ({vision_snap['eye_contact_pct']}%)")

            # ── AXE 3 : POSTURE ───────────────────────────────────────────────
            if vision_snap.get("posture_desc") and not vision_snap.get("posture_ok", True):
                posture = vision_snap["posture_desc"]
                hints.append(f"[POSTURE] Moondream détecte : '{posture}' — à corriger")
            elif vision_snap.get("hand_gesture") == "crossed":
                hints.append("[POSTURE] Bras croisés — posture défensive, à mentionner")

        # ── AXE 4 : VOIX (Hume AI) ────────────────────────────────────────────
        if prosody_snap:
            hume_doubt = prosody_snap.get("hume_doubt", 0.0)
            hume_top   = prosody_snap.get("hume_top_emotion", "")
            wpm        = prosody_snap.get("wpm", 0)
            hesit      = prosody_snap.get("hesitation_rate", 0)

            if hume_doubt > doubt_threshold:
                if niveau == "debutant":
                    hints.append(f"[VOIX] Doute détecté dans la voix (Hume: {hume_doubt:.2f}) — encourage avant de corriger")
                else:
                    hints.append(f"[VOIX] Hume AI: doute vocal fort ({hume_doubt:.2f}) — conviction insuffisante sur cet argument")

            if wpm > 0 and wpm < 70:
                hints.append(f"[VOIX] Débit très lent ({wpm:.0f} mots/min) — hésitations ou manque de préparation")
            elif wpm > 210:
                hints.append(f"[VOIX] Débit trop rapide ({wpm:.0f} mots/min) — stress, perd l'impact")

            if hesit > 8:
                hints.append(f"[VOIX] {hesit:.0f} hésitations/min — fluidité insuffisante")

            if hume_top in {"Confidence", "Determination", "Enthusiasm"}:
                hints.append(f"[VOIX ✓] Hume détecte '{hume_top}' — voix confiante, renforce cette énergie")

        if not hints:
            return ""

        intro = {
            "debutant":      "Signaux comportementaux — intègre avec bienveillance",
            "intermediaire": "Signaux comportementaux — mentionne naturellement dans ta correction",
            "avance":        "Signaux comportementaux — délégué senior, exige la maîtrise complète",
        }.get(niveau, "Signaux comportementaux")

        return f"{intro} :\n" + "\n".join(f"  {h}" for h in hints)

    # ── Rétrocompat ───────────────────────────────────────────────────────────
    def _generate_vision_feedback(self, report, content_score) -> str:
        return self._generate_combined_feedback(report, None, content_score)

    # ══════════════════════════════════════════════════════════════════════════
    # PROGRESSION DE NIVEAU — mis à jour après chaque session complète
    # ══════════════════════════════════════════════════════════════════════════

    def _compute_and_update_niveau(self) -> str:
        """
        Calcule le nouveau niveau du délégué basé sur ses scores cumulés
        sur TOUS les produits, et met à jour self.profile.niveau si changement.

        Logique de progression :
          score moyen < 50         → debutant
          50 <= score moyen < 75   → intermediaire
          score moyen >= 75        → avance

        Un niveau ne descend JAMAIS automatiquement (on peut stagner, pas régresser).
        """
        # Récupérer tous les scores produits du profil
        all_scores = list(self.profile.product_scores.values())

        # Ajouter les scores de la session courante s'ils n'y sont pas déjà
        if self.scores_by_module:
            session_avg = sum(self.scores_by_module.values()) // max(len(self.scores_by_module), 1)
            # Mettre à jour le score du produit courant dans le profil
            if self.current_product:
                self.profile.product_scores[self.current_product] = session_avg
                all_scores = list(self.profile.product_scores.values())

        if not all_scores:
            return self.profile.niveau

        # Score moyen sur tous les produits (pondéré — les produits complétés pèsent plus)
        completed   = [s for s in all_scores if s >= 60]
        in_progress = [s for s in all_scores if s < 60]

        # Pondération : 70% moyenne complétés + 30% moyenne en cours
        if completed and in_progress:
            weighted = 0.7 * (sum(completed) / len(completed)) + \
                       0.3 * (sum(in_progress) / len(in_progress))
        elif completed:
            weighted = sum(completed) / len(completed)
        else:
            weighted = sum(in_progress) / len(in_progress)

        weighted = round(weighted, 1)

        # Déterminer le nouveau niveau
        if weighted >= 75:
            new_niveau = "avance"
        elif weighted >= 50:
            new_niveau = "intermediaire"
        else:
            new_niveau = "debutant"

        # Règle : on ne régresse JAMAIS
        niveau_rank = {"debutant": 0, "intermediaire": 1, "avance": 2}
        current_rank = niveau_rank.get(self.profile.niveau, 0)
        new_rank     = niveau_rank.get(new_niveau, 0)

        if new_rank > current_rank:
            old_niveau = self.profile.niveau
            self.profile.niveau = new_niveau
            print(f"\n🎉 [Niveau] PROGRESSION : {old_niveau} → {new_niveau} "
                  f"(score moyen pondéré : {weighted}/100)")
            return new_niveau
        elif new_rank == current_rank:
            print(f"[Niveau] Maintenu : {self.profile.niveau} (score moyen : {weighted}/100)")
        else:
            print(f"[Niveau] Score moyen {weighted}/100 — niveau maintenu à {self.profile.niveau} "
                  f"(pas de régression automatique)")

        return self.profile.niveau

    # ══════════════════════════════════════════════════════════════════════════
    # ÉVALUATION GLOBALE
    # ══════════════════════════════════════════════════════════════════════════

    def _trigger_global_evaluation(self):
        if not self.scores_by_module:
            return
        print("\n[Alia] Calcul évaluation globale...")

        # ── Mise à jour du niveau AVANT de calculer le bilan ──────────────────
        niveau_final = self._compute_and_update_niveau()

        all_sessions = list_sessions(self.profile.delegue_id)
        bilan = generate_global_evaluation(
            delegue_name=self.profile.name,
            product_name=self.current_product,
            scores_by_module=self.scores_by_module,
            niveau_final=niveau_final,
            all_sessions=all_sessions,
        )

        # Annoncer la progression de niveau si changé
        if niveau_final != self.profile.niveau:
            annonce = (
                f"Et bonne nouvelle {self.profile.name} — "
                f"tes résultats te font passer au niveau {niveau_final}. "
                f"Les prochaines sessions seront plus exigeantes. C'est mérité."
            )
            self._output(annonce, blocking=True)
            self._add("alia", annonce)

        print(f"\n{'='*60}\n  BILAN GLOBAL\n{'='*60}")
        self._output(bilan, blocking=True)
        self._add("alia", bilan)

    # ══════════════════════════════════════════════════════════════════════════
    # SAUVEGARDE
    # ══════════════════════════════════════════════════════════════════════════

    def save_and_close(self):
        if not self.conversation_history:
            print("[Memory] Rien à sauvegarder.")
            return
        if self.simulation_active:
            self.stop_simulation()
        if self.mode_voix and self.voice:
            self.voice.interrupt()

        print("\n[Memory] Sauvegarde...")

        # ── Calcul et mise à jour du niveau (si scores disponibles) ────────────
        if self.scores_by_module:
            self._compute_and_update_niveau()

        product_score = (
            sum(self.scores_by_module.values()) // max(len(self.scores_by_module), 1)
        ) if self.scores_by_module else 0

        save_session(
            delegue_id=self.profile.delegue_id,
            delegue_name=self.profile.name,
            product_name=self.current_product,
            module_reached=self.mode,
            conversation_history=self.conversation_history,
            scores=self.scores_by_module,
            generate_summary=True,
        )
        if self.scores_by_module and self.current_product:
            update_scores(
                delegue_id=self.profile.delegue_id,
                product_name=self.current_product,
                new_score=product_score,
                module="module_1",
                session_csv=SESSION_CSV,
                assignments_csv=ASSIGNMENTS_CSV,
            )

        # ── Persiste le nouveau niveau dans le CSV de session ─────────────────
        self._persist_niveau_to_csv()

        print("[Memory] Session sauvegardée ✓")

    def _persist_niveau_to_csv(self):
        """Met à jour la colonne 'niveau' dans delegue_sessions.csv."""
        try:
            import pandas as pd
            df = pd.read_csv(SESSION_CSV)
            mask = df["delegue_id"] == self.profile.delegue_id
            if mask.any():
                df.loc[mask, "niveau"] = self.profile.niveau
                df.to_csv(SESSION_CSV, index=False)
                print(f"[Memory] Niveau '{self.profile.niveau}' persisté dans le CSV ✓")
        except Exception as e:
            print(f"[Memory] ⚠️  Impossible de persister le niveau : {e}")

    # ══════════════════════════════════════════════════════════════════════════
    # STATUS
    # ══════════════════════════════════════════════════════════════════════════

    def print_status(self):
        labels = {
            "m1_formation": "Module 1 — Formation produit",
            "m1_evaluation": "Module 1 — QCM en cours",
            "m1_done": "Module 1 — Terminé",
            "m2_formation": "Module 2 — Argumentation",
            "m2_evaluation": "Module 2 — QCM en cours",
            "m2_done": "Module 2 — Terminé",
            "m3_medecin": "Module 3 — Simulation Médecin",
            "m3_pharmacien": "Module 3 — Simulation Pharmacien",
            "done": "Parcours terminé ✓",
        }
        voice_info = ""
        if self.mode_voix and self.voice:
            voice_info = f" | Alia parle : {'oui' if self.voice.is_speaking else 'non'}"
        print(f"\n[Status] {labels.get(self.mode, self.mode)}")
        print(f"[Status] Mode       : {'🎤 Voix' if self.mode_voix else '⌨️  Écrit'}{voice_info}")
        print(f"[Status] Simulation : {'🎬 Active (' + ('EXAMEN' if self.exam_mode else 'TRAINING') + ')' if self.simulation_active else 'inactive'}")
        print(f"[Status] Produit    : {self.current_product}")
        print(f"[Status] Niveau     : {self.profile.niveau}")
        print(f"[Status] Scores     : {self.scores_by_module}")
        print(f"[Status] Messages   : {len(self.conversation_history)}")
        print(f"[Status] Tours sim  : {self._sim_turn_count}\n")


# ══════════════════════════════════════════════════════════════════════════════
# SÉLECTION DU MODE
# ══════════════════════════════════════════════════════════════════════════════

def choose_mode() -> tuple:
    print("\n" + "═"*60)
    print("   ALIA — Bienvenue dans votre session de formation")
    print("═"*60)
    print("\nComment veux-tu interagir avec Alia ?\n")
    print("  [1] 🎤  Mode Voix   — VAD automatique + barge-in")
    print("  [2] ⌨️   Mode Écrit  — chat terminal classique")
    print()
    while True:
        choice = input("Ton choix (1 ou 2) : ").strip()
        if choice == "1":
            if not VOICE_ENGINE_AVAILABLE:
                print("⚠️  voice.py manquant → mode écrit")
                return False, WHISPER_MODEL
            print("\nModèle Whisper :")
            print("  [1] tiny   — ultra rapide")
            print("  [2] base   — rapide")
            print("  [3] small  — recommandé")
            print("  [4] medium — plus précis")
            m = input("Choix (1-4, Entrée = small) : ").strip()
            model_map = {"1": "tiny", "2": "base", "3": "small", "4": "medium"}
            whisper_model = model_map.get(m, "small")
            print(f"→ Whisper {whisper_model} sélectionné\n")
            return True, whisper_model
        elif choice == "2":
            return False, WHISPER_MODEL
        else:
            print("Tape 1 ou 2.")


# ══════════════════════════════════════════════════════════════════════════════
# COMMANDES
# ══════════════════════════════════════════════════════════════════════════════

def _is_command(text: str) -> Optional[str]:
    text_lower = text.lower().strip()
    if text_lower in VOICE_COMMANDS:
        return text_lower
    for cmd, variants in VOICE_COMMANDS.items():
        for v in variants:
            if v in text_lower:
                return cmd
    return None


def _handle_command(agent: AliaAgent, cmd: str):
    if cmd == "quit":
        agent.save_and_close()
        print("\nSession terminée. À bientôt !")
        sys.exit(0)
    elif cmd == "eval":
        print("\n[Alia] Évaluation...")
        agent._output(agent.trigger_eval())
    elif cmd == "next":
        print("\n[Alia] Module suivant...")
        agent._output(agent.trigger_next())
    elif cmd == "sim":
        agent.start_simulation(exam_mode=False)
    elif cmd == "exam":
        agent.start_simulation(exam_mode=True)
    elif cmd == "stop_sim":
        agent.stop_simulation()
    elif cmd == "save":
        agent.save_and_close()
    elif cmd == "status":
        agent.print_status()
    elif cmd == "history":
        print_delegue_history(agent.profile.delegue_id, agent.profile.name)


# ══════════════════════════════════════════════════════════════════════════════
# BOUCLE PRINCIPALE
# ══════════════════════════════════════════════════════════════════════════════

def run_interactive():
    mode_voix, whisper_model = choose_mode()
    agent = AliaAgent(mode_voix=mode_voix, whisper_model=whisper_model)

    print("\n" + "-"*60)
    if mode_voix:
        print("🎤 Mode voix actif")
        print("   → Parle naturellement, Alia détecte quand tu t'arrêtes")
        print("   → Tu peux l'interrompre en commençant à parler")
        print("   → Commandes : eval | next | sim | exam | stop_sim | quit")
    else:
        print("⌨️  Commandes : eval | next | sim | exam | stop_sim | save | status | history | quit")
    print("-"*60 + "\n")

    print("[Alia] Génération du message d'ouverture...")
    opening = agent.start_session()
    agent._output(opening, blocking=True)

    while True:
        try:
            if mode_voix and agent.voice:
                listen_start = time.time()
                text_fr, lang = agent.voice.listen()
                listen_duration = time.time() - listen_start

                if not text_fr:
                    continue

                # Analyse prosodique
                if agent.simulation_active and PROSODY_AVAILABLE and agent.prosody_analyzer:
                    try:
                        agent.prosody_analyzer.analyze_turn(
                            text=text_fr,
                            duration_s=listen_duration,
                            audio_path=agent._last_audio_path,
                        )
                    except Exception:
                        pass

                cmd = _is_command(text_fr)
                if cmd:
                    print(f"[Commande vocale] {cmd}")
                    _handle_command(agent, cmd)
                else:
                    print(f"\n👤 {agent.profile.name} : {text_fr}")
                    response = agent.respond(text_fr)
                    # Détecter qui parle: Alia hors rôle ou le personnage
                    if "[Alia - hors rôle]" in response:
                        label = "🤖 Alia"
                        response = response.replace("[Alia - hors rôle]", "").strip()
                    else:
                        label = agent._get_persona_label()
                    agent._output(response, blocking=False, role_label=label)

            else:
                # Mode écrit
                user_input = input(f"👤 {agent.profile.name}: ").strip()
                if not user_input:
                    continue
                cmd = _is_command(user_input)
                if cmd:
                    _handle_command(agent, cmd)
                else:
                    if agent.simulation_active and PROSODY_AVAILABLE and agent.prosody_analyzer:
                        try:
                            estimated_duration = len(user_input.split()) / 2.0
                            agent.prosody_analyzer.analyze_turn(
                                text=user_input,
                                duration_s=max(estimated_duration, 1.0),
                            )
                        except Exception:
                            pass
                    print(f"\n👤 {agent.profile.name} : {user_input}")
                    response = agent.respond(user_input)
                    # Détecter qui parle: Alia hors rôle ou le personnage
                    if "[Alia - hors rôle]" in response:
                        label = "🤖 Alia"
                        response = response.replace("[Alia - hors rôle]", "").strip()
                    else:
                        label = agent._get_persona_label()
                    agent._output(response, role_label=label)

        except (KeyboardInterrupt, EOFError):
            print("\n[Alia] Sauvegarde avant fermeture...")
            agent.save_and_close()
            break


if __name__ == "__main__":
    run_interactive()