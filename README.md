# AISSM

Automated marketing content system built from the provided blueprint.

## Current status

This repository is being scaffolded and implemented in blueprint order:

1. Structure and config
2. Schemas and backend bootstrap
3. Memory, sanitization, and orchestration
4. Visual generation and packaging
5. Streamlit UI, scraper, and Lottie enhancements

## What works now

1. FastAPI routes for health, mock events, trends, generation, image generation, history, package download, and notify
2. Streamlit UI shell with sidebar scraper pulse, generation status flow, visuals tab, and history tab
3. Local persistence for history plus output packaging
4. Safe fallbacks for development when provider dependencies are missing

## What still needs real environment assets for full blueprint mode

1. Python 3.11 runtime instead of Python 3.14
2. Real Ollama runtime with downloaded `mistral`
3. Real SDXL Turbo local model environment or Fal API key
4. Real Lottie JSON animation files
5. Optional Slack webhook configuration

See [SETUP.md](c:/Users/Lenovo/Desktop/AISSM/docs/SETUP.md) for the target bring-up path.

## Initial run targets

Backend:
```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --timeout-keep-alive 120
```

Frontend:
```powershell
streamlit run ui/app.py --server.port 8501
```
