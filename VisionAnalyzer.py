"""
VisionAnalyzer.py - Alia Vision Module v6
═══════════════════════════════════════════════════════════════════════════════
CHANGEMENTS v6 vs v5 :
  - Claude Vision remplace Gemini Vision
      → Latence réduite (~2-3s vs 4-8s), pas de quota 429
      → Même prompt comportemental, même format de sortie
      → Analyse une frame toutes les CLAUDE_VISION_INTERVAL secondes
      → Utilise ANTHROPIC_API_KEY dans .env
  - MediaPipe toujours actif en local pour les métriques brutes (regard, sourire, posture)
  - FER+ / DeepFace conservés en fallback si pas de clé Claude

Dépendances :
    pip install opencv-python mediapipe numpy anthropic
    # FER+ en fallback optionnel : pip install fer
    # DeepFace en fallback optionnel : pip install deepface

Clé API :
    Mettre ANTHROPIC_API_KEY dans le fichier .env (même clé que pour l'agent si utilisé)
"""

import cv2
import time
import threading
import numpy as np
import os
import base64
from collections import deque, Counter
from dataclasses import dataclass, field
from typing import Optional, Dict, List
from dotenv import load_dotenv

load_dotenv()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# ── Claude Vision ──────────────────────────────────────────────────────────────
CLAUDE_VISION_AVAILABLE = False

if ANTHROPIC_API_KEY:
    try:
        import anthropic as _anthropic_lib
        _claude_client = _anthropic_lib.Anthropic(api_key=ANTHROPIC_API_KEY)
        CLAUDE_VISION_AVAILABLE = True
        print("[Vision] Claude Vision (claude-sonnet-4-20250514) ✓")
    except ImportError:
        print("[Vision] ⚠️  anthropic non installé → pip install anthropic")
    except Exception as e:
        print(f"[Vision] ⚠️  Claude Vision init échoué : {e}")
else:
    print("[Vision] ⚠️  ANTHROPIC_API_KEY manquant dans .env → analyse comportementale désactivée")

# Alias pour rétrocompatibilité avec agent.py (gemini_description reste le nom du champ)
GEMINI_AVAILABLE = CLAUDE_VISION_AVAILABLE

# ── FER+ (fallback émotion si pas Claude Vision) ──────────────────────────────
FER_AVAILABLE = False
if not CLAUDE_VISION_AVAILABLE:
    try:
        from fer import FER as FerDetector
        FER_AVAILABLE = True
        print("[Vision] Moteur émotion fallback : FER+ ✓")
    except ImportError:
        pass

# ── DeepFace (fallback si ni Claude Vision ni FER+) ───────────────────────────
DEEPFACE_AVAILABLE = False
if not CLAUDE_VISION_AVAILABLE and not FER_AVAILABLE:
    try:
        from deepface import DeepFace
        DEEPFACE_AVAILABLE = True
        print("[Vision] Moteur émotion fallback : DeepFace ✓")
    except ImportError:
        print("[Vision] ⚠️  Aucun moteur émotion disponible")

# ── MediaPipe ─────────────────────────────────────────────────────────────────
MEDIAPIPE_LEGACY = False
try:
    import mediapipe as mp
    if hasattr(mp, 'solutions') and hasattr(mp.solutions, 'face_mesh'):
        MEDIAPIPE_LEGACY = True
except ImportError:
    pass


# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════

CLAUDE_VISION_INTERVAL = 8.0   # secondes entre chaque analyse Claude Vision (toutes les 2 répliques ~)
EMOTION_INTERVAL      = 1.5    # secondes entre chaque analyse FER+ (fallback)
EYE_CONTACT_THRESHOLD = 0.15
ALERT_INTERVAL_FRAMES = 300
CALIBRATION_SECONDS   = 5

# Alias pour rétrocompatibilité interne
GEMINI_INTERVAL = CLAUDE_VISION_INTERVAL

# Prompt envoyé à Claude Vision pour chaque frame
CLAUDE_VISION_PROMPT = """Tu es un coach expert en vente pharmaceutique. Analyse cette image d'un délégué médical en simulation de visite.

Décris en 2-3 phrases courtes et directes :
1. Ce que fait physiquement la personne (objets tenus, posture, regard)
2. Son niveau d'attention et de professionnalisme apparent
3. Un signal comportemental précis (positif ou négatif)

IMPORTANT :
- Ne coupe jamais une phrase
- Réponds uniquement si tu es sûr
- Si tu n'es pas sûr, reformule de manière générale

Exemples de réponses attendues :
- "Le délégué regarde directement la caméra, posture droite, mains visibles et ouvertes. Présence professionnelle. Pas d'éléments distrayants visibles."
- "La personne tient un objet dans la main droite (semble être un téléphone), regard orienté vers le bas. Distraction visible, contact visuel absent."
- "Le délégué se penche légèrement en avant, sourire naturel, gestes des mains expressifs. Bonne énergie de vente."

Réponds en français, maximum 3 phrases, factuel et concis."""


