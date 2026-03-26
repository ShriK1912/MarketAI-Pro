# Setup Guide

## Target environment

The blueprint targets:

1. Python `3.11`
2. CUDA `12.1`
3. Ollama installed locally
4. Optional Groq and Fal API keys for fallback paths

## Recommended local setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

If your machine currently defaults to Python 3.14, install Python 3.11 first and create the venv with that interpreter:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python --version
```

## Ollama

```powershell
ollama pull mistral
ollama serve
```

Environment:
```env
LLM_PROVIDER=ollama
OLLAMA_MODEL=mistral
OLLAMA_BASE_URL=http://localhost:11434
```

Quick verification:
```powershell
ollama list
curl http://localhost:11434/api/tags
```

## Chroma DB

No external service is required. Data persists locally under:

`data/chroma/`

## SDXL Turbo

Local path:

1. Set `IMAGE_PROVIDER=local`
2. Ensure `torch`, `diffusers`, and GPU support are correctly installed
3. The service attempts local SDXL first, then falls back if unavailable

Expected code path in this repo:

1. [image_service.py](c:/Users/Lenovo/Desktop/AISSM/services/image_service.py) tries local `stabilityai/sdxl-turbo`
2. It uses `num_inference_steps=4` and `guidance_scale=0.0`
3. If local generation fails, it can fall back to Fal

Fallback path:

```env
IMAGE_PROVIDER=api
FAL_API_KEY=your_key_here
```

The repo uses `fal-client`, and the code reads `FAL_API_KEY` from `.env`.

## Lottie assets

Put real animation files here:

1. `data/lottie/sdxl_loading.json`
2. `data/lottie/scraper_pulse.json`

Recommended searches on LottieFiles:

1. `AI loading`
2. `neural network pulse`
3. `radar pulse`
4. `signal wave`

Recommended constraints:

1. keep each file under about `200 KB`
2. use a looping animation
3. avoid extremely busy animations during the demo

## Run

Backend:
```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --timeout-keep-alive 120
```

Frontend:
```powershell
streamlit run ui/app.py --server.port 8501
```

Or use:
```powershell
.\start.ps1
```

## Important note for this machine

The current workspace has been developed with fallback guards because Python `3.14` is installed here, while the blueprint stack is designed around Python `3.11`.

For the full intended provider stack, move to Python `3.11`.

## Readiness check

After setup, call:

```powershell
curl http://localhost:8000/health
```

You want these to be true for the real flow:

1. `ollama_reachable`
2. `sdxl_lottie_present`
3. `scraper_lottie_present`

`fal_key_configured` only needs to be true if you want the Fal fallback.
