"""
MoondreamCoach.py - Alia Vision Module v6 — Moondream API
═══════════════════════════════════════════════════════════════════════════════
Remplace VisionAnalyzer.py pour la partie analyse comportementale.

Architecture :
  - Moondream3 API (toutes les 4s) → 3 questions ciblées en parallèle :
      Q1 : Objets tenus (sandwich, téléphone, tasse, stylo...)
      Q2 : Posture (penché, droit, bras croisés...)
      Q3 : Regard (caméra, bas, côté...)
  - MediaPipe Holistic (continu, local) → métriques brutes posture/regard/mains
  - Output structuré par axe : {objects, posture, regard, emotion, voix_hint}
  - get_snapshot() → dict injecté dans le prompt Alia

Dépendances :
    pip install moondream opencv-python mediapipe numpy

Clé API :
    Mettre MOONDREAM_API_KEY dans le fichier .env
    Obtenir une clé gratuite : https://moondream.ai
"""

import cv2
import time
import threading
import numpy as np
import os
from collections import deque, Counter
from dataclasses import dataclass, field
from typing import Optional, Dict, List
from dotenv import load_dotenv

load_dotenv()
MOONDREAM_API_KEY = os.getenv("MOONDREAM_API_KEY", "")

# ── Moondream ──────────────────────────────────────────────────────────────────
MOONDREAM_AVAILABLE = False
_md_model = None

if MOONDREAM_API_KEY:
    try:
        from PIL import Image
        import moondream as md
        _md_model = md.vl(model="moondream3-preview", api_key=MOONDREAM_API_KEY)
        MOONDREAM_AVAILABLE = True
        print("[Vision] Moondream3 API ✓")
    except ImportError:
        print("[Vision] ⚠️  moondream non installé → pip install moondream pillow")
    except Exception as e:
        print(f"[Vision] ⚠️  Moondream init échoué : {e}")
else:
    print("[Vision] ⚠️  MOONDREAM_API_KEY manquant → pip install moondream + clé sur moondream.ai")

# ── MediaPipe ──────────────────────────────────────────────────────────────────
MP_AVAILABLE = False
try:
    import mediapipe as mp
    if hasattr(mp, "solutions") and hasattr(mp.solutions, "holistic"):
        MP_AVAILABLE = True
except ImportError:
    pass

# ── Config ─────────────────────────────────────────────────────────────────────
MOONDREAM_INTERVAL = 4.0        # secondes entre chaque analyse Moondream
EYE_CONTACT_THRESHOLD = 0.15
ALERT_INTERVAL_FRAMES = 250     # frames entre chaque alerte temps réel
CALIBRATION_SECONDS   = 5


# ══════════════════════════════════════════════════════════════════════════════
# STRUCTURES
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class FrameMetrics:
    timestamp:        float = 0.0
    eye_contact:      bool  = False
    smile:            bool  = False
    posture_open:     bool  = True
    hand_gesture:     str   = "unknown"
    face_detected:    bool  = False
    stress_intensity: float = 0.0


@dataclass
class VisionAxes:
    """Résultat structuré par axe — produit par Moondream toutes les 4s."""
    timestamp:        float = 0.0
    # Axe OBJET
    object_detected:  bool  = False
    object_desc:      str   = ""          # "tient un sandwich", "téléphone à la main"
    # Axe POSTURE
    posture_desc:     str   = ""          # "dos droit, épaules ouvertes" / "penché en avant"
    posture_ok:       bool  = True
    # Axe REGARD
    regard_desc:      str   = ""          # "regarde directement la caméra" / "regard vers le bas"
    regard_ok:        bool  = True
    # Axe GÉNÉRAL
    general_desc:     str   = ""          # description libre complémentaire
    raw_answers:      dict  = field(default_factory=dict)


@dataclass
class CalibrationProfile:
    baseline_eye:   float = 0.50
    baseline_smile: float = 0.20
    calibrated:     bool  = False