# ══════════════════════════════════════════════════════════════════════════════
# STRUCTURES
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class FrameMetrics:
    timestamp:        float = 0.0
    eye_contact:      bool  = False
    smile:            bool  = False
    emotion:          str   = "neutral"
    emotion_scores:   dict  = field(default_factory=dict)
    stress_intensity: float = 0.0
    posture_open:     bool  = True
    hand_gesture:     str   = "unknown"
    hand_movement:    float = 0.0
    face_detected:    bool  = False


@dataclass
class CalibrationProfile:
    baseline_stress: float = 15.0
    baseline_eye:    float = 0.50
    baseline_smile:  float = 0.20
    baseline_emotion: str  = "neutral"
    calibrated:      bool  = False


@dataclass
class TurnVisionSnapshot:
    turn_number:         int   = 0
    timestamp:           float = 0.0
    eye_contact_ratio:   float = 0.0
    smile_ratio:         float = 0.0
    posture_ratio:       float = 0.0
    dominant_emotion:    str   = "neutral"
    stress_intensity:    float = 0.0
    face_coverage:       float = 0.0
    hand_gesture:        str   = "unknown"
    gemini_description:  str   = ""   # description textuelle Gemini


@dataclass
class SessionReport:
    duration_seconds:     float = 0.0
    total_frames:         int   = 0
    frames_with_face:     int   = 0
    eye_contact_score:    float = 0.0
    smile_score:          float = 0.0
    posture_score:        float = 0.0
    gesture_score:        float = 0.0
    stress_score:         float = 0.0
    emotion_score:        float = 0.0
    behavioral_score:     float = 0.0
    dominant_emotion:     str   = "neutral"
    emotion_distribution: dict  = field(default_factory=dict)
    stress_peaks:         int   = 0
    eye_contact_ratio:    float = 0.0
    smile_ratio:          float = 0.0
    strengths:            list  = field(default_factory=list)
    weaknesses:           list  = field(default_factory=list)
    tips:                 list  = field(default_factory=list)
    turn_snapshots:       List[TurnVisionSnapshot] = field(default_factory=list)
    calibration:          Optional[CalibrationProfile] = None
    gemini_descriptions:  List[str] = field(default_factory=list)  # toutes les descriptions


# ══════════════════════════════════════════════════════════════════════════════
# FALLBACK OPENCV
# ══════════════════════════════════════════════════════════════════════════════

class OpenCVFallbackDetector:
    def __init__(self):
        self.face_cascade  = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        self.smile_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_smile.xml')

    def analyze(self, frame) -> FrameMetrics:
        metrics = FrameMetrics(timestamp=time.time())
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        h, w = frame.shape[:2]
        faces = self.face_cascade.detectMultiScale(gray, 1.1, 4, minSize=(80, 80))
        if len(faces) == 0:
            return metrics
        metrics.face_detected = True
        x, y, fw, fh = faces[0]
        face_roi = gray[y:y+fh, x:x+fw]
        cx = (x + fw / 2) / w
        cy = (y + fh / 2) / h
        metrics.eye_contact = ((cx - 0.5)**2 + (cy - 0.5)**2) ** 0.5 < 0.25
        smiles = self.smile_cascade.detectMultiScale(
            face_roi, 1.8, 20, minSize=(int(fw * 0.25), int(fh * 0.1)))
        metrics.smile = len(smiles) > 0
        metrics.posture_open = (fw * fh) / (w * h) > 0.02
        return metrics


# ══════════════════════════════════════════════════════════════════════════════
# ANALYSEUR PRINCIPAL v5
# ══════════════════════════════════════════════════════════════════════════════

