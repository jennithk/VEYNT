# VEYNT — Voice Authenticity & Verification

## Problem statement

Problem Statement ID: 26104

Title: AI-Powered Real-Time Detection and Prevention of Voice Cloning Impersonation Attacks

Theme: Blockchain & Cybersecurity

## Problem motivation

AI-generated voice cloning and impersonation attacks can exploit trust in high-risk financial and executive communication flows. The goal is to detect suspicious impersonation before a harmful action is approved.

## Solution overview

This project is a cross-platform Veynt prototype for responsible voice authenticity analysis. It provides:

- microphone recording and audio upload on web and mobile
- English, Hindi, Telugu, and auto-detect language selection
- persistent analysis metadata and history
- explicit INCONCLUSIVE results when verified model providers are unavailable
- replaceable speech-to-text and authenticity service interfaces

This is a prototype and demonstration platform, not a live telephony interception system.

## Scope and honesty

This project intentionally does not claim to intercept live cellular calls or to use a production-trained deepfake detector.

The provider adapters are isolated behind `SpeechToTextService` and `VoiceAuthenticityService`. With no verified provider configured, the product returns `INCONCLUSIVE` instead of fabricating scores or transcripts.

## Architecture

The system is organized into a FastAPI backend, React web client, and Expo native client. The processing flow is:

1. recording or upload
2. server-side audio validation
3. configured speech-to-text provider
4. configured authenticity provider
5. risk and explainability output
6. persisted history metadata

## Demo scenarios

- Genuine call: low risk, continue
- AI-cloned voice: high AI probability, verification required
- Executive impersonation: urgent payment request + secrecy + credentials = high risk
- Medium-risk suspicious call: additional verification required

## Running locally

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

### Native mobile client

```bash
cd mobile
npm install
npx expo start
```

Set `VITE_API_URL` for web or `EXPO_PUBLIC_API_URL` for mobile to a backend address reachable by the device.

### Run from project root

```bash
cd SIH
python -m pytest backend/tests/test_health.py backend/tests/test_demo_detector.py backend/tests/test_context_and_risk.py backend/tests/test_analysis_endpoint.py
```

## API summary

- GET /api/health
- POST /api/analyze
- POST /api/analyses (multipart audio upload; provider-backed or explicitly inconclusive)
- GET /api/analyses
- GET /api/analyses/{id}
- DELETE /api/analyses/{id}
- POST /api/auth/signup
- POST /api/auth/signin
- POST /api/auth/signout
- GET /api/auth/me
- POST /api/speaker-verification

## Local AI setup

The local development path is now configured for honest CPU-first analysis without an API key:

```bash
cd C:\Users\kjenn\SIH\backend
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Set the backend environment in a file such as `.env` or `.env.example`:

```env
VEYNT_STT_PROVIDER=local
VEYNT_STT_MODEL=small
VEYNT_STT_DEVICE=cpu
VEYNT_STT_COMPUTE_TYPE=int8
VEYNT_AUTHENTICITY_PROVIDER=local_aasist
```

Notes:

- Whisper handles speech-to-text locally and supports English, Hindi, Telugu, and auto-detection.
- AASIST is a separate anti-spoofing model for synthetic-speech detection; it is not equivalent to speaker verification.
- The app stays honest and returns `INCONCLUSIVE` if the model checkpoint or provider is missing.
- Speaker verification is a separate subsystem and should not be confused with anti-spoofing detection.

## Provider configuration

The backend never fabricates model output. Configure a verified provider before enabling production analysis:

- `VEYNT_STT_PROVIDER=local` uses the installed `faster-whisper` runtime without any OpenAI key.
- `VEYNT_STT_PROVIDER=openai` keeps the OpenAI-compatible provider available for future use with `VEYNT_STT_API_KEY` and optional `VEYNT_STT_URL` / `VEYNT_STT_MODEL`.
- `VEYNT_AUTHENTICITY_PROVIDER=local_aasist` expects a downloaded official AASIST checkpoint. Without it, Veynt intentionally returns `INCONCLUSIVE`.
- `VEYNT_AUTHENTICITY_PROVIDER=http` can use a remote anti-spoofing endpoint if configured.
- `VEYNT_SPEAKER_PROVIDER=http` remains the independent speaker-embedding path for future verification workflows.
- Keep `VEYNT_ALLOW_ANONYMOUS=0` outside local development. Provider keys must only exist in the backend environment.

Uploads are held in memory for the queued job and are not written as public files. The SQLite database stores analysis metadata and results, not raw audio.
- WebSocket /ws/{call_id}

## Prototype status

Current prototype status:

- working FastAPI, React web, and Expo native foundations
- validated upload and microphone capture flows
- persistent local analysis history
- replaceable multilingual provider contracts
- honest provider-gated result handling

## Limits

- not a live call interception system
- verified STT and authenticity providers still need to be configured through server-side adapters
- speaker embedding verification still needs a provider adapter
- not benchmarked with real-world datasets
- evaluation remains pending

## Demo script

1. Open the dashboard.
2. Start with the genuine call scenario.
3. Show low risk and normal transcript.
4. Switch to the AI-cloned scenario.
5. Show rising AI probability and mismatch.
6. Switch to the executive impersonation scenario.
7. Highlight urgent financial request, secrecy instruction, and OCR-style recommendation.
8. Emphasize that the system recommends independent verification and does not perform transactions automatically.

## Future scope

- trained AI voice detector integration
- speaker verification model with enrollment data
- ASR and live transcript pipeline
- real history database and privacy-preserving storage
- tamper-evident audit trail
- future VoIP / telephony integration beyond the simulated prototype
# VEYNT
