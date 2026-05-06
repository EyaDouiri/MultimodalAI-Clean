"""
voice.py - Alia Voice Engine v3
Barge-in réel : micro toujours actif en arrière-plan.
Dès que tu parles pendant qu'Alia parle → elle s'arrête immédiatement.

Dépendances :
    pip install openai-whisper sounddevice numpy edge-tts pygame webrtcvad
"""

import time
import threading
import asyncio
import tempfile
import os
import uuid
import queue
import numpy as np
from typing import Optional, Tuple

try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False

try:
    import sounddevice as sd
    SD_AVAILABLE = True
except ImportError:
    SD_AVAILABLE = False

try:
    import webrtcvad
    VAD_AVAILABLE = True
except ImportError:
    VAD_AVAILABLE = False

try:
    import edge_tts
    EDGETTS_AVAILABLE = True
except ImportError:
    EDGETTS_AVAILABLE = False

try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False

try:
    from deep_translator import GoogleTranslator
    TRANSLATOR_AVAILABLE = True
except ImportError:
    TRANSLATOR_AVAILABLE = False

# ── Config ─────────────────────────────────────────────────────────────────
SAMPLE_RATE      = 16000
FRAME_DURATION   = 30       # ms — requis par webrtcvad
VAD_MODE         = 3        # 0=permissif, 3=agressif
SILENCE_DURATION = 1.2      # secondes de silence → fin de parole
MAX_DURATION     = 30       # secondes max par énoncé
MIN_SPEECH_MS    = 400      # ms min de parole réelle pour déclencher transcription

# Barge-in : 10 frames = ~300ms parole continue — filtre oiseaux/bruits ponctuels
BARGE_IN_FRAMES  = 10

# Seuils RMS (sans webrtcvad)
RMS_SPEECH_THRESHOLD  = 0.038   # écoute normale  (était 0.018)
RMS_BARGEIN_THRESHOLD = 0.055   # barge-in strict

VOICE_MAP = {
    "fr": {
        "alia":      "fr-FR-DeniseNeural",   # Alia — coach féminine (voix claire et directe)
        "doctor":    "fr-FR-HenriNeural",    # Dr. Karim — voix masculine médecin
        "pharmacien":"fr-BE-CharlineNeural", # Mme Sonia — voix féminine différente d'Alia (accent belge, chaleureux)
        "delegate":  "fr-FR-VivienneNeural"  # délégué — 3ème voix féminine si besoin
    },
    "en": {
        "alia":      "en-US-JennyNeural",
        "doctor":    "en-US-GuyNeural",
        "pharmacien":"en-US-AriaNeural",
        "delegate":  "en-US-JennyNeural"
    }
}


# ════════════════════════════════════════════════════════════════════════════
# SIMPLE TRANSLATOR — Mode de traduction sans voix
# (Utilisé en mode web avec mode_voix=False — pour garder le système multilingue)
# ════════════════════════════════════════════════════════════════════════════

class SimpleTranslator:
    """
    Traduction multilingue légère — SANS micro, micro TTS, VAD, barge-in.
    Utilisé quand mode_voix=False mais on veut garder la détection/traduction de langue.
    """
    def __init__(self):
        self.delegue_lang = "fr"  # Langue détectée du délégué
    
    def _to_french(self, text: str, lang: str) -> str:
        """Traduit du langage du délégué vers le français."""
        if lang == "fr" or not text or not TRANSLATOR_AVAILABLE:
            return text
        try:
            return GoogleTranslator(source=lang, target="fr").translate(text)
        except Exception as e:
            print(f"[Translator] Erreur traduction {lang}→fr : {e}")
            return text
    
    def _from_french(self, text: str, lang: str) -> str:
        """Traduit du français vers la langue du délégué."""
        if lang == "fr" or not text or not TRANSLATOR_AVAILABLE:
            return text
        try:
            return GoogleTranslator(source="fr", target=lang).translate(text)
        except Exception as e:
            print(f"[Translator] Erreur traduction fr→{lang} : {e}")
            return text