class VisionAnalyzer:

    def __init__(self, camera_index: int = 0, show_preview: bool = False):
        self.camera_index = camera_index
        self.show_preview = show_preview

        self._thread:  Optional[threading.Thread] = None
        self._running  = False
        self._lock     = threading.Lock()

        self._metrics_history: deque = deque(maxlen=600)
        self._realtime_alerts: deque = deque(maxlen=20)

        self._start_time:          float = 0.0
        self._last_emotion_time:   float = 0.0
        self._last_claude_time:    float = 0.0
        self._last_hand_positions        = None
        self._stress_peak_count:   int   = 0
        self._frame_count:         int   = 0

        self._calibration: CalibrationProfile = CalibrationProfile()
        self._calibrating  = False
        self._calib_frames: List[FrameMetrics] = []

        self._turn_snapshots:      List[TurnVisionSnapshot] = []
        self._gemini_descriptions: List[str] = []  # historique descriptions
        self._last_gemini_desc:    str = ""          # dernière description

        self._fer_detector = None  # initialisé dans le thread si besoin

        # MediaPipe init
        self._use_mediapipe  = False
        self._use_holistic   = False
        self._holistic       = None
        self._mp_holistic    = None
        self._face_mesh      = None
        self._mp_face_mesh   = None
        self._pose           = None
        self._mp_pose        = None
        self._fallback_det   = None

        self._init_mediapipe()
        print("[Vision] VisionAnalyzer v5 prêt ✓")

    def _init_mediapipe(self):
        if not MEDIAPIPE_LEGACY:
            self._fallback_det = OpenCVFallbackDetector()
            return
        try:
            self._mp_holistic = mp.solutions.holistic
            self._holistic = self._mp_holistic.Holistic(
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
                model_complexity=0,
            )
            self._use_holistic  = True
            self._use_mediapipe = True
            print("[Vision] MediaPipe Holistic (face+pose+mains) ✓")
        except Exception as e:
            try:
                self._mp_face_mesh = mp.solutions.face_mesh
                self._mp_pose      = mp.solutions.pose
                self._face_mesh = self._mp_face_mesh.FaceMesh(
                    max_num_faces=1, refine_landmarks=True,
                    min_detection_confidence=0.5, min_tracking_confidence=0.5)
                self._pose = self._mp_pose.Pose(
                    min_detection_confidence=0.5, min_tracking_confidence=0.5)
                self._use_mediapipe = True
                print(f"[Vision] MediaPipe FaceMesh+Pose (Holistic indispo : {e})")
            except Exception as e2:
                print(f"[Vision] MediaPipe échoué ({e2}) → fallback OpenCV")
                self._fallback_det = OpenCVFallbackDetector()

    # ── Start / Stop ───────────────────────────────────────────────────────────

    def start(self):
        if self._running:
            return
        self._running    = True
        self._start_time = time.time()
        self._thread     = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        print("[Vision] 📷 Analyse visuelle démarrée")
        self._start_calibration()

    def stop(self) -> SessionReport:
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        report = self._build_report()
        print("[Vision] 📷 Analyse arrêtée")
        return report

    # ── Calibration ────────────────────────────────────────────────────────────

    def _start_calibration(self):
        self._calibrating  = True
        self._calib_frames = []
        print(f"[Vision] 🔧 Calibration {CALIBRATION_SECONDS}s — reste naturel devant la caméra...")

        def _end():
            time.sleep(CALIBRATION_SECONDS)
            self._finish_calibration()
        threading.Thread(target=_end, daemon=True).start()

    def _finish_calibration(self):
        self._calibrating = False
        frames = self._calib_frames
        face   = [f for f in frames if f.face_detected]
        if not face:
            print("[Vision] ⚠️  Calibration : pas de visage détecté — seuils par défaut")
            return
        n = len(face)
        baseline_stress  = float(np.mean([f.stress_intensity for f in face]))
        baseline_eye     = sum(1 for f in face if f.eye_contact) / n
        baseline_smile   = sum(1 for f in face if f.smile) / n
        emotions         = [f.emotion for f in face]
        baseline_emotion = Counter(emotions).most_common(1)[0][0] if emotions else "neutral"

        self._calibration = CalibrationProfile(
            baseline_stress  = round(baseline_stress, 1),
            baseline_eye     = round(baseline_eye, 2),
            baseline_smile   = round(baseline_smile, 2),
            baseline_emotion = baseline_emotion,
            calibrated       = True,
        )
        print(f"[Vision] ✅ Calibration OK — stress neutre={baseline_stress:.0f}%, "
              f"regard={int(baseline_eye*100)}%, émotion={baseline_emotion}")

    # ── Boucle de capture ──────────────────────────────────────────────────────

    def _capture_loop(self):
        try:
            cap = cv2.VideoCapture(self.camera_index)
        except AttributeError as e:
            print(f"[Vision] ❌ cv2.VideoCapture indisponible : {e}")
            self._running = False
            return
        if not cap.isOpened():
            print(f"[Vision] ❌ Caméra {self.camera_index} inaccessible")
            self._running = False
            return
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        print(f"[Vision] Caméra {self.camera_index} ouverte ✓")

        # FER+ init dans le thread si pas Gemini
        if FER_AVAILABLE and not GEMINI_AVAILABLE:
            try:
                self._fer_detector = FerDetector(mtcnn=False)
            except Exception as e:
                print(f"[Vision] FER+ thread init échoué : {e}")

        self._last_frame_for_claude = None  # stocke la dernière frame pour Claude Vision

        while self._running:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.1)
                continue

            self._frame_count += 1
            metrics = FrameMetrics(timestamp=time.time())

            if self._use_mediapipe:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                metrics = self._analyze_holistic(rgb, frame, metrics) if self._use_holistic \
                    else self._analyze_mediapipe_legacy(rgb, frame, metrics)
            elif self._fallback_det:
                metrics = self._fallback_det.analyze(frame)

            now = time.time()

            # Claude Vision — toutes les CLAUDE_VISION_INTERVAL secondes (dans un thread séparé)
            if CLAUDE_VISION_AVAILABLE and (now - self._last_claude_time) >= CLAUDE_VISION_INTERVAL:
                self._last_claude_time = now
                frame_copy = frame.copy()
                threading.Thread(
                    target=self._analyze_claude_async,
                    args=(frame_copy,),
                    daemon=True
                ).start()

            # FER+ / DeepFace fallback (si pas Claude Vision)
            elif not CLAUDE_VISION_AVAILABLE and (now - self._last_emotion_time) >= EMOTION_INTERVAL:
                self._last_emotion_time = now
                metrics = self._analyze_emotion_fallback(frame, metrics)

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
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

            time.sleep(0.033)

        cap.release()
        if self.show_preview:
            cv2.destroyAllWindows()

    # ── Claude Vision ──────────────────────────────────────────────────────────

    def _analyze_claude_async(self, frame):
        """Envoie une frame à Claude Vision et stocke la description textuelle."""
        try:
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            image_b64 = base64.standard_b64encode(buffer.tobytes()).decode("utf-8")

            message = _claude_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=200,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": image_b64,
                                },
                            },
                            {"type": "text", "text": CLAUDE_VISION_PROMPT},
                        ],
                    }
                ],
            )

            desc = message.content[0].text.strip() if message.content else ""
            if desc:
                with self._lock:
                    self._last_gemini_desc = desc          # champ conservé pour rétrocompatibilité
                    self._gemini_descriptions.append(desc)
                # Log discret uniquement si distraction détectée
                if any(w in desc.lower() for w in ["distrait", "téléphone", "objet", "tient", "inattentif"]):
                    short = desc[:90].replace('\n', ' ')
                    print(f"\n  📱 [Vision] {short}...")

        except Exception as e:
            err_str = str(e)
            if "rate_limit" in err_str.lower() or "529" in err_str or "overloaded" in err_str.lower():
                global CLAUDE_VISION_INTERVAL, GEMINI_INTERVAL
                CLAUDE_VISION_INTERVAL = min(CLAUDE_VISION_INTERVAL * 1.5, 60.0)
                GEMINI_INTERVAL = CLAUDE_VISION_INTERVAL
                print(f"[Vision] Claude surchargé → intervalle ajusté à {CLAUDE_VISION_INTERVAL:.0f}s")
            # Autres erreurs : silencieux pour ne pas polluer la simulation

    # ── FER+ / DeepFace fallback ───────────────────────────────────────────────

    def _analyze_emotion_fallback(self, frame, metrics: FrameMetrics) -> FrameMetrics:
        if self._fer_detector is not None:
            return self._analyze_fer(frame, metrics)
        elif DEEPFACE_AVAILABLE:
            return self._analyze_deepface(frame, metrics)
        return metrics

    def _analyze_fer(self, frame, metrics: FrameMetrics) -> FrameMetrics:
        try:
            result = self._fer_detector.detect_emotions(frame)
            if not result:
                return metrics
            emotions = result[0].get("emotions", {})
            if not emotions:
                return metrics
            total = sum(emotions.values()) or 1.0
            norm  = {k: round(v/total*100, 1) for k, v in emotions.items()}
            metrics.emotion        = max(norm, key=norm.get)
            metrics.emotion_scores = norm
            raw_stress = norm.get("fear",0)+norm.get("angry",0)+norm.get("disgust",0)+norm.get("sad",0)
            adjusted   = raw_stress - self._calibration.baseline_stress
            metrics.stress_intensity = round(max(0.0, float(adjusted)), 1)
            if metrics.stress_intensity > 35:
                with self._lock:
                    self._stress_peak_count += 1
        except Exception:
            pass
        return metrics

    def _analyze_deepface(self, frame, metrics: FrameMetrics) -> FrameMetrics:
        try:
            r = DeepFace.analyze(frame, actions=["emotion"], enforce_detection=False, silent=True)
            if isinstance(r, list): r = r[0]
            emotions = r.get("emotion", {})
            norm     = {k: round(v,1) for k,v in emotions.items()}
            metrics.emotion        = r.get("dominant_emotion","neutral")
            metrics.emotion_scores = norm
            raw = norm.get("fear",0)+norm.get("angry",0)+norm.get("disgust",0)+norm.get("sad",0)
            metrics.stress_intensity = round(max(0.0, float(raw - self._calibration.baseline_stress)), 1)
            if metrics.stress_intensity > 35:
                with self._lock:
                    self._stress_peak_count += 1
        except Exception:
            pass
        return metrics

    # ── MediaPipe Holistic ─────────────────────────────────────────────────────

    def _analyze_holistic(self, rgb, frame, metrics: FrameMetrics) -> FrameMetrics:
        try:
            results = self._holistic.process(rgb)
            if results.face_landmarks:
                metrics.face_detected = True
                lm = results.face_landmarks.landmark
                try:
                    iris_x = (lm[468].x + lm[473].x) / 2
                    iris_y = (lm[468].y + lm[473].y) / 2
                    metrics.eye_contact = ((iris_x-0.5)**2 + (iris_y-0.5)**2)**0.5 < EYE_CONTACT_THRESHOLD
                except IndexError:
                    nose = lm[1]
                    metrics.eye_contact = ((nose.x-0.5)**2 + (nose.y-0.5)**2)**0.5 < 0.18
                try:
                    mouth_w = abs(lm[291].x - lm[61].x)
                    mouth_h = abs(lm[13].y  - lm[14].y) + 1e-6
                    metrics.smile = (mouth_w / mouth_h) > 4.0
                except IndexError:
                    pass
            if results.pose_landmarks:
                lm = results.pose_landmarks.landmark
                P  = self._mp_holistic.PoseLandmark
                try:
                    ls, rs = lm[P.LEFT_SHOULDER],  lm[P.RIGHT_SHOULDER]
                    le, re = lm[P.LEFT_EAR],       lm[P.RIGHT_EAR]
                    metrics.posture_open = abs(ls.y-rs.y) < 0.05 and \
                        abs((le.y+re.y)/2 - (ls.y+rs.y)/2) > 0.1
                except Exception:
                    pass
                try:
                    lw = lm[P.LEFT_WRIST]; rw = lm[P.RIGHT_WRIST]
                    cur = np.array([lw.x, lw.y, rw.x, rw.y])
                    if self._last_hand_positions is not None:
                        metrics.hand_movement = float(
                            np.linalg.norm(cur - self._last_hand_positions) * 1000)
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
                try:
                    lw = lm[P.LEFT_WRIST];  rw = lm[P.RIGHT_WRIST]
                    ls = lm[P.LEFT_SHOULDER]; rs = lm[P.RIGHT_SHOULDER]
                    if lw.x > rs.x or rw.x < ls.x:
                        return "crossed"
                except Exception:
                    pass
            def is_open(hand_lm) -> bool:
                if not hand_lm:
                    return True
                lm = hand_lm.landmark
                tips = [8, 12, 16, 20]; mcps = [5, 9, 13, 17]
                extended = sum(1 for t, m in zip(tips, mcps) if lm[t].y < lm[m].y)
                return extended >= 3
            if is_open(left) or is_open(right):
                return "open"
            return "closed"
        except Exception:
            return "unknown"

    def _analyze_mediapipe_legacy(self, rgb, frame, metrics: FrameMetrics) -> FrameMetrics:
        try:
            res = self._face_mesh.process(rgb)
            if res.multi_face_landmarks:
                metrics.face_detected = True
                lm = res.multi_face_landmarks[0].landmark
                try:
                    ix = (lm[468].x+lm[473].x)/2; iy = (lm[468].y+lm[473].y)/2
                    metrics.eye_contact = ((ix-0.5)**2+(iy-0.5)**2)**0.5 < EYE_CONTACT_THRESHOLD
                except IndexError:
                    pass
                try:
                    metrics.smile = abs(lm[291].x-lm[61].x)/(abs(lm[13].y-lm[14].y)+1e-6) > 4.0
                except IndexError:
                    pass
        except Exception:
            pass
        try:
            res = self._pose.process(rgb)
            if res.pose_landmarks:
                lm = res.pose_landmarks.landmark
                P  = self._mp_pose.PoseLandmark
                ls, rs = lm[P.LEFT_SHOULDER], lm[P.RIGHT_SHOULDER]
                le, re = lm[P.LEFT_EAR],      lm[P.RIGHT_EAR]
                metrics.posture_open = abs(ls.y-rs.y)<0.05 and abs((le.y+re.y)/2-(ls.y+rs.y)/2)>0.1
                lw = lm[P.LEFT_WRIST]; rw = lm[P.RIGHT_WRIST]
                cur = np.array([lw.x,lw.y,rw.x,rw.y])
                if self._last_hand_positions is not None:
                    metrics.hand_movement = float(np.linalg.norm(cur-self._last_hand_positions)*1000)
                self._last_hand_positions = cur
        except Exception:
            pass
        return metrics

    # ══════════════════════════════════════════════════════════════════════════
    # GET_SNAPSHOT — retourne tout ce qu'agent.py injecte dans le prompt
    # ══════════════════════════════════════════════════════════════════════════

    def get_snapshot(self, turn_number: int = 0) -> Dict:
        with self._lock:
            recent         = list(self._metrics_history)[-90:]
            gemini_desc    = self._last_gemini_desc

        base = {"face_detected": False, "turn": turn_number, "calibration_applied": False,
                "gemini_description": gemini_desc}

        if not recent:
            return base

        face = [m for m in recent if m.face_detected]
        n    = len(face)
        if n == 0:
            return base

        eye_r     = sum(1 for m in face if m.eye_contact) / n
        smile_r   = sum(1 for m in face if m.smile)       / n
        posture_r = sum(1 for m in face if m.posture_open) / n
        dominant  = Counter(m.emotion for m in face).most_common(1)[0][0] if face else "neutral"
        stress_vals = [m.stress_intensity for m in face]
        avg_stress  = round(float(np.mean(stress_vals)), 1) if stress_vals else 0.0
        gestures    = [m.hand_gesture for m in face if m.hand_gesture != "unknown"]
        dom_gest    = Counter(gestures).most_common(1)[0][0] if gestures else "unknown"
        emotion_dist = {}
        for m in reversed(face):
            if m.emotion_scores:
                emotion_dist = m.emotion_scores
                break

        snap = TurnVisionSnapshot(
            turn_number       = turn_number,
            timestamp         = time.time() - self._start_time,
            eye_contact_ratio = round(eye_r,     2),
            smile_ratio       = round(smile_r,   2),
            posture_ratio     = round(posture_r, 2),
            dominant_emotion  = dominant,
            stress_intensity  = avg_stress,
            face_coverage     = round(n / len(recent), 2),
            hand_gesture      = dom_gest,
            gemini_description = gemini_desc,
        )
        with self._lock:
            self._turn_snapshots.append(snap)

        calib = self._calibration
        return {
            "turn": turn_number,
            "face_detected": True,
            "calibration_applied": calib.calibrated,
            "face_coverage": snap.face_coverage,
            "eye_contact": snap.eye_contact_ratio,
            "eye_contact_pct": int(snap.eye_contact_ratio * 100),
            "eye_label": self._eye_label(eye_r, calib),
            "smile": snap.smile_ratio,
            "smile_pct": int(snap.smile_ratio * 100),
            "posture_open": snap.posture_ratio,
            "posture_pct": int(snap.posture_ratio * 100),
            "posture_label": self._posture_label(snap.posture_ratio),
            "dominant_emotion": dominant,
            "stress_intensity": avg_stress,
            "stress_label": self._stress_label(avg_stress),
            "emotion_dist": emotion_dist,
            "hand_gesture": dom_gest,
            "hand_gesture_label": self._gesture_label(dom_gest),
            "baseline_stress": calib.baseline_stress if calib.calibrated else None,
            "baseline_eye_pct": int(calib.baseline_eye * 100) if calib.calibrated else None,
            # ← NOUVEAU : description Gemini en langage naturel
            "gemini_description": gemini_desc,
        }

    def get_current_metrics(self) -> dict:
        return self.get_snapshot(turn_number=0)

    # ── Labels ────────────────────────────────────────────────────────────────

    def _eye_label(self, ratio: float, calib: CalibrationProfile) -> str:
        if calib.calibrated:
            rel = ratio / max(calib.baseline_eye, 0.01)
            if rel >= 0.9: return "excellent"
            if rel >= 0.65: return "correct"
            if rel >= 0.40: return "insuffisant"
            return "très faible"
        if ratio >= 0.75: return "excellent"
        if ratio >= 0.50: return "correct"
        if ratio >= 0.30: return "insuffisant"
        return "très faible"

    def _stress_label(self, intensity: float) -> str:
        if intensity < 10: return "détendu"
        if intensity < 25: return "légèrement tendu"
        if intensity < 45: return "tendu"
        return "très stressé"

    def _posture_label(self, ratio: float) -> str:
        if ratio >= 0.80: return "excellente"
        if ratio >= 0.60: return "correcte"
        if ratio >= 0.40: return "insuffisante"
        return "fermée"

    def _gesture_label(self, gesture: str) -> str:
        return {
            "open":    "gestes ouverts (positif)",
            "closed":  "mains fermées / crispées",
            "crossed": "bras croisés (posture défensive)",
            "unknown": "mains non visibles",
        }.get(gesture, "unknown")

    # ── Alertes ───────────────────────────────────────────────────────────────

    def _check_realtime_alerts(self):
        with self._lock:
            recent     = list(self._metrics_history)[-90:]
            gemini_desc = self._last_gemini_desc

        # Alerte Gemini en priorité si elle détecte quelque chose
        if gemini_desc and any(w in gemini_desc.lower() for w in
                                ["distrait", "téléphone", "objet", "regard vers le bas",
                                 "inattentif", "distraction"]):
            self._emit_alert(f"📱 Gemini: {gemini_desc[:80]}...")
            return

        face = [m for m in recent if m.face_detected]
        if not face:
            return
        n = len(face)
        eye_r     = sum(1 for m in face if m.eye_contact)  / n
        smile_r   = sum(1 for m in face if m.smile)        / n
        posture_r = sum(1 for m in face if m.posture_open) / n
        gestures  = [m.hand_gesture for m in face if m.hand_gesture != "unknown"]
        gest      = Counter(gestures).most_common(1)[0][0] if gestures else "unknown"
        stress_vals = [m.stress_intensity for m in face]
        avg_stress  = float(np.mean(stress_vals)) if stress_vals else 0.0

        if self._eye_label(eye_r, self._calibration) in ("insuffisant", "très faible"):
            self._emit_alert("👁️  Contact visuel faible — regarde la caméra")
        if avg_stress > 30:
            self._emit_alert("😟 Tension détectée — respire, tu maîtrises le sujet")
        if smile_r < 0.08:
            self._emit_alert("😐 Pense à sourire — ça met ton interlocuteur à l'aise")
        if posture_r < 0.4:
            self._emit_alert("🪑 Posture fermée — ouvre les épaules")
        if gest == "crossed":
            self._emit_alert("🤗 Bras croisés — adopte une posture plus ouverte")

    def _emit_alert(self, message: str):
        print(f"\n  ⚡ [Vision] {message}")
        with self._lock:
            self._realtime_alerts.append({"time": round(time.time()-self._start_time,1), "message": message})

    def _draw_overlay(self, frame, metrics: FrameMetrics):
        ok, bad = (0,200,0), (0,0,200)
        items = [
            (f"Eye: {'ok' if metrics.eye_contact else '!!'}", ok if metrics.eye_contact else bad),
            (f"Smile: {'yes' if metrics.smile else 'no'}", ok if metrics.smile else (255,165,0)),
            (f"Pose: {'ok' if metrics.posture_open else '!!'}", ok if metrics.posture_open else bad),
            (f"Hands: {metrics.hand_gesture}",
             bad if metrics.hand_gesture in ("crossed","closed") else ok),
        ]
        # Afficher la dernière description Gemini si disponible
        if self._last_gemini_desc:
            desc_short = self._last_gemini_desc[:60]
            cv2.putText(frame, f"Gemini: {desc_short}", (10, frame.shape[0]-15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 200, 255), 1)
        for i, (txt, col) in enumerate(items):
            cv2.putText(frame, txt, (10, 28+i*24), cv2.FONT_HERSHEY_SIMPLEX, 0.55, col, 2)

    # ── Bilan ─────────────────────────────────────────────────────────────────

    def _build_report(self) -> SessionReport:
        with self._lock:
            history             = list(self._metrics_history)
            stress_peaks        = self._stress_peak_count
            turn_snapshots      = list(self._turn_snapshots)
            gemini_descriptions = list(self._gemini_descriptions)

        report = SessionReport(
            duration_seconds    = time.time() - self._start_time,
            total_frames        = len(history),
            stress_peaks        = stress_peaks,
            turn_snapshots      = turn_snapshots,
            calibration         = self._calibration,
            gemini_descriptions = gemini_descriptions,
        )
        face = [m for m in history if m.face_detected]
        report.frames_with_face = len(face)
        if not face:
            report.behavioral_score = 5.0
            return report

        n = len(face)
        eye_r     = sum(1 for m in face if m.eye_contact) / n
        smile_r   = sum(1 for m in face if m.smile)       / n
        posture_r = sum(1 for m in face if m.posture_open) / n
        movements = [m.hand_movement for m in face if m.hand_movement > 0]
        avg_mv    = float(np.mean(movements)) if movements else 0.0
        gestures  = [m.hand_gesture for m in face if m.hand_gesture != "unknown"]
        dom_gest  = Counter(gestures).most_common(1)[0][0] if gestures else "unknown"
        crossed_r = sum(1 for g in gestures if g=="crossed") / max(len(gestures),1)
        emotions  = [m.emotion for m in face]
        ecounts   = Counter(emotions)
        dominant  = ecounts.most_common(1)[0][0] if ecounts else "neutral"
        neg_count = sum(ecounts.get(e,0) for e in ["fear","angry","sad","disgust"])
        stress_ratio = neg_count / max(len(emotions),1)

        calib = self._calibration
        eye_score = (eye_r / max(calib.baseline_eye, 0.01)) * 7.0 if calib.calibrated else eye_r * 10
        report.eye_contact_score = round(min(10.0, eye_score), 1)
        report.smile_score       = round(smile_r * 10, 1)
        report.posture_score     = round(posture_r * 10, 1)
        report.gesture_score     = round(self._score_gesture(avg_mv, crossed_r), 1)
        report.stress_score      = round((1 - stress_ratio) * 10, 1)
        report.emotion_score     = {"happy":10,"neutral":7,"surprise":6,"sad":4,"fear":3,"angry":2,"disgust":2}.get(dominant,5.0)
        report.dominant_emotion  = dominant
        report.emotion_distribution = dict(ecounts)
        report.eye_contact_ratio = round(eye_r, 2)
        report.smile_ratio       = round(smile_r, 2)
        report.behavioral_score  = round(
            report.eye_contact_score*0.25 + report.posture_score*0.20 +
            report.stress_score*0.20 + report.smile_score*0.15 +
            report.gesture_score*0.10 + report.emotion_score*0.10, 1)
        report.strengths, report.weaknesses, report.tips = self._generate_feedback(report, dom_gest, crossed_r)
        return report

    def _score_gesture(self, avg_mv: float, crossed_ratio: float) -> float:
        if crossed_ratio > 0.4: return 3.0
        if avg_mv < 5:   return 4.0
        if avg_mv < 15:  return 7.0
        if avg_mv < 40:  return 10.0
        if avg_mv < 70:  return 7.0
        return 4.0

    def _generate_feedback(self, r: SessionReport, dominant_gest: str, crossed_ratio: float):
        s, w, t = [], [], []
        if r.eye_contact_score >= 7:
            s.append("Excellent contact visuel — tu as regardé ton interlocuteur naturellement")
        elif r.eye_contact_score >= 4:
            w.append("Contact visuel insuffisant"); t.append("Regarde le centre de la caméra 3s à chaque prise de parole")
        else:
            w.append("Contact visuel très faible"); t.append("Maintiens le regard 3 secondes avant de baisser les yeux")
        if r.smile_score >= 6:
            s.append("Bonne chaleur relationnelle — tu souris naturellement")
        elif r.smile_score < 3:
            w.append("Peu de sourire — tu parais froid ou stressé")
            t.append("Un sourire d'accueil met le médecin en confiance dès le début")
        if r.posture_score >= 7:
            s.append("Posture ouverte et professionnelle")
        elif r.posture_score < 4:
            w.append("Posture fermée"); t.append("Épaules en arrière, dos droit")
        if r.stress_score >= 8:
            s.append("Tu sembles détendu et maître de ta présentation")
        elif r.stress_score < 5:
            w.append(f"Stress visible ({r.stress_peaks} pics détectés au-delà de ta baseline)")
            t.append("3 respirations profondes avant chaque visite régulent le stress")
        if crossed_ratio > 0.4:
            w.append("Bras croisés fréquents — posture défensive")
            t.append("Garde les mains visibles et ouvertes — c'est le signal de confiance le plus puissant")
        elif dominant_gest == "open":
            s.append("Gestes ouverts — tu projettes de la transparence et de la confiance")
        # Ajouter les observations Gemini dans le feedback si disponibles
        if r.gemini_descriptions:
            last_desc = r.gemini_descriptions[-1]
            if any(w in last_desc.lower() for w in ["distrait", "téléphone", "objet", "inattentif"]):
                w.append(f"Distraction détectée par Gemini Vision : {last_desc[:100]}")
        return s, w, t


