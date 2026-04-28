"""
demo_simulation.py — Alia Simulation Demo (fichier standalone)
═══════════════════════════════════════════════════════════════
Lance une simulation médecin OU pharmacien avec :
  - Alia qui joue le rôle (LLM Cerebras)
  - Webcam active (analyse comportementale temps réel)
  - Bilan complet à la fin (scores comportementaux + feedback Alia)

Usage :
    python demo_simulation.py

Dépendances :
    pip install requests opencv-python mediapipe==0.10.9 deepface python-dotenv

Variables d'environnement (.env) :
    GROQ_API_KEY=your_cerebras_or_groq_key
═══════════════════════════════════════════════════════════════
"""

import os
import sys
import time
import threading
import requests
import cv2
import numpy as np
from collections import deque, Counter
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv

# ══════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════

load_dotenv()
API_KEY  = os.getenv("GROQ_API_KEY", "")
API_URL  = "https://api.cerebras.ai/v1/chat/completions"
MODEL    = "llama-3.1-8b"
MAX_TOK  = 600
TEMP     = 0.5

CAMERA_INDEX      = 0
DEEPFACE_INTERVAL = 4.0   # secondes entre analyses émotion
ALERT_EVERY_N     = 300   # frames entre alertes (~10s à 30fps)

# ══════════════════════════════════════════════════════════════
# LLM
# ══════════════════════════════════════════════════════════════

def call_llm(system: str, user: str) -> str:
    if not API_KEY:
        return "[ERREUR] GROQ_API_KEY manquant dans .env"
    try:
        resp = requests.post(
            API_URL,
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user},
                ],
                "max_tokens": MAX_TOK,
                "temperature": TEMP,
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"[ERREUR LLM] {e}"


# ══════════════════════════════════════════════════════════════
# VISION — OpenCV + MediaPipe (fallback si absent)
# ══════════════════════════════════════════════════════════════

# Tenter MediaPipe
MEDIAPIPE_OK = False
try:
    import mediapipe as mp
    if hasattr(mp, "solutions") and hasattr(mp.solutions, "face_mesh"):
        MEDIAPIPE_OK = True
        print("[Vision] ✓ MediaPipe disponible")
    else:
        print("[Vision] MediaPipe version incompatible → fallback OpenCV")
except ImportError:
    print("[Vision] MediaPipe absent → fallback OpenCV Haar Cascades")

# Tenter DeepFace
DEEPFACE_OK = False
try:
    from deepface import DeepFace
    DEEPFACE_OK = True
    print("[Vision] ✓ DeepFace disponible (analyse émotions)")
except ImportError:
    print("[Vision] DeepFace absent → émotions désactivées")


@dataclass
class FrameData:
    eye_contact:   bool  = False
    smile:         bool  = False
    emotion:       str   = "neutral"
    posture_open:  bool  = True
    hand_movement: float = 0.0
    face_detected: bool  = False


@dataclass
class BehaviorReport:
    duration:          float = 0.0
    eye_contact_score: float = 0.0
    smile_score:       float = 0.0
    posture_score:     float = 0.0
    gesture_score:     float = 0.0
    stress_score:      float = 0.0
    behavioral_score:  float = 0.0
    dominant_emotion:  str   = "neutral"
    stress_peaks:      int   = 0
    eye_contact_pct:   int   = 0
    smile_pct:         int   = 0
    strengths:         list  = field(default_factory=list)
    weaknesses:        list  = field(default_factory=list)
    tips:              list  = field(default_factory=list)