@dataclass
class TurnSnapshot:
    turn_number:       int   = 0
    timestamp:         float = 0.0
    eye_contact_ratio: float = 0.0
    smile_ratio:       float = 0.0
    posture_ratio:     float = 0.0
    hand_gesture:      str   = "unknown"
    axes:              Optional[VisionAxes] = None   # dernière analyse Moondream


@dataclass
class SessionReport:
    duration_seconds:   float = 0.0
    total_frames:       int   = 0
    frames_with_face:   int   = 0
    eye_contact_score:  float = 0.0
    smile_score:        float = 0.0
    posture_score:      float = 0.0
    gesture_score:      float = 0.0
    stress_score:       float = 0.0
    behavioral_score:   float = 0.0
    eye_contact_ratio:  float = 0.0
    smile_ratio:        float = 0.0
    turn_snapshots:     List[TurnSnapshot]  = field(default_factory=list)
    axes_history:       List[VisionAxes]    = field(default_factory=list)
    calibration:        Optional[CalibrationProfile] = None
    strengths:          list  = field(default_factory=list)
    weaknesses:         list  = field(default_factory=list)
    tips:               list  = field(default_factory=list)


# ══════════════════════════════════════════════════════════════════════════════
# FALLBACK OPENCV (si MediaPipe absent)
# ══════════════════════════════════════════════════════════════════════════════

class OpenCVFallback:
    def __init__(self):
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

    def analyze(self, frame) -> FrameMetrics:
        m = FrameMetrics(timestamp=time.time())
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        h, w = frame.shape[:2]
        faces = self.face_cascade.detectMultiScale(gray, 1.1, 4, minSize=(80, 80))
        if not len(faces):
            return m
        m.face_detected = True
        x, y, fw, fh = faces[0]
        cx = (x + fw / 2) / w
        cy = (y + fh / 2) / h
        m.eye_contact = ((cx - 0.5) ** 2 + (cy - 0.5) ** 2) ** 0.5 < 0.25
        m.posture_open = (fw * fh) / (w * h) > 0.02
        return m


# ══════════════════════════════════════════════════════════════════════════════
# MOONDREAM COACH — analyseur principal
# ══════════════════════════════════════════════════════════════════════════════

