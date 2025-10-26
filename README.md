# legal-intake-orchestrator — Flask backend scaffold

This repository contains a minimal Flask backend that accepts legal intake
messages and returns a generated draft and a task category. The app includes
a small adapter to integrate with Google Gemini (Generative AI). If Gemini
isn't configured, the adapter uses a deterministic stub so the API is usable
locally.

Files added:
- `backend/app.py` — Flask application with `/analyze` endpoint
- `backend/gemini_client.py` — Gemini adapter (stub fallback included)
- `backend/requirements.txt` — minimal dependencies
- `controller.py` — top-level entrypoint (runs the Flask app)

Quick start (macOS / zsh):

1. Create and activate a virtualenv (recommended):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

2. (Optional) Install and configure Gemini/Generative AI client and credentials.
   - If using an API key, set `GOOGLE_API_KEY`.
   - Or set `GOOGLE_APPLICATION_CREDENTIALS` to your service-account JSON.

3. Run the app:

```bash
python controller.py
```

4. Example request:

```bash
curl -X POST http://localhost:5000/analyze \
  -H "Content-Type: application/json" \
  -d '{"message": "I need help drafting a contract for a freelancer."}'
```

Response shape:

```json
{
  "message": {
    "raw_text": "...",
    "task_type": "contract",
    "confidence": 0.75,
    "draft": "... generated draft ...",
    "status": "ok"
  }
}
```

Notes:
- The Gemini adapter in `backend/gemini_client.py` contains examples and
  fallbacks — you should replace the call site with the exact client calls
  matching the library you choose to install.