class VisionThread:
    """Analyse webcam en arrière-plan, affiche une fenêtre de preview."""

    def __init__(self):
        self._running        = False
        self._thread         = None
        self._lock           = threading.Lock()
        self._history        = deque(maxlen=600)
        self._stress_peaks   = 0
        self._start_time     = 0.0
        self._last_deepface  = 0.0
        self._last_hand_pos  = None
        self._frame_count    = 0
        self._last_alert_msg = ""

        # Initialiser détecteur
        self._mp_face_mesh = None
        self._mp_pose      = None
        self._face_mesh    = None
        self._pose_det     = None
        self._face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        self._smile_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_smile.xml"
        )

        if MEDIAPIPE_OK:
            try:
                self._mp_face_mesh = mp.solutions.face_mesh
                self._mp_pose      = mp.solutions.pose
                self._face_mesh    = self._mp_face_mesh.FaceMesh(
                    max_num_faces=1, refine_landmarks=True,
                    min_detection_confidence=0.5, min_tracking_confidence=0.5,
                )
                self._pose_det = self._mp_pose.Pose(
                    min_detection_confidence=0.5, min_tracking_confidence=0.5,
                )
                print("[Vision] FaceMesh + Pose prêts ✓")
            except Exception as e:
                print(f"[Vision] MediaPipe init échoué ({e}) → OpenCV")
                self._face_mesh = None

    # ── Start / Stop ──────────────────────────────────────────

    def start(self):
        self._running    = True
        self._start_time = time.time()
        self._thread     = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> BehaviorReport:
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        cv2.destroyAllWindows()
        return self._build_report()

    def get_current(self) -> dict:
        with self._lock:
            recent = list(self._history)[-90:]
        face = [m for m in recent if m.face_detected]
        if not face:
            return {}
        n = len(face)
        return {
            "eye_contact":  round(sum(1 for m in face if m.eye_contact) / n, 2),
            "smile":        round(sum(1 for m in face if m.smile) / n, 2),
            "posture":      round(sum(1 for m in face if m.posture_open) / n, 2),
            "emotion":      Counter(m.emotion for m in face).most_common(1)[0][0],
            "stress_peaks": self._stress_peaks,
        }

    # ── Boucle capture ────────────────────────────────────────

    def _loop(self):
        cap = cv2.VideoCapture(CAMERA_INDEX)
        if not cap.isOpened():
            print(f"[Vision] ❌ Caméra {CAMERA_INDEX} inaccessible")
            self._running = False
            return
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        print("[Vision] 📷 Caméra ouverte ✓")

        self._last_alert_msg = ""

        while self._running:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.05)
                continue

            self._frame_count += 1
            fd = FrameData()

            # Analyse
            if self._face_mesh:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                fd  = self._analyze_mediapipe(rgb, frame, fd)
            else:
                fd = self._analyze_opencv(frame, fd)

            # DeepFace
            now = time.time()
            if DEEPFACE_OK and (now - self._last_deepface) >= DEEPFACE_INTERVAL:
                self._last_deepface = now
                fd = self._analyze_deepface(frame, fd)

            with self._lock:
                self._history.append(fd)

            # Alertes toutes les N frames
            if self._frame_count % ALERT_EVERY_N == 0:
                self._check_alerts()

            # ── Affichage preview ──────────────────────────────
            self._draw_hud(frame, fd)
            cv2.imshow("Alia — Simulation (appuie Q pour arreter)", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                self._running = False
                break

            time.sleep(0.033)

        cap.release()
        cv2.destroyAllWindows()

    # ── Analyse MediaPipe ─────────────────────────────────────

    def _analyze_mediapipe(self, rgb, frame, fd: FrameData) -> FrameData:
        h, w = frame.shape[:2]
        try:
            res = self._face_mesh.process(rgb)
            if res.multi_face_landmarks:
                fd.face_detected = True
                lm = res.multi_face_landmarks[0].landmark
                # Contact visuel iris
                try:
                    ix = (lm[468].x + lm[473].x) / 2
                    iy = (lm[468].y + lm[473].y) / 2
                    fd.eye_contact = ((ix - 0.5)**2 + (iy - 0.5)**2)**0.5 < 0.15
                except IndexError:
                    pass
                # Sourire
                try:
                    mw = abs(lm[291].x - lm[61].x)
                    mh = abs(lm[13].y  - lm[14].y) + 1e-6
                    fd.smile = (mw / mh) > 4.0
                except IndexError:
                    pass
        except Exception:
            pass

        try:
            pr = self._pose_det.process(rgb)
            if pr.pose_landmarks:
                lm      = pr.pose_landmarks.landmark
                mp_pose = self._mp_pose
                ls = lm[mp_pose.PoseLandmark.LEFT_SHOULDER]
                rs = lm[mp_pose.PoseLandmark.RIGHT_SHOULDER]
                le = lm[mp_pose.PoseLandmark.LEFT_EAR]
                re = lm[mp_pose.PoseLandmark.RIGHT_EAR]
                fd.posture_open = (
                    abs(ls.y - rs.y) < 0.05 and
                    abs((le.y + re.y)/2 - (ls.y + rs.y)/2) > 0.1
                )
                lw = lm[mp_pose.PoseLandmark.LEFT_WRIST]
                rw = lm[mp_pose.PoseLandmark.RIGHT_WRIST]
                cur = np.array([lw.x, lw.y, rw.x, rw.y])
                if self._last_hand_pos is not None:
                    fd.hand_movement = float(np.linalg.norm(cur - self._last_hand_pos) * 1000)
                self._last_hand_pos = cur
        except Exception:
            pass

        return fd

    # ── Analyse OpenCV fallback ───────────────────────────────

    def _analyze_opencv(self, frame, fd: FrameData) -> FrameData:
        gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        h, w  = frame.shape[:2]
        faces = self._face_cascade.detectMultiScale(gray, 1.1, 4, minSize=(80, 80))
        if len(faces) == 0:
            return fd
        fd.face_detected = True
        x, y, fw, fh = faces[0]
        cx = (x + fw/2) / w
        cy = (y + fh/2) / h
        fd.eye_contact   = ((cx - 0.5)**2 + (cy - 0.5)**2)**0.5 < 0.25
        face_gray        = gray[y:y+fh, x:x+fw]
        smiles           = self._smile_cascade.detectMultiScale(face_gray, 1.8, 20)
        fd.smile         = len(smiles) > 0
        fd.posture_open  = (fw * fh) / (w * h) > 0.02
        return fd

    # ── DeepFace ──────────────────────────────────────────────

    def _analyze_deepface(self, frame, fd: FrameData) -> FrameData:
        try:
            res = DeepFace.analyze(frame, actions=["emotion"],
                                   enforce_detection=False, silent=True)
            if isinstance(res, list):
                res = res[0]
            fd.emotion = res.get("dominant_emotion", "neutral")
            emo        = res.get("emotion", {})
            stress     = (emo.get("fear", 0) + emo.get("angry", 0) +
                          emo.get("disgust", 0) + emo.get("sad", 0))
            if stress > 40:
                with self._lock:
                    self._stress_peaks += 1
        except Exception:
            pass
        return fd

    # ── HUD overlay ───────────────────────────────────────────

    def _draw_hud(self, frame, fd: FrameData):
        h, w = frame.shape[:2]

        # Barre de statut en haut
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, 50), (20, 20, 20), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

        green  = (80, 200, 80)
        red    = (60, 60, 220)
        yellow = (40, 200, 220)
        white  = (240, 240, 240)

        items = [
            ("👁 Contact", fd.eye_contact),
            ("😊 Sourire",  fd.smile),
            ("🧍 Posture",  fd.posture_open),
        ]
        for i, (label, ok) in enumerate(items):
            col   = green if ok else red
            state = "✓" if ok else "✗"
            cv2.putText(frame, f"{label}: {state}",
                        (10 + i * 200, 33),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, col, 2)

        # Émotion en haut à droite
        emo_col = green if fd.emotion in ("happy", "neutral") else yellow
        cv2.putText(frame, f"Emotion: {fd.emotion}",
                    (w - 200, 33), cv2.FONT_HERSHEY_SIMPLEX, 0.55, emo_col, 2)

        # Alerte en bas si présente
        if self._last_alert_msg:
            cv2.rectangle(frame, (0, h - 45), (w, h), (0, 60, 150), -1)
            cv2.putText(frame, self._last_alert_msg,
                        (10, h - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.55, white, 2)

        # Enregistrement indicator
        elapsed = int(time.time() - self._start_time)
        cv2.putText(frame, f"⏱ {elapsed}s  ● REC",
                    (w - 160, h - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, red, 2)

    # ── Alertes ───────────────────────────────────────────────

    def _check_alerts(self):
        with self._lock:
            recent = list(self._history)[-90:]
        face = [m for m in recent if m.face_detected]
        if not face:
            return
        n     = len(face)
        eye_r = sum(1 for m in face if m.eye_contact) / n
        smi_r = sum(1 for m in face if m.smile) / n
        pos_r = sum(1 for m in face if m.posture_open) / n

        if eye_r < 0.3:
            msg = "⚡ Regarde la camera — contact visuel faible"
        elif pos_r < 0.4:
            msg = "⚡ Ouvre tes epaules — posture fermee"
        elif smi_r < 0.1:
            msg = "⚡ Souris — tu parais ferme"
        else:
            msg = ""

        if msg:
            print(f"\n  {msg}")
        self._last_alert_msg = msg

    # ── Bilan ─────────────────────────────────────────────────

    def _build_report(self) -> BehaviorReport:
        with self._lock:
            history = list(self._history)
            peaks   = self._stress_peaks

        r = BehaviorReport(
            duration    = time.time() - self._start_time,
            stress_peaks= peaks,
        )
        face = [m for m in history if m.face_detected]
        if not face:
            r.behavioral_score = 5.0
            return r

        n         = len(face)
        eye_r     = sum(1 for m in face if m.eye_contact) / n
        smi_r     = sum(1 for m in face if m.smile) / n
        pos_r     = sum(1 for m in face if m.posture_open) / n
        movements = [m.hand_movement for m in face if m.hand_movement > 0]
        avg_mv    = float(np.mean(movements)) if movements else 0.0
        emotions  = [m.emotion for m in face]
        dominant  = Counter(emotions).most_common(1)[0][0] if emotions else "neutral"
        neg       = sum(1 for e in emotions if e in ("fear","angry","sad","disgust"))
        stress_r  = neg / max(len(emotions), 1)

        def gesture_score(avg):
            if avg < 5:  return 4.0
            if avg < 15: return 7.0
            if avg < 40: return 10.0
            if avg < 70: return 7.0
            return 4.0

        r.eye_contact_score = round(eye_r    * 10, 1)
        r.smile_score       = round(smi_r    * 10, 1)
        r.posture_score     = round(pos_r    * 10, 1)
        r.gesture_score     = round(gesture_score(avg_mv), 1)
        r.stress_score      = round((1 - stress_r) * 10, 1)
        r.dominant_emotion  = dominant
        r.eye_contact_pct   = int(eye_r * 100)
        r.smile_pct         = int(smi_r * 100)

        r.behavioral_score = round(
            r.eye_contact_score * 0.25 +
            r.posture_score     * 0.20 +
            r.stress_score      * 0.20 +
            r.smile_score       * 0.15 +
            r.gesture_score     * 0.10,
            1
        )

        # Feedback
        if r.eye_contact_score >= 7:
            r.strengths.append("Excellent contact visuel")
        else:
            r.weaknesses.append("Contact visuel insuffisant")
            r.tips.append("Fixe la camera comme si c'etaient les yeux du medecin")

        if r.smile_score >= 6:
            r.strengths.append("Bonne chaleur relationnelle")
        elif r.smile_score < 3:
            r.weaknesses.append("Absence de sourire — tu parais froid")
            r.tips.append("Un sourire d'accueil met le medecin en confiance")

        if r.posture_score >= 7:
            r.strengths.append("Posture ouverte et professionnelle")
        elif r.posture_score < 4:
            r.weaknesses.append("Posture fermee ou affaissee")
            r.tips.append("Epaules en arriere, dos droit — ca projette de l'assurance")

        if r.stress_score >= 8:
            r.strengths.append("Tu sembles detendu et confiant")
        elif r.stress_score < 5:
            r.weaknesses.append(f"Stress visible ({peaks} pics detectes)")
            r.tips.append("3 respirations profondes avant une visite reduisent le stress")

        return r


# ══════════════════════════════════════════════════════════════
# SIMULATION ALIA — MÉDECIN / PHARMACIEN
# ══════════════════════════════════════════════════════════════

SYSTEM_MEDECIN = """Tu es Dr. Benali, médecin généraliste expérimenté et occupé.
Tu reçois un délégué médical pharmaceutique.

TON COMPORTEMENT :
- Tu es professionnel mais pressé — tu n'as que 10 minutes
- Tu poses des questions sur les preuves cliniques et les effets secondaires
- Tu es sceptique si le délégué n'est pas précis
- Tu peux être interrompu et tu le signales poliment
- Tu réponds en FRANÇAIS, phrases courtes (2-3 phrases max)
- Si le délégué est bon, tu te montres plus intéressé progressivement

RÈGLE : Tu ne révèles jamais que tu es une IA. Tu restes dans le rôle."""

SYSTEM_PHARMACIEN = """Tu es M. Khalil, pharmacien d'officine avec 15 ans d'expérience.
Tu reçois un délégué médical pharmaceutique.

TON COMPORTEMENT :
- Tu es curieux sur les prix, remboursements et interactions médicamenteuses
- Tu veux savoir si tes patients pourront se permettre ce médicament
- Tu poses des questions pratiques sur le stock et les conditionnements
- Tu es chaleureux mais tu défends tes clients/patients
- Tu réponds en FRANÇAIS, phrases courtes (2-3 phrases max)
- Si le délégué connaît bien son produit, tu poses des questions plus techniques

RÈGLE : Tu ne révèles jamais que tu es une IA. Tu restes dans le rôle."""


def run_simulation():
    print("\n" + "═" * 60)
    print("   ALIA — Simulation de Visite Pharmaceutique")
    print("   📷 Webcam + Analyse comportementale")
    print("═" * 60)

    # ── Choisir le rôle ──────────────────────────────────────
    print("\nQui joue Alia ?\n")
    print("  [1] 🩺  Dr. Benali — Médecin généraliste")
    print("  [2] 💊  M. Khalil  — Pharmacien d'officine")
    print()
    while True:
        ch = input("Ton choix (1 ou 2) : ").strip()
        if ch == "1":
            role, system = "Médecin", SYSTEM_MEDECIN
            interlocuteur = "Dr. Benali"
            break
        elif ch == "2":
            role, system = "Pharmacien", SYSTEM_PHARMACIEN
            interlocuteur = "M. Khalil"
            break
        else:
            print("Tape 1 ou 2.")

    # ── Info délégué ─────────────────────────────────────────
    print()
    delegue_name = input("Ton prénom (délégué) : ").strip() or "Délégué"
    product_name = input("Nom du médicament présenté : ").strip() or "votre médicament"

    # ── Démarrage webcam ─────────────────────────────────────
    print("\n[Vision] Démarrage de la webcam...")
    vision = VisionThread()
    vision.start()
    time.sleep(1.5)

    # ── Intro Alia ────────────────────────────────────────────
    print("\n" + "─" * 60)
    print(f"🎬 SIMULATION DÉMARRÉE — {interlocuteur} ({role})")
    print(f"   Produit : {product_name}")
    print(f"   Délégué : {delegue_name}")
    print()
    print("   💡 Commandes :")
    print("      'stop' ou 'fin'  → terminer et voir le bilan")
    print("      'bilan'          → voir ton score comportemental en cours")
    print("─" * 60 + "\n")

    history = []
    system_enriched = (
        f"{system}\n\n"
        f"Le délégué s'appelle {delegue_name} et présente : {product_name}."
    )

    # Message d'ouverture
    opening = call_llm(
        system_enriched,
        f"Le délégué {delegue_name} vient d'entrer dans ton cabinet/pharmacie. "
        f"Accueille-le brièvement et demande-lui ce qu'il vient présenter.",
    )
    print(f"🎭 {interlocuteur}:\n{opening}\n")
    history.append({"role": "assistant", "content": opening})

    # ── Boucle de conversation ────────────────────────────────
    while True:
        try:
            user_input = input(f"👤 {delegue_name}: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n[Simulation] Interruption.")
            break

        if not user_input:
            continue

        cmd = user_input.lower()

        # ── Commandes spéciales ───────────────────────────────
        if cmd in ("stop", "fin", "quit", "exit", "arrêt", "arret"):
            break

        if cmd in ("bilan", "score", "status"):
            metrics = vision.get_current()
            if metrics:
                print("\n📊 Bilan comportemental en cours :")
                print(f"   👁  Contact visuel : {int(metrics.get('eye_contact', 0)*100)}%")
                print(f"   😊 Sourire         : {int(metrics.get('smile', 0)*100)}%")
                print(f"   🧍 Posture ouverte : {int(metrics.get('posture', 0)*100)}%")
                print(f"   🎭 Emotion dominante: {metrics.get('emotion', 'neutral')}")
                print(f"   😰 Pics de stress  : {metrics.get('stress_peaks', 0)}\n")
            else:
                print("[Bilan] Aucune donnée encore — assure-toi que la caméra te voit.\n")
            continue

        # ── Réponse LLM ───────────────────────────────────────
        history.append({"role": "user", "content": user_input})

        # Construire messages pour l'API
        messages = [{"role": "system", "content": system_enriched}]
        for turn in history[-10:]:   # contexte des 10 derniers tours
            messages.append(turn)

        try:
            resp = requests.post(
                API_URL,
                headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": MODEL,
                    "messages": messages,
                    "max_tokens": MAX_TOK,
                    "temperature": TEMP,
                },
                timeout=30,
            )
            resp.raise_for_status()
            alia_response = resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            alia_response = f"[ERREUR] {e}"

        print(f"\n🎭 {interlocuteur}:\n{alia_response}\n")
        history.append({"role": "assistant", "content": alia_response})

    # ══════════════════════════════════════════════════════════
    # BILAN FINAL
    # ══════════════════════════════════════════════════════════

    print("\n[Alia] Fin de la simulation — génération du bilan...\n")
    report = vision.stop()
    time.sleep(0.5)

    # Bilan comportemental
    print("═" * 60)
    print("  BILAN FINAL — SIMULATION " + role.upper())
    print("═" * 60)
    print(f"\n⏱️  Durée              : {int(report.duration)}s")
    print(f"👁  Contact visuel    : {report.eye_contact_score}/10  ({report.eye_contact_pct}% du temps)")
    print(f"😊 Sourire            : {report.smile_score}/10  ({report.smile_pct}% du temps)")
    print(f"🧍 Posture            : {report.posture_score}/10")
    print(f"🤝 Gestes             : {report.gesture_score}/10")
    print(f"😌 Sérénité           : {report.stress_score}/10  ({report.stress_peaks} pics de stress)")
    print(f"🎭 Émotion dominante  : {report.dominant_emotion}")
    print(f"\n⭐ SCORE COMPORTEMENTAL : {report.behavioral_score}/10")

    if report.strengths:
        print("\n✅ POINTS FORTS")
        for s in report.strengths:
            print(f"   • {s}")

    if report.weaknesses:
        print("\n⚠️  POINTS À AMÉLIORER")
        for w in report.weaknesses:
            print(f"   • {w}")

    if report.tips:
        print("\n💡 CONSEILS")
        for t in report.tips:
            print(f"   → {t}")

    # Feedback vocal Alia (LLM)
    print("\n" + "─" * 60)
    print("🤖 Feedback d'Alia :")
    print("─" * 60)

    conv_summary = "\n".join(
        [f"{'Délégué' if t['role']=='user' else interlocuteur}: {t['content']}"
         for t in history[-6:]]
    )

    feedback_system = f"""Tu es Alia, formatrice pharmaceutique et coach.
Tu viens d'observer la simulation de {delegue_name} face à un {role.lower()}.

SCORES COMPORTEMENTAUX :
- Contact visuel : {report.eye_contact_score}/10 ({report.eye_contact_pct}%)
- Sourire        : {report.smile_score}/10
- Posture        : {report.posture_score}/10
- Gestes         : {report.gesture_score}/10
- Sérénité       : {report.stress_score}/10 ({report.stress_peaks} pics de stress)
- Émotion dominante : {report.dominant_emotion}
- Score global   : {report.behavioral_score}/10

Points forts   : {', '.join(report.strengths) or 'aucun notable'}
Points faibles : {', '.join(report.weaknesses) or 'aucun'}

Fin de conversation :
{conv_summary}

Génère un feedback oral en 4-5 phrases :
1. Félicite 1-2 choses bien précises
2. Mentionne 1-2 axes d'amélioration concrets
3. Donne 1 conseil actionnable pour la prochaine visite
4. Termine par une phrase motivante personnalisée
Style : coach bienveillant et direct, pas rapport RH."""

    feedback = call_llm(feedback_system, f"Donne ton feedback à {delegue_name}.")
    print(f"\n{feedback}")
    print("\n" + "═" * 60)
    print("   Merci pour cette simulation ! À bientôt. 👋")
    print("═" * 60 + "\n")


# ══════════════════════════════════════════════════════════════
# ENTRÉE
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    run_simulation()