# Multimodal AI Training Agent

A conversational AI agent designed to train professionals through interactive role-play simulations — combining a RAG pipeline, real-time behavioral analysis, voice prosody evaluation, and a synchronized 3D avatar.

---

## Why this project exists

Training professionals through traditional methods is slow, expensive, and hard to scale. You need a trainer available, a room, and a schedule. Feedback is often delayed and subjective.

This project explores a different approach: what if an AI could simulate a realistic training scenario, evaluate the trainee in real time across multiple dimensions — what they say, how they say it, and how they present themselves — and give structured, actionable feedback immediately?

That's what this agent does.

---

## What it does

The agent runs in two modes:

**Simulation mode (training)**
The AI plays the role of a professional the trainee needs to convince (a doctor, a pharmacist, etc.). After each exchange, the agent steps out of character and gives feedback on three axes:
- **Content** — is the information accurate, complete, well-argued?
- **Behavior** — posture, eye contact, objects in hand (phone, food, etc.)
- **Voice** — tone, confidence, speech rate

**Exam mode**
Same simulation, but the agent stays in character and takes silent notes. At the end, it delivers a full scored report across all three axes.

The trainee decides when they feel ready to switch from training to exam.

---

## Architecture

```
User speech (mic)
    │
    ├── STT (Whisper / browser API)
    │       └── Text → Agent
    │
    ├── Voice prosody analysis (Hume AI)
    │       └── Tone, confidence, stress → Axes score
    │
    └── Webcam feed
            ├── MediaPipe (continuous, local)
            │       └── Posture, eye contact, smile
            └── Moondream VLM (every 4s, API)
                    └── Objects detection, gesture description
                        → "holding a sandwich", "looking away"

Agent core
    ├── RAG pipeline
    │       ├── FAISS vector store (product knowledge base)
    │       ├── Embeddings (sentence-transformers)
    │       └── LLaMA 3.1-8B via Groq API
    │
    ├── Prompt engineering (Role+Persona technique)
    │       └── Selected after benchmarking 4 LLMs × 4 techniques
    │
    └── Response with behavioral hint injected

Output
    ├── Text response
    ├── TTS (Edge-TTS, fr-FR-DeniseNeural / HenriNeural / CharlineNeural)
    └── 3D avatar (Three.js, ReadyPlayerMe GLB)
            ├── Lip sync (11 morph targets, jawOpen, mouthFunnel...)
            └── Arm gestures (lerp between rest pose and talking pose)
```

---

## Benchmarking

Before deploying, we ran a systematic evaluation of 4 LLMs across 4 prompt engineering techniques on 7 real training scenarios.

| Model | Zero-shot | Few-shot | Role+Persona | CoT | Avg |
|---|---|---|---|---|---|
| llama-3.1-8b | 5.83 | 6.14 | **8.49** | 6.11 | **6.64** |
| qwen3-32b | 5.00 | 6.26 | 3.77 | 5.91 | 5.24 |
| llama-4-scout | 1.29 | 7.23 | 7.03 | 3.54 | 4.77 |
| llama-3.3-70b | 3.63 | 5.87 | 2.00 | 2.15 | 3.31 |

Evaluation was done with an LLM-as-judge approach across 5 criteria: faithfulness to RAG context, pedagogical quality, tone consistency, scope respect, and fluency.

**Winner: `llama-3.1-8b` + Role+Persona prompt — 8.49/10, latency 0.59s**

The result surprised us. A well-prompted 8B model outperformed a 70B model with poor prompting. The Role+Persona technique — giving the model a strong identity with specific instructions about teaching style, tone, and scope — was by far the most effective approach.

---

## Tech stack

| Layer | Technology |
|---|---|
| LLM | LLaMA 3.1-8B via Groq API (Cerebras) |
| RAG | FAISS + sentence-transformers |
| Vision | Moondream3 API + MediaPipe Holistic |
| Voice analysis | Hume AI Expression API |
| STT | Whisper (local) |
| TTS | Edge-TTS (Microsoft Neural voices, French) |
| Avatar | Three.js + ReadyPlayerMe GLB |
| Backend | Python, HTTP server (no framework) |
| Frontend | Vanilla HTML/CSS/JS |

---

## Project structure

```
.
├── agent.py              # Core agent — RAG, simulation logic, scoring
├── prompts.py            # All prompt templates (M1, M2, M3, simulation, exam)
├── retriever.py          # FAISS retriever + embedding pipeline
├── memory.py             # Session save/load, history, summaries
├── session.py            # Delegate profile loader (CSV → dataclass)
├── Moondreamcoach.py     # Vision module — Moondream + MediaPipe
├── voice.py              # TTS engine with persona-based voice selection
├── voice_prosody.py      # Hume AI prosody analysis
├── avatar_server.py      # HTTP server — serves dashboard + avatar API
├── launch.py             # One-command launcher (server + browser)
├── dashboard.html        # Delegate dashboard (progress, history, Alia access)
├── alia_avatar.html      # 3D avatar interface
├── benchmark.py          # LLM benchmarking script
├── sessions/             # Saved sessions (auto-generated JSON files)
└── data/
    └── raw/              # Source knowledge base (scraped, cleaned)
```

---

## Running it

### Prerequisites

```bash
pip install groq requests python-dotenv edge-tts pygame mediapipe moondream pillow
```

### Environment variables

Create a `.env` file:

```
GROQ_API_KEY=your_groq_key
MOONDREAM_API_KEY=your_moondream_key
HUME_API_KEY=your_hume_key
```

### Launch

```bash
python launch.py
```

This starts the server on `http://localhost:9000` and opens the dashboard automatically in your browser.

---

## How a session looks

1. The delegate logs in — the dashboard loads their profile, assigned products, scores, and session history.
2. They open Alia in conversation mode — she greets them and starts with their current product.
3. They choose to launch a simulation: doctor or pharmacist.
4. The camera opens. The role-play starts.
5. After each delegate turn, Alia gives feedback — content, posture, voice.
6. When they feel ready, they switch to exam mode. Alia goes silent.
7. At the end of the exam, Alia delivers the full report.

---

## What I learned

A few things that weren't obvious at the start:

**On LLMs**: model size doesn't determine quality — prompting strategy does. An 8B model with the right identity instruction consistently outperformed a 70B model given a vague prompt.

**On vision**: general-purpose VLMs respond much better to specific closed questions ("is the person holding any object?") than to open-ended instructions ("analyze the body language"). The latter produces generic descriptions that are hard to parse programmatically.

**On TTS synchronization**: the avatar lip sync needs to trigger *after* the audio file is synthesized and *before* playback starts — not before synthesis. A 1-2 second synthesis delay with the avatar already animating looks broken. Timing the state change to the actual `play()` call solves it entirely.

**On latency**: the full pipeline (LLM + vision + TTS) runs in under 3 seconds per turn, which feels natural in conversation. The vision analysis runs in a background thread every 4 seconds and doesn't block the main response loop.

---

## Limitations and next steps

- The knowledge base is domain-specific and needs to be rebuilt for each new use case
- Moondream object detection works well for obvious items (phone, cup) but struggles with ambiguous objects in poor lighting
- The scoring rubric is heuristic — a proper human evaluation on a larger sample would strengthen the benchmark
- Session data is stored as local JSON files — a proper backend (Django API) is planned

---

## Note on confidentiality

This project was built as part of an academic partnership. The knowledge base and business context are not included in this repository. The code, architecture, and evaluation methodology are entirely original work.

---

*Built with Python, curiosity, and a lot of debugging at 2am.*
