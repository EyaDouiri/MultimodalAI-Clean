"""
voice_prosody.py - Alia Prosody Analyzer v2 — Hume AI
═══════════════════════════════════════════════════════════════
CHANGEMENTS v2 vs v1 :
  - Hume AI remplace librosa pour l'analyse émotionnelle de la voix
      → Envoie le fichier audio à l'API Hume Expression Measurement
      → Retourne 48 dimensions émotionnelles sur la voix :
         confidence, doubt, determination, enthusiasm, fear, joy...
      → Bien plus précis que les métriques acoustiques RMS de librosa
      → librosa conservé en fallback si pas de clé Hume
  - get_snapshot() retourne maintenant "hume_emotions" (dict) et
    "hume_top_emotion" (str) pour injection dans le prompt Llama
  - Analyse Hume tourne dans un thread séparé — non bloquant

Dépendances :
    pip install hume numpy
    # librosa en fallback optionnel : pip install librosa soundfile

Clé API :
    Mettre HUME_API_KEY dans le fichier .env
    Obtenir une clé gratuite sur : https://platform.hume.ai
"""

import re
import os
import time
import threading
import tempfile
import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from dotenv import load_dotenv

load_dotenv()
HUME_API_KEY = os.getenv("HUME_API_KEY", "")

# ── Hume AI ────────────────────────────────────────────────────────────────
HUME_AVAILABLE = False
if HUME_API_KEY:
    try:
        from hume import HumeClient
        HUME_AVAILABLE = True
        print("[Prosody] Hume AI (analyse emotionnelle voix) OK")
    except ImportError as e:
        print(f"[Prosody] WARNING: hume non installé → pip install hume — ImportError: {e}")
    except Exception as e:
        print(f"[Prosody] WARNING: Hume init echoue : {e}")
else:
    print("[Prosody] WARNING: HUME_API_KEY manquant dans .env → fallback librosa/texte")
    print("[Prosody]     Obtenir une clé gratuite : https://platform.hume.ai")

# ── librosa (fallback) ─────────────────────────────────────────────────────
LIBROSA_AVAILABLE = False
if not HUME_AVAILABLE:
    try:
        import librosa
        LIBROSA_AVAILABLE = True
        print("[Prosody] Fallback librosa OK")
    except ImportError:
        print("[Prosody] WARNING: librosa non installe — analyse texte uniquement")


# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════

HESITATION_WORDS = [
    "euh", "euhm", "hmm", "hm", "ben", "bah", "donc", "voilà",
    "enfin", "comment dire", "c'est-à-dire", "en fait", "du coup",
    "eh bien", "alors", "ouais", "hein",
]

IDEAL_WPM_MIN = 110
IDEAL_WPM_MAX = 160
LONG_SILENCE_THRESHOLD = 2.0
AVG_SYLLABLES_PER_WORD_FR = 1.9

# Émotions Hume qui signalent un bon état pour un délégué en visite
HUME_POSITIVE_EMOTIONS = {
    "Confidence", "Determination", "Enthusiasm", "Joy",
    "Interest", "Excitement", "Satisfaction", "Amusement"
}
# Émotions qui signalent du stress / manque de confiance
HUME_NEGATIVE_EMOTIONS = {
    "Doubt", "Fear", "Nervousness", "Anxiety", "Distress",
    "Embarrassment", "Shame", "Awkwardness"
}


# ══════════════════════════════════════════════════════════════════════════════
# STRUCTURES
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class TurnProsody:
    turn_number:          int   = 0
    text:                 str   = ""
    duration_s:           float = 0.0
    word_count:           int   = 0
    speech_rate_wpm:      float = 0.0
    hesitation_count:     int   = 0
    hesitation_rate:      float = 0.0
    silence_ratio:        float = 0.0
    energy_mean:          float = 0.0
    energy_variability:   float = 0.0
    confidence_score:     float = 5.0
    # Hume AI fields
    hume_emotions:        Dict[str, float] = field(default_factory=dict)
    hume_top_emotion:     str   = ""
    hume_confidence:      float = 0.0   # score Confidence de Hume 0-1
    hume_doubt:           float = 0.0   # score Doubt de Hume 0-1
    hume_enthusiasm:      float = 0.0