class MoondreamCoach:
    """
    Analyseur comportemental temps réel.
    Combine Moondream (compréhension de scène) + MediaPipe (métriques brutes).
    """

    def __init__(self, camera_index: int = 0, show_preview: bool = False):
        self.camera_index = camera_index
        self.show_preview = show_preview

        self._thread:  Optional[threading.Thread] = None
        self._running  = False
        self._lock     = threading.Lock()

        self._metrics_history: deque = deque(maxlen=600)
        self._axes_history:    List[VisionAxes] = []
        self._last_axes:       Optional[VisionAxes] = None
        self._realtime_alerts: deque = deque(maxlen=20)

        self._start_time:          float = 0.0
        self._last_moondream_time: float = 0.0
        self._last_hand_positions        = None
        self._frame_count:         int   = 0

        self._calibration = CalibrationProfile()
        self._calibrating = False
        self._calib_frames: List[FrameMetrics] = []

        self._turn_snapshots: List[TurnSnapshot] = []

        self._panel_running = False
        self._panel_thread: Optional[threading.Thread] = None

        # MediaPipe / fallback
        self._holistic     = None
        self._mp_holistic  = None
        self._fallback     = None
        self._use_holistic = False
        self._init_mediapipe()

        print("[Vision] MoondreamCoach v6 prêt ✓")

    # ── Init MediaPipe ─────────────────────────────────────────────────────────

    def _init_mediapipe(self):
        if not MP_AVAILABLE:
            self._fallback = OpenCVFallback()
            print("[Vision] Fallback OpenCV (MediaPipe absent)")
            return
        try:
            self._mp_holistic = mp.solutions.holistic
            self._holistic = self._mp_holistic.Holistic(
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
                model_complexity=0,
            )
            self._use_holistic = True
            print("[Vision] MediaPipe Holistic ✓")
        except Exception as e:
            print(f"[Vision] MediaPipe échoué ({e}) → fallback OpenCV")
            self._fallback = OpenCVFallback()

    def start_display_panel(self):
        """
        Lance un thread qui affiche les données vision en temps réel
        dans le terminal principal — proprement, sans spammer.
        Mise à jour toutes les 3s seulement si changement.
        """
        self._panel_running = True
        self._panel_thread = threading.Thread(target=self._display_loop, daemon=True)
        self._panel_thread.start()

    def _display_loop(self):
        """Affiche un résumé vision compact toutes les 3s pendant la simulation."""
        last_hash = ""
        while self._panel_running and self._running:
            time.sleep(3.0)
            with self._lock:
                axes = self._last_axes
                recent = list(self._metrics_history)[-60:]

            if not recent:
                continue

            face = [m for m in recent if m.face_detected]
            if not face:
                continue

            n = len(face)
            eye_pct   = int(sum(1 for m in face if m.eye_contact) / n * 100)
            smile_pct = int(sum(1 for m in face if m.smile) / n * 100)

            lines = [f"👁️ {eye_pct}%", f"😊 {smile_pct}%"]
            if axes:
                if axes.object_detected and axes.object_desc:
                    lines.append(f"🚨 OBJET: {axes.object_desc[:30]}")
                elif not axes.regard_ok and axes.regard_desc:
                    lines.append(f"👀 {axes.regard_desc[:35]}")
                elif not axes.posture_ok and axes.posture_desc:
                    lines.append(f"🪑 {axes.posture_desc[:35]}")

            summary = " | ".join(lines)
            if summary != last_hash:
                print(f"\n  📷 [Vision] {summary}")
                last_hash = summary

    def stop_display_panel(self):
        self._panel_running = False

    # ── Start / Stop ───────────────────────────────────────────────────────────

    def start(self):
        if self._running:
            return
        self._running    = True
        self._start_time = time.time()
        self._thread     = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        print("[Vision] 📷 Analyse démarrée")
        self._start_calibration()
        self.start_display_panel()

    def stop(self) -> SessionReport:
        self._running = False
        self.stop_display_panel()
        if self._thread:
            self._thread.join(timeout=3)
        report = self._build_report()
        print("[Vision] 📷 Analyse arrêtée")
        return report

    # ── Calibration ────────────────────────────────────────────────────────────

    def _start_calibration(self):
        self._calibrating  = True
        self._calib_frames = []
        print(f"[Vision] 🔧 Calibration {CALIBRATION_SECONDS}s — reste naturel...")

        def _end():
            time.sleep(CALIBRATION_SECONDS)
            self._finish_calibration()
        threading.Thread(target=_end, daemon=True).start()

    def _finish_calibration(self):
        self._calibrating = False
        face = [f for f in self._calib_frames if f.face_detected]
        if not face:
            print("[Vision] ⚠️  Calibration : pas de visage — seuils par défaut")
            return
        n = len(face)
        self._calibration = CalibrationProfile(
            baseline_eye   = round(sum(1 for f in face if f.eye_contact) / n, 2),
            baseline_smile = round(sum(1 for f in face if f.smile) / n, 2),
            calibrated     = True,
        )
        print(f"[Vision] ✅ Calibration OK — regard={int(self._calibration.baseline_eye*100)}%")

    # ── Boucle de capture ──────────────────────────────────────────────────────

    def _capture_loop(self):
        try:
            cap = cv2.VideoCapture(self.camera_index)
        except Exception as e:
            print(f"[Vision] ❌ VideoCapture : {e}")
            self._running = False
            return
        if not cap.isOpened():
            print(f"[Vision] ❌ Caméra {self.camera_index} inaccessible")
            self._running = False
            return
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        print(f"[Vision] Caméra {self.camera_index} ✓")

        while self._running:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.1)
                continue

            self._frame_count += 1
            metrics = FrameMetrics(timestamp=time.time())

            if self._use_holistic and self._holistic:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                metrics = self._analyze_holistic(rgb, frame, metrics)
            elif self._fallback:
                metrics = self._fallback.analyze(frame)

            now = time.time()

            # Moondream — toutes les MOONDREAM_INTERVAL secondes
            if MOONDREAM_AVAILABLE and (now - self._last_moondream_time) >= MOONDREAM_INTERVAL:
                self._last_moondream_time = now
                frame_copy = frame.copy()
                threading.Thread(
                    target=self._analyze_moondream_async,
                    args=(frame_copy,),
                    daemon=True,
                ).start()

            if self._calibrating:
                self._calib_frames.append(metrics)
            else:
                with self._lock:
                    self._metrics_history.append(metrics)

            if not self._calibrating and self._frame_count % ALERT_INTERVAL_FRAMES == 0:
                self._check_realtime_alerts()

            if self.show_preview:
                self._draw_overlay(frame, metrics)
                cv2.imshow("Alia Vision", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            time.sleep(0.033)

        cap.release()
        if self.show_preview:
            cv2.destroyAllWindows()

    # ── Moondream — 3 questions ciblées ───────────────────────────────────────

    def _analyze_moondream_async(self, frame):
        """
        Envoie 3 questions ciblées à Moondream en parallèle.
        Questions fermées + précises → bien meilleures réponses que description libre.
        """
        if not MOONDREAM_AVAILABLE or _md_model is None:
            return
        try:
            from PIL import Image as PILImage
            img = PILImage.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            axes = VisionAxes(timestamp=time.time())

            # Lancer les 3 questions en parallèle
            results = {}
            threads = []

            def _ask(key, question):
                try:
                    r = _md_model.query(img, question)
                    results[key] = r.get("answer", "").strip() if isinstance(r, dict) else str(r).strip()
                except Exception as e:
                    results[key] = ""

            questions = {
                "objects": (
                    "Is the person holding or touching any object? "
                    "Answer YES or NO first, then if YES describe the object in 5 words max "
                    "(example: YES — sandwich in left hand)."
                ),
                "posture": (
                    "Describe the person's posture in 8 words max. "
                    "Focus on: back straight or bent, shoulders open or crossed, "
                    "leaning forward or backward. Example: 'upright, shoulders open, slight lean forward'."
                ),
                "regard": (
                    "Where is the person looking? Answer ONE of: "
                    "CAMERA (direct eye contact), DOWN (looking down), "
                    "SIDE (looking sideways), AWAY (looking away). "
                    "Then add 5 words of context."
                ),
            }

            for key, q in questions.items():
                t = threading.Thread(target=_ask, args=(key, q), daemon=True)
                t.start()
                threads.append(t)

            # Attendre max 6s pour toutes les réponses
            for t in threads:
                t.join(timeout=6.0)

            # Parser les réponses
            axes.raw_answers = dict(results)

            # Axe OBJET
            obj_ans = results.get("objects", "").upper()
            if obj_ans.startswith("YES"):
                axes.object_detected = True
                # Extraire la description après le tiret
                parts = results["objects"].split("—", 1)
                axes.object_desc = parts[1].strip() if len(parts) > 1 else results["objects"]
            else:
                axes.object_detected = False
                axes.object_desc = ""

            # Axe POSTURE
            posture_ans = results.get("posture", "").lower()
            axes.posture_desc = results.get("posture", "")
            bad_posture_kw = ["bent", "slouch", "crossed", "hunched", "lean back", "penché", "croisé"]
            axes.posture_ok = not any(kw in posture_ans for kw in bad_posture_kw)

            # Axe REGARD
            regard_ans = results.get("regard", "").upper()
            axes.regard_desc = results.get("regard", "")
            if regard_ans.startswith("CAMERA"):
                axes.regard_ok = True
            else:
                axes.regard_ok = False

            with self._lock:
                self._last_axes = axes
                self._axes_history.append(axes)

            # Log discret — seulement si objet détecté ou problème notable
            if axes.object_detected:
                print(f"\n  🚨 [Vision] OBJET DÉTECTÉ : {axes.object_desc}")
            elif not axes.regard_ok:
                pass  # silencieux pour ne pas spammer

        except Exception as e:
            # Erreur quota ou réseau → silencieux
            if "429" in str(e) or "quota" in str(e).lower():
                pass
            else:
                print(f"[Vision] Moondream erreur : {e}")

    # ── MediaPipe Holistic ─────────────────────────────────────────────────────

    def _analyze_holistic(self, rgb, frame, metrics: FrameMetrics) -> FrameMetrics:
        try:
            results = self._holistic.process(rgb)
            if results.face_landmarks:
                metrics.face_detected = True
                lm = results.face_landmarks.landmark
                try:
                    ix = (lm[468].x + lm[473].x) / 2
                    iy = (lm[468].y + lm[473].y) / 2
                    metrics.eye_contact = ((ix - 0.5) ** 2 + (iy - 0.5) ** 2) ** 0.5 < EYE_CONTACT_THRESHOLD
                except IndexError:
                    nose = lm[1]
                    metrics.eye_contact = ((nose.x - 0.5) ** 2 + (nose.y - 0.5) ** 2) ** 0.5 < 0.18
                try:
                    mw = abs(lm[291].x - lm[61].x)
                    mh = abs(lm[13].y - lm[14].y) + 1e-6
                    metrics.smile = (mw / mh) > 4.0
                except IndexError:
                    pass
            if results.pose_landmarks:
                lm = results.pose_landmarks.landmark
                P  = self._mp_holistic.PoseLandmark
                try:
                    ls, rs = lm[P.LEFT_SHOULDER], lm[P.RIGHT_SHOULDER]
                    le, re = lm[P.LEFT_EAR],      lm[P.RIGHT_EAR]
                    metrics.posture_open = (abs(ls.y - rs.y) < 0.05 and
                                            abs((le.y + re.y) / 2 - (ls.y + rs.y) / 2) > 0.1)
                except Exception:
                    pass
                try:
                    lw = lm[P.LEFT_WRIST]; rw = lm[P.RIGHT_WRIST]
                    cur = np.array([lw.x, lw.y, rw.x, rw.y])
                    if self._last_hand_positions is not None:
                        pass  # hand movement calculé si besoin
                    self._last_hand_positions = cur
                except Exception:
                    pass
            metrics.hand_gesture = self._detect_hand_gesture(results)
        except Exception:
            pass
        return metrics

    def _detect_hand_gesture(self, results) -> str:
        try:
            left  = results.left_hand_landmarks
            right = results.right_hand_landmarks
            pose  = results.pose_landmarks
            if not left and not right:
                return "unknown"
            if pose:
                P  = self._mp_holistic.PoseLandmark
                lm = pose.landmark
                lw = lm[P.LEFT_WRIST]; rw = lm[P.RIGHT_WRIST]
                ls = lm[P.LEFT_SHOULDER]; rs = lm[P.RIGHT_SHOULDER]
                if lw.x > rs.x or rw.x < ls.x:
                    return "crossed"

            def is_open(hand_lm) -> bool:
                if not hand_lm:
                    return True
                lm = hand_lm.landmark
                tips = [8, 12, 16, 20]; mcps = [5, 9, 13, 17]
                return sum(1 for t, m in zip(tips, mcps) if lm[t].y < lm[m].y) >= 3

            return "open" if (is_open(left) or is_open(right)) else "closed"
        except Exception:
            return "unknown"

    # ══════════════════════════════════════════════════════════════════════════
    # GET_SNAPSHOT — injecté dans le prompt Alia à chaque tour
    # ══════════════════════════════════════════════════════════════════════════

    def get_snapshot(self, turn_number: int = 0) -> Dict:
        with self._lock:
            recent    = list(self._metrics_history)[-90:]
            last_axes = self._last_axes

        base = {"face_detected": False, "turn": turn_number}
        if not recent:
            return base

        face = [m for m in recent if m.face_detected]
        n    = len(face)
        if n == 0:
            return base

        eye_r     = sum(1 for m in face if m.eye_contact) / n
        smile_r   = sum(1 for m in face if m.smile)       / n
        posture_r = sum(1 for m in face if m.posture_open) / n
        gestures  = [m.hand_gesture for m in face if m.hand_gesture != "unknown"]
        dom_gest  = Counter(gestures).most_common(1)[0][0] if gestures else "unknown"

        calib = self._calibration
        snap  = TurnSnapshot(
            turn_number       = turn_number,
            timestamp         = time.time() - self._start_time,
            eye_contact_ratio = round(eye_r, 2),
            smile_ratio       = round(smile_r, 2),
            posture_ratio     = round(posture_r, 2),
            hand_gesture      = dom_gest,
            axes              = last_axes,
        )
        with self._lock:
            self._turn_snapshots.append(snap)

        result = {
            "turn":             turn_number,
            "face_detected":    True,
            "eye_contact_pct":  int(eye_r * 100),
            "eye_label":        self._eye_label(eye_r, calib),
            "smile_pct":        int(smile_r * 100),
            "posture_pct":      int(posture_r * 100),
            "posture_label":    "correcte" if posture_r >= 0.6 else "fermée",
            "hand_gesture":     dom_gest,
            "stress_intensity": 0.0,   # sans FER+, on se base sur Moondream
            "stress_label":     "non mesuré",
            "calibration_applied": calib.calibrated,
            # ── Axes Moondream ──────────────────────────────────────────────────
            "moondream_available": MOONDREAM_AVAILABLE,
            "object_detected":  False,
            "object_desc":      "",
            "posture_desc":     "",
            "regard_desc":      "",
            "posture_ok":       True,
            "regard_ok":        True,
        }

        if last_axes:
            result["object_detected"] = last_axes.object_detected
            result["object_desc"]     = last_axes.object_desc
            result["posture_desc"]    = last_axes.posture_desc
            result["posture_ok"]      = last_axes.posture_ok
            result["regard_desc"]     = last_axes.regard_desc
            result["regard_ok"]       = last_axes.regard_ok

        return result

    # ── Labels ────────────────────────────────────────────────────────────────

    def _eye_label(self, ratio: float, calib: CalibrationProfile) -> str:
        if calib.calibrated:
            rel = ratio / max(calib.baseline_eye, 0.01)
            if rel >= 0.9:  return "excellent"
            if rel >= 0.65: return "correct"
            if rel >= 0.40: return "insuffisant"
            return "très faible"
        if ratio >= 0.75: return "excellent"
        if ratio >= 0.50: return "correct"
        if ratio >= 0.30: return "insuffisant"
        return "très faible"

    # ── Alertes temps réel ───────────────────────────────────────────────────

    def _check_realtime_alerts(self):
        with self._lock:
            recent    = list(self._metrics_history)[-90:]
            last_axes = self._last_axes

        # Alerte objet — PRIORITÉ ABSOLUE
        if last_axes and last_axes.object_detected and last_axes.object_desc:
            self._emit_alert(f"🚨 Objet détecté : {last_axes.object_desc}")
            return

        face = [m for m in recent if m.face_detected]
        if not face:
            return
        n     = len(face)
        eye_r = sum(1 for m in face if m.eye_contact) / n
        smile = sum(1 for m in face if m.smile)       / n
        gest  = Counter(m.hand_gesture for m in face if m.hand_gesture != "unknown").most_common(1)
        dom_g = gest[0][0] if gest else "unknown"

        if last_axes and not last_axes.regard_ok:
            self._emit_alert(f"👁️  Regard : {last_axes.regard_desc}")
        elif eye_r < 0.25:
            self._emit_alert("👁️  Contact visuel faible — regarde la caméra")

        if last_axes and not last_axes.posture_ok:
            self._emit_alert(f"🪑 Posture : {last_axes.posture_desc}")

        if smile < 0.05:
            self._emit_alert("😐 Pense à sourire")

        if dom_g == "crossed":
            self._emit_alert("🤗 Bras croisés — posture défensive")

    def _emit_alert(self, msg: str):
        print(f"\n  ⚡ [Vision] {msg}")
        with self._lock:
            self._realtime_alerts.append({
                "time": round(time.time() - self._start_time, 1),
                "message": msg,
            })

    def _draw_overlay(self, frame, metrics: FrameMetrics):
        ok, bad = (0, 200, 0), (0, 0, 200)
        items = [
            (f"Eye: {'ok' if metrics.eye_contact else '!!'}", ok if metrics.eye_contact else bad),
            (f"Smile: {'yes' if metrics.smile else 'no'}", ok if metrics.smile else (255, 165, 0)),
            (f"Pose: {'ok' if metrics.posture_open else '!!'}", ok if metrics.posture_open else bad),
            (f"Hands: {metrics.hand_gesture}", bad if metrics.hand_gesture in ("crossed", "closed") else ok),
        ]
        with self._lock:
            axes = self._last_axes
        if axes and axes.object_detected:
            cv2.putText(frame, f"OBJ: {axes.object_desc[:40]}", (10, frame.shape[0] - 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 2)
        for i, (txt, col) in enumerate(items):
            cv2.putText(frame, txt, (10, 28 + i * 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55, col, 2)

    # ── Rapport final ─────────────────────────────────────────────────────────

    def _build_report(self) -> SessionReport:
        with self._lock:
            history      = list(self._metrics_history)
            axes_history = list(self._axes_history)
            turn_snaps   = list(self._turn_snapshots)

        report = SessionReport(
            duration_seconds = time.time() - self._start_time,
            total_frames     = len(history),
            axes_history     = axes_history,
            turn_snapshots   = turn_snaps,
            calibration      = self._calibration,
        )

        face = [m for m in history if m.face_detected]
        report.frames_with_face = len(face)
        if not face:
            report.behavioral_score = 5.0
            return report

        n         = len(face)
        eye_r     = sum(1 for m in face if m.eye_contact) / n
        smile_r   = sum(1 for m in face if m.smile)       / n
        posture_r = sum(1 for m in face if m.posture_open) / n
        gestures  = [m.hand_gesture for m in face if m.hand_gesture != "unknown"]
        crossed_r = sum(1 for g in gestures if g == "crossed") / max(len(gestures), 1)

        calib = self._calibration
        eye_score = (eye_r / max(calib.baseline_eye, 0.01)) * 7.0 if calib.calibrated else eye_r * 10
        report.eye_contact_score = round(min(10.0, eye_score), 1)
        report.smile_score       = round(smile_r * 10, 1)
        report.posture_score     = round(posture_r * 10, 1)
        report.stress_score      = 7.0   # neutre sans FER+
        report.eye_contact_ratio = round(eye_r, 2)
        report.smile_ratio       = round(smile_r, 2)

        # Pénalité si bras croisés fréquents
        gesture_score = 4.0 if crossed_r > 0.4 else (7.0 if crossed_r > 0.2 else 9.0)
        # Pénalité si objet détecté fréquemment
        obj_count = sum(1 for a in axes_history if a.object_detected)
        if obj_count >= 2:
            gesture_score = max(2.0, gesture_score - 2.0)
        report.gesture_score = round(gesture_score, 1)

        report.behavioral_score = round(
            report.eye_contact_score * 0.30 +
            report.posture_score     * 0.25 +
            report.stress_score      * 0.15 +
            report.smile_score       * 0.15 +
            report.gesture_score     * 0.15,
            1
        )
        report.strengths, report.weaknesses, report.tips = self._generate_feedback(
            report, crossed_r, obj_count, axes_history
        )
        return report

    def _generate_feedback(self, r: SessionReport, crossed_r: float,
                           obj_count: int, axes: List[VisionAxes]):
        s, w, t = [], [], []

        if r.eye_contact_score >= 7:
            s.append("Contact visuel naturel et soutenu")
        elif r.eye_contact_score < 4:
            w.append("Contact visuel insuffisant")
            t.append("Regarde le centre de la caméra 3s à chaque prise de parole")

        if r.smile_score >= 6:
            s.append("Bonne chaleur relationnelle")
        elif r.smile_score < 2:
            w.append("Peu de sourire — posture froide")
            t.append("Un sourire d'accueil fait une différence dès les premières secondes")

        if r.posture_score >= 7:
            s.append("Posture ouverte et professionnelle")
        elif r.posture_score < 4:
            w.append("Posture fermée détectée")
            t.append("Épaules en arrière, dos droit — ça se voit et ça influence l'interlocuteur")

        if obj_count >= 2:
            obj_descs = [a.object_desc for a in axes if a.object_detected][:3]
            w.append(f"Objets détectés pendant la simulation : {', '.join(obj_descs)}")
            t.append("Aucun objet en main pendant une visite — ça distrait et nuit au professionnalisme")

        if crossed_r > 0.4:
            w.append("Bras croisés fréquents — signal de fermeture")
            t.append("Mains visibles et ouvertes = signal de confiance inconscient")

        return s, w, t


# ══════════════════════════════════════════════════════════════════════════════
# FORMAT BILAN (compatible avec l'existant)
# ══════════════════════════════════════════════════════════════════════════════

def format_vision_report(report: SessionReport, content_score=None) -> str:
    lines = [
        "\n" + "═" * 60,
        "  BILAN COMPORTEMENTAL — ANALYSE VISUELLE",
        "═" * 60,
        f"\n⏱️  Durée simulation    : {int(report.duration_seconds)}s",
        f"📹 Frames avec visage  : {report.frames_with_face}/{report.total_frames}",
        "\n📊 SCORES COMPORTEMENTAUX (/ 10)",
        f"  👁️  Contact visuel  : {report.eye_contact_score:>4.1f}  ({int(report.eye_contact_ratio*100)}%)",
        f"  😊 Sourire         : {report.smile_score:>4.1f}  ({int(report.smile_ratio*100)}%)",
        f"  🪑 Posture         : {report.posture_score:>4.1f}",
        f"  🤝 Gestes/objets   : {report.gesture_score:>4.1f}",
        f"\n  ⭐ Score comportemental : {report.behavioral_score}/10",
    ]

    if content_score is not None:
        c10      = round(content_score / 10, 1)
        combined = round(report.behavioral_score * 0.4 + c10 * 0.6, 1)
        lines   += [f"  📚 Score contenu : {c10}/10", f"\n  🏆 SCORE GLOBAL  : {combined}/10"]

    # Objets détectés
    obj_list = [(a.timestamp, a.object_desc) for a in report.axes_history if a.object_detected]
    if obj_list:
        lines.append("\n🚨 OBJETS DÉTECTÉS (à éviter en visite)")
        for ts, desc in obj_list[:5]:
            lines.append(f"  [{ts:.0f}s] {desc}")

    # Tour par tour
    if report.turn_snapshots:
        lines.append("\n📍 MOMENTS CLÉS PAR RÉPLIQUE")
        for snap in report.turn_snapshots:
            flags = ""
            if snap.axes and snap.axes.object_detected:   flags += " 🚨objet"
            if snap.eye_contact_ratio < 0.35:             flags += " 👁️regard"
            if snap.hand_gesture == "crossed":            flags += " 🤐croisés"
            lines.append(
                f"  Tour {snap.turn_number:>2} | Regard:{int(snap.eye_contact_ratio*100):>3}% | "
                f"Sourire:{int(snap.smile_ratio*100):>3}% | Mains:{snap.hand_gesture}{flags}"
            )

    if report.strengths:
        lines.append("\n✅ POINTS FORTS")
        lines += [f"  • {s}" for s in report.strengths]
    if report.weaknesses:
        lines.append("\n⚠️  POINTS À AMÉLIORER")
        lines += [f"  • {w}" for w in report.weaknesses]
    if report.tips:
        lines.append("\n💡 CONSEILS")
        lines += [f"  → {t}" for t in report.tips]
    lines.append("\n" + "═" * 60)
    return "\n".join(lines)


# ── Test standalone ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    coach = MoondreamCoach(camera_index=0, show_preview=True)
    coach.start()
    try:
        for turn in range(1, 4):
            time.sleep(6)
            snap = coach.get_snapshot(turn_number=turn)
            print(f"\n=== Snapshot tour {turn} ===")
            for k, v in snap.items():
                print(f"  {k}: {v}")
    except KeyboardInterrupt:
        pass
    report = coach.stop()
    print(format_vision_report(report))