class VoiceEngine:
    """
    Moteur voix avec barge-in réel.

    Architecture :
      - Thread micro TOUJOURS actif (même quand Alia parle)
      - Dès que VAD détecte parole pendant TTS → interrupt immédiat
      - Après interrupt → enregistre l'énoncé complet → transcrit
    """

    def __init__(self, whisper_model: str = "small"):
        self.whisper_model_name = whisper_model
        self._whisper           = None
        self.delegue_lang       = "fr"

        # TTS state
        self.is_speaking        = False
        self._stop_tts          = threading.Event()
        self._tts_thread: Optional[threading.Thread] = None

        # Micro continu
        self._mic_queue         = queue.Queue()
        self._mic_thread: Optional[threading.Thread] = None
        self._mic_running       = False

        # Signal : barge-in détecté pendant TTS
        self._barge_in_event    = threading.Event()

        # Pygame
        self._pygame_ok         = False

        self._init_whisper()
        self._init_pygame()
        self._start_mic_stream()

    # ── Init ───────────────────────────────────────────────────────────────────

    def _init_whisper(self):
        if not WHISPER_AVAILABLE:
            print("[Voice] ⚠️  whisper manquant → pip install openai-whisper")
            return
        print(f"[Voice] Chargement Whisper ({self.whisper_model_name})...")
        self._whisper = whisper.load_model(self.whisper_model_name)
        print(f"[Voice] Whisper {self.whisper_model_name} ✓")

    def _init_pygame(self):
        if not PYGAME_AVAILABLE:
            return
        try:
            pygame.mixer.pre_init(44100, -16, 2, 512)
            pygame.mixer.init()
            self._pygame_ok = True
        except Exception as e:
            print(f"[Voice] pygame init échoué : {e}")

    # ── Micro continu ──────────────────────────────────────────────────────────

    def _start_mic_stream(self):
        """Lance le thread micro en arrière-plan — tourne toujours."""
        if not SD_AVAILABLE:
            return
        self._mic_running = True
        self._mic_thread  = threading.Thread(target=self._mic_loop, daemon=True)
        self._mic_thread.start()

    def _mic_loop(self):
        """
        Capture audio en continu et met les frames dans _mic_queue.
        Tourne même pendant que Alia parle → permet le barge-in.
        """
        frame_samples = int(SAMPLE_RATE * FRAME_DURATION / 1000)

        def callback(indata, frames, time_info, status):
            pcm = (indata[:, 0] * 32767).astype(np.int16).tobytes()
            self._mic_queue.put(pcm)

        try:
            with sd.InputStream(
                samplerate=SAMPLE_RATE, channels=1,
                dtype='float32', blocksize=frame_samples,
                callback=callback,
            ):
                while self._mic_running:
                    time.sleep(0.1)
        except Exception as e:
            print(f"[Voice] Erreur micro : {e}")

    def _get_vad(self):
        if VAD_AVAILABLE:
            try:
                return webrtcvad.Vad(VAD_MODE)
            except Exception:
                pass
        return None

    def _is_speech_rms(self, pcm: bytes) -> bool:
        """Fallback amplitude si webrtcvad absent."""
        arr = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32767.0
        return float(np.sqrt(np.mean(arr**2))) > RMS_SPEECH_THRESHOLD

    def _is_speech(self, vad, pcm: bytes) -> bool:
        if vad:
            try:
                frame_bytes = int(SAMPLE_RATE * FRAME_DURATION / 1000) * 2
                return vad.is_speech(pcm[:frame_bytes], SAMPLE_RATE)
            except Exception:
                pass
        return self._is_speech_rms(pcm)

    # ── LISTEN ────────────────────────────────────────────────────────────────

    def listen(self) -> Tuple[str, str]:
        """
        Attend que tu parles, enregistre jusqu'au silence, transcrit.
        Si Alia parle → barge-in automatique dès que tu commences.
        """
        if not WHISPER_AVAILABLE or self._whisper is None:
            return "", "fr"

        vad            = self._get_vad()
        audio_frames   = []
        silent_frames  = 0
        speech_frames  = 0
        is_recording   = False
        pre_buffer     = []

        frame_samples    = int(SAMPLE_RATE * FRAME_DURATION / 1000)
        silence_trigger  = int(SILENCE_DURATION * 1000 / FRAME_DURATION)
        min_speech_f     = int(MIN_SPEECH_MS / FRAME_DURATION)
        max_frames       = int(MAX_DURATION * 1000 / FRAME_DURATION)
        pre_buffer_size  = int(300 / FRAME_DURATION)

        # Vider la queue (frames accumulées pendant TTS)
        while not self._mic_queue.empty():
            try:
                self._mic_queue.get_nowait()
            except queue.Empty:
                break

        self._barge_in_event.clear()
        print("🎤 En attente...", end="", flush=True)

        frame_count = 0
        while frame_count < max_frames:
            try:
                pcm = self._mic_queue.get(timeout=1.0)
            except queue.Empty:
                continue

            frame_count += 1
            speech = self._is_speech(vad, pcm)
            frame_f = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32767.0

            if not is_recording:
                pre_buffer.append(frame_f)
                if len(pre_buffer) > pre_buffer_size:
                    pre_buffer.pop(0)
                if speech:
                    is_recording = True
                    speech_frames += 1
                    audio_frames.extend(pre_buffer)
                    audio_frames.append(frame_f)
                    print(" parole...", end="", flush=True)
            else:
                audio_frames.append(frame_f)
                if speech:
                    speech_frames += 1
                    silent_frames  = 0
                else:
                    silent_frames += 1
                    if silent_frames >= silence_trigger and speech_frames >= min_speech_f:
                        print(" ✓")
                        break

        if not audio_frames or speech_frames < min_speech_f:
            print()
            return "", "fr"

        return self._transcribe(np.concatenate(audio_frames))

    def _transcribe(self, audio: np.ndarray) -> Tuple[str, str]:
        try:
            result = self._whisper.transcribe(audio, fp16=False)
            text   = result["text"].strip()
            lang   = result.get("language", "fr")
            self.delegue_lang = lang
            print(f"[STT] ({lang}): {text}")
            return self._to_french(text, lang), lang
        except Exception as e:
            print(f"[Voice] Whisper erreur : {e}")
            return "", "fr"

    # ── BARGE-IN WATCHER ─────────────────────────────────────────────────────

    def _is_speech_bargein(self, vad, pcm: bytes) -> bool:
        """Seuil strict barge-in — filtre oiseaux et bruits ambiants courts."""
        if vad:
            try:
                frame_bytes = int(SAMPLE_RATE * FRAME_DURATION / 1000) * 2
                return vad.is_speech(pcm[:frame_bytes], SAMPLE_RATE)
            except Exception:
                pass
        arr = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32767.0
        return float(np.sqrt(np.mean(arr**2))) > RMS_BARGEIN_THRESHOLD

    def _barge_in_watcher(self):
        """
        Thread actif PENDANT que Alia parle.
        Nécessite 10 frames consécutives (~300ms) de parole réelle.
        Filtre les bruits ponctuels : oiseaux, voitures, bruit de rue.
        Reset progressif : une micro-pause dans la voix ne remet pas à zéro.
        """
        vad           = self._get_vad()
        consec_speech = 0

        # Attendre 1.5s avant de surveiller — évite que le son de l'enceinte
        # au démarrage du TTS soit détecté comme barge-in
        import time as _t
        _t.sleep(1.5)

        while self.is_speaking:
            try:
                pcm = self._mic_queue.get(timeout=0.05)
            except queue.Empty:
                continue

            if self._is_speech_bargein(vad, pcm):
                consec_speech += 1
                if consec_speech >= BARGE_IN_FRAMES:
                    print("\n🎤 [Barge-in] Tu as interrompu Alia")
                    self._barge_in_event.set()
                    self.interrupt()
                    break
            else:
                # Reset progressif (pas binaire) : tolère les micro-pauses vocales
                consec_speech = max(0, consec_speech - 2)

        # ── SPEAK ────────────────────────────────────────────────────────────────

    def speak(self, text_fr: str, role: str = "alia", blocking: bool = False):
        """
        Synthétise et joue le texte.
        Lance un watcher en parallèle pour détecter le barge-in.
        """
        if not EDGETTS_AVAILABLE:
            return

        self.interrupt()
        time.sleep(0.03)
        self._stop_tts.clear()
        self._barge_in_event.clear()

        lang  = self.delegue_lang
        text  = self._from_french(text_fr, lang)
        voice = VOICE_MAP.get(lang, {}).get(role, "fr-FR-DeniseNeural")

        self._tts_thread = threading.Thread(
            target=self._speak_worker, args=(text, voice), daemon=True
        )
        self._tts_thread.start()

        # Lancer le barge-in watcher en parallèle
        watcher = threading.Thread(target=self._barge_in_watcher, daemon=True)
        watcher.start()

        if blocking:
            self._tts_thread.join()

    def _speak_worker(self, text: str, voice: str):
        self.is_speaking = True
        tmp_path = os.path.join(
            tempfile.gettempdir(), f"alia_{uuid.uuid4().hex[:8]}.mp3"
        )
        try:
            # Synthèse
            asyncio.run(self._synthesize(text, voice, tmp_path))

            # Lecture (si pas encore interrompu)
            if not self._stop_tts.is_set():
                self._play(tmp_path)
        except Exception as e:
            print(f"[TTS] Erreur : {e}")
        finally:
            self.is_speaking = False
            # Libérer + supprimer le fichier
            try:
                if PYGAME_AVAILABLE and self._pygame_ok:
                    pygame.mixer.music.unload()
            except Exception:
                pass
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass

    async def _synthesize(self, text: str, voice: str, path: str):
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(path)

    def _play(self, path: str):
        if not PYGAME_AVAILABLE or not self._pygame_ok:
            return
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                if self._stop_tts.is_set():
                    pygame.mixer.music.stop()
                    break
                time.sleep(0.05)   # polling 50ms — réactivité barge-in
        except Exception as e:
            print(f"[TTS] Erreur lecture : {e}")

    def interrupt(self):
        """Coupe Alia immédiatement."""
        if self.is_speaking:
            self._stop_tts.set()
            if PYGAME_AVAILABLE and self._pygame_ok:
                try:
                    pygame.mixer.music.stop()
                except Exception:
                    pass
            self.is_speaking = False

    # ── Traduction ────────────────────────────────────────────────────────────

    def _to_french(self, text: str, lang: str) -> str:
        if lang == "fr" or not text or not TRANSLATOR_AVAILABLE:
            return text
        try:
            return GoogleTranslator(source=lang, target="fr").translate(text)
        except Exception:
            return text

    def _from_french(self, text: str, lang: str) -> str:
        if lang == "fr" or not text or not TRANSLATOR_AVAILABLE:
            return text
        try:
            return GoogleTranslator(source="fr", target=lang).translate(text)
        except Exception:
            return text