@dataclass
class ProsodySessionReport:
    total_turns:            int   = 0
    avg_wpm:                float = 0.0
    avg_hesitation_rate:    float = 0.0
    avg_silence_ratio:      float = 0.0
    avg_confidence_score:   float = 0.0
    avg_energy_variability: float = 0.0
    avg_hume_confidence:    float = 0.0
    avg_hume_doubt:         float = 0.0
    high_stress_turns:  List[int] = field(default_factory=list)
    low_fluency_turns:  List[int] = field(default_factory=list)
    strong_turns:       List[int] = field(default_factory=list)
    strengths:   List[str] = field(default_factory=list)
    weaknesses:  List[str] = field(default_factory=list)
    tips:        List[str] = field(default_factory=list)
    turns: List[TurnProsody] = field(default_factory=list)


# ══════════════════════════════════════════════════════════════════════════════
# ANALYSEUR PRINCIPAL v2
# ══════════════════════════════════════════════════════════════════════════════

class ProsodyAnalyzer:
    """
    Analyse prosodique + émotionnelle de la voix du délégué.

    Usage :
        analyzer = ProsodyAnalyzer()

        # Appelé après chaque tour Whisper :
        turn = analyzer.analyze_turn(
            text="Bonjour docteur euh je voulais vous parler de...",
            duration_s=4.2,
            audio_path="C:/tmp/alia_abc123.mp3"  # requis pour Hume / librosa
        )
        snapshot = analyzer.get_snapshot()  # pour injecter dans le prompt

        # En fin de simulation :
        report = analyzer.build_report()
    """

    def __init__(self):
        self._turns:      List[TurnProsody] = []
        self._turn_count  = 0
        self._start_time  = time.time()
        self._hume_lock   = threading.Lock()

    # ══════════════════════════════════════════════════════════════════════════
    # ANALYSE D'UN TOUR
    # ══════════════════════════════════════════════════════════════════════════

    def analyze_turn(
        self,
        text: str,
        duration_s: float,
        audio_path: Optional[str] = None,
    ) -> TurnProsody:
        self._turn_count += 1
        turn = TurnProsody(turn_number=self._turn_count, text=text)

        # ── 1. Métriques textuelles ──────────────────────────────────────────
        turn.duration_s       = max(duration_s, 0.5)
        turn.word_count       = len(text.split())
        turn.speech_rate_wpm  = self._calc_wpm(text, turn.duration_s)
        turn.hesitation_count = self._count_hesitations(text)
        turn.hesitation_rate  = (turn.hesitation_count / turn.duration_s) * 60

        # ── 2. Analyse audio ─────────────────────────────────────────────────
        if audio_path:
            if HUME_AVAILABLE:
                # Hume dans un thread pour ne pas bloquer
                threading.Thread(
                    target=self._analyze_hume_async,
                    args=(audio_path, turn),
                    daemon=True
                ).start()
            elif LIBROSA_AVAILABLE:
                audio_metrics = self._analyze_librosa(audio_path)
                turn.silence_ratio      = audio_metrics.get("silence_ratio", 0.0)
                turn.energy_mean        = audio_metrics.get("energy_mean", 0.5)
                turn.energy_variability = audio_metrics.get("energy_variability", 0.0)
        else:
            turn.silence_ratio = self._estimate_silence_ratio(turn.speech_rate_wpm)

        # ── 3. Score confiance synthétique ───────────────────────────────────
        turn.confidence_score = self._calc_confidence(turn)
        self._turns.append(turn)
        return turn

    # ── Hume AI ───────────────────────────────────────────────────────────────

    def _analyze_hume_async(self, audio_path: str, turn: TurnProsody):
        """Envoie le fichier audio à Hume et met à jour turn avec les résultats."""
        try:
            client = HumeClient(api_key=HUME_API_KEY)

            # Prepare file tuple(s) for upload
            ext = os.path.splitext(audio_path)[1].lower()
            if ext == '.mp3':
                ctype = 'audio/mpeg'
            elif ext in ('.wav', '.wave'):
                ctype = 'audio/wav'
            else:
                ctype = 'application/octet-stream'

            with open(audio_path, 'rb') as fh:
                file_tuple = (os.path.basename(audio_path), fh, ctype)
                job_id = client.expression_measurement.batch.start_inference_job_from_local_file(
                    file=[file_tuple]
                )

            # Poll job until completion (timeout ~30s)
            start = time.time()
            while True:
                details = client.expression_measurement.batch.get_job_details(id=job_id)
                status = getattr(details, 'status', None)
                if status and str(status).lower() in ('completed', 'completed'.upper()):
                    break
                if time.time() - start > 30:
                    raise TimeoutError('Hume batch job timeout')
                time.sleep(1.0)

            predictions = client.expression_measurement.batch.get_job_predictions(id=job_id)

            # Parser les résultats Hume
            emotions = {}
            for pred in predictions:
                for source in pred.get("results", {}).get("predictions", []):
                    for model_pred in source.get("models", {}).get("prosody", {}).get("grouped_predictions", []):
                        for segment in model_pred.get("predictions", []):
                            for emo in segment.get("emotions", []):
                                name  = emo.get("name", "")
                                score = emo.get("score", 0.0)
                                if name:
                                    emotions[name] = max(emotions.get(name, 0.0), score)

            if emotions:
                top = max(emotions, key=emotions.get)
                with self._hume_lock:
                    turn.hume_emotions    = emotions
                    turn.hume_top_emotion = top
                    turn.hume_confidence  = round(emotions.get("Confidence", 0.0), 3)
                    turn.hume_doubt       = round(emotions.get("Doubt", 0.0), 3)
                    turn.hume_enthusiasm  = round(emotions.get("Enthusiasm", 0.0), 3)
                    # Recalcule le confidence_score avec les données Hume
                    turn.confidence_score = self._calc_confidence_with_hume(turn)
                print(f"[Prosody Hume] Tour {turn.turn_number} — top: {top} ({emotions.get(top,0):.2f}), "
                      f"confidence={turn.hume_confidence:.2f}, doubt={turn.hume_doubt:.2f}")

        except Exception as e:
            print(f"[Prosody] Hume erreur tour {turn.turn_number} : {e}")

    def _calc_confidence_with_hume(self, turn: TurnProsody) -> float:
        """Score confiance enrichi avec les émotions Hume."""
        base = self._calc_confidence(turn)

        # Bonus/malus Hume
        if turn.hume_confidence > 0.5:
            base += 1.5
        elif turn.hume_confidence > 0.3:
            base += 0.5

        if turn.hume_doubt > 0.5:
            base -= 2.0
        elif turn.hume_doubt > 0.3:
            base -= 1.0

        if turn.hume_enthusiasm > 0.4:
            base += 1.0

        # Bonus si l'émotion dominante Hume est positive
        if turn.hume_top_emotion in HUME_POSITIVE_EMOTIONS:
            base += 0.5
        elif turn.hume_top_emotion in HUME_NEGATIVE_EMOTIONS:
            base -= 1.0

        return round(max(0.0, min(10.0, base)), 1)

    # ── librosa fallback ──────────────────────────────────────────────────────

    def _analyze_librosa(self, path: str) -> Dict[str, float]:
        result = {"silence_ratio": 0.0, "energy_mean": 0.5, "energy_variability": 0.0}
        try:
            y, sr = librosa.load(path, sr=None, mono=True)
            if len(y) < sr * 0.3:
                return result
            hop_length = 512
            rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]
            if len(rms) == 0:
                return result
            threshold = 0.05 * float(np.max(rms))
            silent_frames = np.sum(rms < threshold)
            result["silence_ratio"] = round(float(silent_frames / len(rms)), 3)
            rms_nonsilent = rms[rms >= threshold]
            if len(rms_nonsilent) > 0:
                result["energy_mean"] = round(
                    float(np.mean(rms_nonsilent)) / (float(np.max(rms)) + 1e-8), 3)
            mean_e = float(np.mean(rms_nonsilent)) if len(rms_nonsilent) > 0 else 1e-8
            std_e  = float(np.std(rms_nonsilent))  if len(rms_nonsilent) > 0 else 0.0
            result["energy_variability"] = round(std_e / (mean_e + 1e-8), 3)
        except Exception as e:
            print(f"[Prosody] Erreur librosa: {e}")
        return result

    # ── Métriques textuelles ──────────────────────────────────────────────────

    def _calc_wpm(self, text: str, duration_s: float) -> float:
        words = [w for w in text.split() if len(w) > 1]
        return round((len(words) / max(duration_s, 1)) * 60, 1)

    def _count_hesitations(self, text: str) -> int:
        text_lower = text.lower()
        count = 0
        for word in HESITATION_WORDS:
            pattern = r'\b' + re.escape(word) + r'\b'
            count += len(re.findall(pattern, text_lower))
        return count

    def _estimate_silence_ratio(self, wpm: float) -> float:
        if wpm < 60:   return 0.45
        if wpm < 90:   return 0.30
        if wpm < 120:  return 0.20
        if wpm < 160:  return 0.12
        return 0.08

    def _calc_confidence(self, turn: TurnProsody) -> float:
        score = 7.0
        wpm = turn.speech_rate_wpm
        if wpm < 60:
            score -= 2.5
        elif wpm < 90:
            score -= 1.0
        elif IDEAL_WPM_MIN <= wpm <= IDEAL_WPM_MAX:
            score += 1.0
        elif wpm > 200:
            score -= 1.5
        if turn.hesitation_rate > 10:
            score -= 2.0
        elif turn.hesitation_rate > 5:
            score -= 1.0
        elif turn.hesitation_rate == 0:
            score += 0.5
        if turn.silence_ratio > 0.5:
            score -= 1.5
        elif turn.silence_ratio > 0.35:
            score -= 0.5
        if turn.energy_variability > 0.3:
            score += 0.5
        return round(max(0.0, min(10.0, score)), 1)

    # ══════════════════════════════════════════════════════════════════════════
    # SNAPSHOT TEMPS RÉEL
    # ══════════════════════════════════════════════════════════════════════════

    def get_snapshot(self) -> Dict:
        """
        Retourne les métriques du dernier tour + émotions Hume.
        Conçu pour être injecté dans prompt_followup_m3().
        """
        if not self._turns:
            return {}

        last   = self._turns[-1]
        recent = self._turns[-3:]
        avg_conf = round(sum(t.confidence_score for t in recent) / len(recent), 1)
        avg_wpm  = round(sum(t.speech_rate_wpm  for t in recent) / len(recent), 1)

        trend = "stable"
        if len(self._turns) >= 3:
            older_conf = sum(t.confidence_score for t in self._turns[-5:-2]) / max(len(self._turns[-5:-2]), 1)
            if avg_conf > older_conf + 1:
                trend = "improving"
            elif avg_conf < older_conf - 1:
                trend = "declining"

        # Top 5 émotions Hume du dernier tour (triées par score)
        hume_top5 = {}
        if last.hume_emotions:
            sorted_emo = sorted(last.hume_emotions.items(), key=lambda x: x[1], reverse=True)
            hume_top5  = {k: round(v, 3) for k, v in sorted_emo[:5]}

        return {
            "turn":             last.turn_number,
            "wpm":              last.speech_rate_wpm,
            "wpm_status":       self._wpm_label(last.speech_rate_wpm),
            "hesitations":      last.hesitation_count,
            "hesitation_rate":  round(last.hesitation_rate, 1),
            "silence_ratio":    last.silence_ratio,
            "confidence_score": last.confidence_score,
            "trend":            trend,
            "avg_confidence":   avg_conf,
            "avg_wpm_3turns":   avg_wpm,
            # Hume AI — émotions vocales
            "hume_available":   HUME_AVAILABLE,
            "hume_top_emotion": last.hume_top_emotion,
            "hume_confidence":  last.hume_confidence,
            "hume_doubt":       last.hume_doubt,
            "hume_enthusiasm":  last.hume_enthusiasm,
            "hume_top5":        hume_top5,
        }

    def _wpm_label(self, wpm: float) -> str:
        if wpm < 60:   return "très lent (hésitations)"
        if wpm < 90:   return "lent"
        if wpm < 110:  return "correct mais lent"
        if wpm <= 160: return "idéal"
        if wpm <= 200: return "rapide"
        return "trop rapide (stress probable)"

    # ══════════════════════════════════════════════════════════════════════════
    # RAPPORT FINAL
    # ══════════════════════════════════════════════════════════════════════════

    def build_report(self) -> ProsodySessionReport:
        report = ProsodySessionReport(turns=list(self._turns))
        if not self._turns:
            return report

        report.total_turns           = len(self._turns)
        report.avg_wpm               = round(sum(t.speech_rate_wpm for t in self._turns) / report.total_turns, 1)
        report.avg_hesitation_rate   = round(sum(t.hesitation_rate for t in self._turns) / report.total_turns, 1)
        report.avg_silence_ratio     = round(sum(t.silence_ratio   for t in self._turns) / report.total_turns, 3)
        report.avg_confidence_score  = round(sum(t.confidence_score for t in self._turns) / report.total_turns, 1)
        report.avg_energy_variability = round(
            sum(t.energy_variability for t in self._turns) / report.total_turns, 3)

        hume_turns = [t for t in self._turns if t.hume_emotions]
        if hume_turns:
            report.avg_hume_confidence = round(sum(t.hume_confidence for t in hume_turns) / len(hume_turns), 3)
            report.avg_hume_doubt      = round(sum(t.hume_doubt      for t in hume_turns) / len(hume_turns), 3)

        for t in self._turns:
            if t.confidence_score <= 4.0 or t.hesitation_rate > 10 or t.hume_doubt > 0.5:
                report.high_stress_turns.append(t.turn_number)
            if t.speech_rate_wpm < 80 or t.silence_ratio > 0.45:
                report.low_fluency_turns.append(t.turn_number)
            if t.confidence_score >= 8.0 or t.hume_confidence > 0.5:
                report.strong_turns.append(t.turn_number)

        report.strengths, report.weaknesses, report.tips = self._generate_feedback(report)
        return report

    def _generate_feedback(self, r: ProsodySessionReport):
        strengths, weaknesses, tips = [], [], []

        if IDEAL_WPM_MIN <= r.avg_wpm <= IDEAL_WPM_MAX:
            strengths.append(f"Débit de parole naturel ({int(r.avg_wpm)} mots/min)")
        elif r.avg_wpm < 90:
            weaknesses.append(f"Débit trop lent ({int(r.avg_wpm)} mots/min) — tu sembles hésitant")
            tips.append("Prépare 3 phrases clés par produit à l'avance — elles sortiront naturellement")
        elif r.avg_wpm > 180:
            weaknesses.append(f"Débit trop rapide ({int(r.avg_wpm)} mots/min) — le médecin décroche")
            tips.append("Marque une pause après chaque argument fort — ça laisse l'impact s'installer")

        if r.avg_hesitation_rate < 2:
            strengths.append("Très peu d'hésitations — tu parais préparé et confiant")
        elif r.avg_hesitation_rate > 8:
            weaknesses.append(f"Hésitations fréquentes ({r.avg_hesitation_rate:.0f}/min)")
            tips.append("Remplace les 'euh' par une respiration courte — ça passe mieux et ça te calme")

        # Feedback Hume si disponible
        if HUME_AVAILABLE and r.avg_hume_confidence > 0:
            if r.avg_hume_confidence >= 0.4:
                strengths.append(f"Hume AI détecte une voix confiante (score confidence={r.avg_hume_confidence:.2f})")
            elif r.avg_hume_doubt >= 0.4:
                weaknesses.append(f"Hume AI détecte du doute dans ta voix (score doubt={r.avg_hume_doubt:.2f})")
                tips.append("Enregistre-toi et réécoute — le doute s'entend souvent avant de se voir")
        elif r.avg_confidence_score >= 7.5:
            strengths.append("Voix confiante et fluide sur l'ensemble de la simulation")
        elif r.avg_confidence_score < 5.0:
            weaknesses.append("Manque de fluidité vocal global — travaille le discours à voix haute")
            tips.append("Enregistre-toi et réécoute — tu détecteras toi-même les patterns à corriger")

        if r.high_stress_turns:
            turn_labels = ", ".join([f"réplique {t}" for t in r.high_stress_turns[:3]])
            tips.append(f"Retravailler spécifiquement : {turn_labels} (stress vocal détecté)")

        return strengths, weaknesses, tips

    def format_report_text(self, report: ProsodySessionReport) -> str:
        lines = [
            "\n" + "─" * 55,
            "  BILAN PROSODIQUE — VOIX & FLUIDITÉ",
            "─" * 55,
            f"  Débit moyen          : {report.avg_wpm:.0f} mots/min "
            f"({'✅ idéal' if IDEAL_WPM_MIN <= report.avg_wpm <= IDEAL_WPM_MAX else '⚠️ à corriger'})",
            f"  Hésitations          : {report.avg_hesitation_rate:.1f}/min",
            f"  Score confiance voix : {report.avg_confidence_score}/10",
        ]

        if HUME_AVAILABLE and report.avg_hume_confidence > 0:
            lines += [
                f"  Hume — Confidence    : {report.avg_hume_confidence:.2f}/1.0",
                f"  Hume — Doubt         : {report.avg_hume_doubt:.2f}/1.0",
            ]

        if report.strong_turns:
            lines.append(f"  Tours solides        : {report.strong_turns}")
        if report.high_stress_turns:
            lines.append(f"  Tours tendus         : {report.high_stress_turns}")

        if report.strengths:
            lines.append("\n✅ VOIX — Points forts")
            lines += [f"  • {s}" for s in report.strengths]
        if report.weaknesses:
            lines.append("\n⚠️  VOIX — Points à améliorer")
            lines += [f"  • {w}" for w in report.weaknesses]
        if report.tips:
            lines.append("\n💡 VOIX — Conseils")
            lines += [f"  → {t}" for t in report.tips]
        lines.append("─" * 55)
        return "\n".join(lines)