# ══════════════════════════════════════════════════════════════════════════════
# FORMAT BILAN
# ══════════════════════════════════════════════════════════════════════════════

def format_vision_report(report: SessionReport, content_score=None) -> str:
    calib_note = ""
    if report.calibration and report.calibration.calibrated:
        calib_note = f" — calibré (baseline stress={report.calibration.baseline_stress:.0f}%)"

    lines = [
        "\n" + "═"*60,
        "  BILAN COMPORTEMENTAL — ANALYSE VISUELLE",
        "═"*60,
        f"\n⏱️  Durée simulation    : {int(report.duration_seconds)}s",
        f"📹 Frames avec visage  : {report.frames_with_face}/{report.total_frames}{calib_note}",
        "\n📊 SCORES COMPORTEMENTAUX (/ 10)",
        f"  👁️  Contact visuel  : {report.eye_contact_score:>4.1f}  ({int(report.eye_contact_ratio*100)}%)",
        f"  😊 Sourire         : {report.smile_score:>4.1f}  ({int(report.smile_ratio*100)}%)",
        f"  🪑 Posture         : {report.posture_score:>4.1f}",
        f"  🤝 Gestes mains    : {report.gesture_score:>4.1f}",
        f"  😌 Sérénité        : {report.stress_score:>4.1f}  ({report.stress_peaks} pics)",
        f"  🎭 Émotion dominante: {report.dominant_emotion}",
        f"\n  ⭐ Score comportemental : {report.behavioral_score}/10",
    ]
    if content_score is not None:
        c10 = round(content_score/10, 1)
        combined = round(report.behavioral_score*0.4 + c10*0.6, 1)
        lines += [f"  📚 Score contenu : {c10}/10", f"\n  🏆 SCORE GLOBAL  : {combined}/10"]

    # Observations Claude Vision
    if report.gemini_descriptions:
        lines.append("\n🤖 OBSERVATIONS CLAUDE VISION (analyse comportementale)")
        for i, desc in enumerate(report.gemini_descriptions[-5:], 1):
            lines.append(f"  [{i}] {desc}")

    if report.turn_snapshots:
        lines.append("\n📍 MOMENTS CLÉS PAR RÉPLIQUE")
        for s in report.turn_snapshots:
            flags = ""
            if s.stress_intensity > 25:    flags += " ⚠️stress"
            if s.eye_contact_ratio < 0.35: flags += " 👁️regard"
            if s.hand_gesture == "crossed": flags += " 🤐bras croisés"
            if s.gemini_description:       flags += " 🤖gemini"
            lines.append(
                f"  Tour {s.turn_number:>2} | Regard:{int(s.eye_contact_ratio*100):>3}% | "
                f"Sourire:{int(s.smile_ratio*100):>3}% | Stress:{s.stress_intensity:>4.0f}% | "
                f"Mains:{s.hand_gesture} | {s.dominant_emotion}{flags}"
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
    lines.append("\n" + "═"*60)
    return "\n".join(lines)


if __name__ == "__main__":
    analyzer = VisionAnalyzer(camera_index=0, show_preview=True)
    analyzer.start()
    try:
        time.sleep(8)
        snap = analyzer.get_snapshot(turn_number=1)
        print("\nSnapshot tour 1 :", snap)
        time.sleep(12)
    except KeyboardInterrupt:
        pass
    report = analyzer.stop()
    print(format_vision_report(report, content_score=75))