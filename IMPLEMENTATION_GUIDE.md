# Automated Marketing Content System Implementation Guide

This guide is derived from:

1. `improved_approach_final (2).docx`
2. `uiux_upgrade_addendum (1).docx`

These documents are treated as the authoritative blueprint.

## Phase 1: Planning and Setup

1. Create the project skeleton.
   Purpose: establish the exact app boundaries before any integration work.
   Suggested structure:
   ```text
   AISSM/
   ├─ app/
   │  └─ main.py
   ├─ services/
   │  ├─ memory_service.py
   │  ├─ rag_chain.py
   │  ├─ input_sanitizer.py
   │  ├─ content_validator.py
   │  ├─ brand_scorer.py
   │  ├─ image_service.py
   │  ├─ carousel_service.py
   │  ├─ package_builder.py
   │  └─ notification_service.py
   ├─ models/
   │  └─ schemas.py
   ├─ ui/
   │  └─ app.py
   ├─ data/
   │  ├─ brand_guidelines.json
   │  ├─ seed_posts.json
   │  ├─ mock_trends.json
   │  ├─ mock_events.json
   │  ├─ fonts/
   │  └─ lottie/
   │     ├─ sdxl_loading.json
   │     └─ scraper_pulse.json
   ├─ output/
   ├─ tests/
   ├─ requirements.txt
   ├─ .env
   ├─ docker-compose.yml
   └─ start.sh
   ```

2. Lock the runtime and dependency versions.
   Purpose: avoid Trap 5 from the blueprint.
   Requirements:
   - Python `3.11`
   - CUDA `12.1`
   - Streamlit `1.35`
   - LangChain `0.2`
   - `streamlit-lottie==0.0.5`
   - `requests==2.31.0`
   - `json-repair`
   - `tiktoken`
   - `chromadb`
   - `sentence-transformers`
   - `fastapi`
   - `uvicorn`
   - `httpx`
   - `slack-sdk`
   - `imageio`
   - `Pillow`
   - `diffusers`
   - `transformers`
   - `bitsandbytes`
   - `xformers`

3. Prepare `.env`.
   Purpose: centralize provider toggles and secrets.
   ```env
   LLM_PROVIDER=ollama
   IMAGE_PROVIDER=local
   OLLAMA_BASE_URL=http://localhost:11434
   GROQ_API_KEY=
   FAL_API_KEY=
   SLACK_WEBHOOK_URL=
   CHROMA_DIR=./data/chroma
   SQLITE_PATH=./data/history.db
   FASTAPI_URL=http://localhost:8000
   ```

4. Pre-download all local assets before build execution.
   Purpose: satisfy Trap 1 and the Lottie addendum.
   Required assets:
   - Ollama model: `mistral` or `mistral:7b-instruct`
   - Hugging Face SDXL-Turbo weights
   - Google font files in `data/fonts/`
   - Lottie JSON files in `data/lottie/`

5. Seed the local data layer.
   Purpose: enable Chroma retrieval, mock scraper flows, and brand validation.
   Required files:
   - `data/brand_guidelines.json`
   - `data/seed_posts.json`
   - `data/mock_trends.json`
   - `data/mock_events.json`

6. Build the Pydantic schema layer first.
   Purpose: every API, LangChain, validation, and packaging step depends on it.
   Core models:
   - `FeatureInput`
   - `PlatformCopy`
   - `GeneratedCopy`
   - `ValidationResult`
   - `TokenStats`
   - `VariantRequest`

## Phase 2: Sequential Implementation

### 1. Implement FastAPI app bootstrap

File: `app/main.py`

Tasks:
1. Create `FastAPI()` instance.
2. Add `CORSMiddleware` for `http://localhost:8501`.
3. Add `/health` route.
4. Add startup hook to warm embeddings and brand anchor state.

Starter:
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Automated Marketing Content System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"ok": True}
```

Prerequisite: schemas and services stubs must exist.

### 2. Implement Chroma DB and embedding memory

File: `services/memory_service.py`

Purpose:
- persist `posts` and `brand` collections
- support top-3 retrieval filtered by platform and engagement score

Implementation steps:
1. Initialize persistent Chroma client at `./data/chroma`.
2. Load `sentence-transformers/all-MiniLM-L6-v2`.
3. Create collections: `posts`, `brand`.
4. Ingest `seed_posts.json` at startup if empty.
5. Truncate post text to about `320` chars for prompt usage.
6. Expose:
   - `pre_warm()`
   - `retrieve_similar(query, platform, k=3)`
   - `top_brand_posts()`

Connection point:
- called by `app/main.py` startup
- called by `services/rag_chain.py`
- called by `services/brand_scorer.py`

Troubleshooting:
- If Chroma locks its files, delete only the `data/chroma` dev directory, not your seed JSON.
- If embeddings are slow on first run, that is expected; warm them at startup.

### 3. Implement input sanitization and token guardrails

File: `services/input_sanitizer.py`

Purpose:
- enforce the blueprint's Layer 1 guard
- prevent prompt injection and runaway context size

Implementation:
1. Strip phrases like `ignore`, `forget`, `system prompt`, `developer`.
2. Wrap feature text in delimiters before prompt assembly.
3. Count tokens with `tiktoken`.
4. Reject unsafe or oversized inputs with HTTP `422`.

Suggested functions:
```python
def sanitize_text(value: str) -> str: ...
def wrap_user_block(value: str) -> str: ...
def count_tokens(value: str) -> int: ...
```

### 4. Implement Ollama integration

File: `services/rag_chain.py`

Purpose:
- use local Ollama as the primary LLM provider
- create separate creative and structured passes

Setup steps:
1. Install Ollama locally.
2. Pull model:
   ```powershell
   ollama pull mistral
   ```
3. Verify service:
   ```powershell
   ollama list
   ollama serve
   ```
4. Configure two LLM instances:
   - creative: `temperature=0.75`, `seed=42`, `num_predict=1200`
   - structured: `temperature=0.1`, `seed=42`, `num_predict=400`
5. Set `keep_alive=0` to allow VRAM release before image generation.

Example shape:
```python
llm_creative = OllamaLLM(
    model="mistral",
    temperature=0.75,
    seed=42,
    keep_alive=0,
    num_predict=1200,
)
```

Troubleshooting:
- If VRAM does not drop after generation, confirm your Ollama version supports `keep_alive=0`.
- If throughput is poor, check that Ollama is using GPU and not CPU fallback.

### 5. Implement fallback LLM provider

Purpose:
- satisfy the blueprint fallback path

Steps:
1. Add `GROQ_API_KEY` to `.env`.
2. Build a provider switch with `LLM_PROVIDER=ollama|groq`.
3. Match output schema and retry behavior exactly so both providers return the same shape.

### 6. Implement the master prompt and RAG chain

File: `services/rag_chain.py`

Prompt sections required by the blueprint:
1. System brand voice and tone rules.
2. Forbidden words and hallucination prohibition.
3. Two good examples and one bad example from Chroma memory.
4. Top trends from `mock_trends.json`.
5. User feature block wrapped in delimiters.
6. Dynamic output schema limited to selected platforms.

Execution flow:
1. Retrieve top-3 RAG posts.
2. Load brand guidelines and trends.
3. Build prompt.
4. Generate creative content.
5. Run structured JSON formatting pass.
6. Repair JSON if needed.
7. Retry up to two times.
8. Return graceful fallback if parsing still fails.

### 7. Implement platform adaptation

File: `services/platform_adapter.py`

Purpose:
- make content platform-compliant after base generation

Rules from blueprint:
- LinkedIn: `<=1300` chars, `3-5` hashtags
- X/Twitter: `<=280` chars, `2-3` hashtags, optional thread split
- Instagram: `<=2200` chars, `20-30` hashtags moved to comment field

### 8. Implement validation and brand scoring

Files:
- `services/content_validator.py`
- `services/brand_scorer.py`

Validation checks:
1. hallucination regex scan for numbers, percentages, claims
2. competitor mention scan
3. forbidden word scan
4. cross-platform similarity scoring
5. hashtag validation

Brand score thresholds:
- `>=80`: pass
- `65-79`: warn
- `<65`: silent regeneration

### 9. Implement `/generate` streaming endpoint

File: `app/main.py`

Purpose:
- run the full text generation pipeline with SSE

Required flow:
1. sanitize input
2. count tokens
3. fetch RAG docs
4. build prompt
5. stream generation
6. validate output
7. score output
8. persist token stats and history

SSE response shape:
```python
return StreamingResponse(
    token_generator(),
    media_type="text/event-stream",
    headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
)
```

Troubleshooting:
- if streaming stalls, run uvicorn with `--timeout-keep-alive 120`
- if Streamlit hangs, keep `httpx` timeout at `120`

### 10. Integrate SDXL Turbo

File: `services/image_service.py`

Purpose:
- local hero image generation after LLM unload

Blueprint-safe sequence:
1. finish LLM call
2. `keep_alive=0`
3. `gc.collect()`
4. `torch.cuda.empty_cache()`
5. `torch.cuda.synchronize()`
6. `sleep(4)`
7. load SDXL-Turbo in int8
8. generate image
9. unload pipeline

Key code areas:
- `generate_hero(prompt, session_id)`
- `apply_brand_overlay(image, brand_config)`
- `resize_for_platform(image, platform)`

Troubleshooting:
- if `out of memory` occurs, immediately switch to Fal AI
- if local generation exceeds ~25s consistently, verify CUDA, xformers, and quantization

### 11. Integrate FAL AI fallback

File: `services/image_service.py`

Purpose:
- serve as zero-VRAM fallback for image generation

Setup:
1. add `FAL_API_KEY` to `.env`
2. install the FAL client your chosen SDK requires
3. wrap local SDXL generation in `try/except RuntimeError`
4. on OOM, call FAL:
   ```python
   result = fal_client.run(
       "fal-ai/fast-sdxl",
       arguments={"prompt": prompt}
   )
   ```

Connection point:
- this should be transparent to the UI
- UI still calls a single `/generate-image` endpoint

### 12. Implement carousel, GIF, and MP4 generation

File: `services/carousel_service.py`

Purpose:
- produce non-VRAM visual assets from generated copy

Required outputs:
- `slide_01.png` to `slide_05.png`
- `carousel.gif`
- `launch_video.mp4`

### 13. Implement packaging and notification services

Files:
- `services/package_builder.py`
- `services/notification_service.py`

Package contents:
- platform text files
- image assets
- carousel assets
- manifest
- validation result
- token stats

Notification:
- send Slack webhook after successful package creation
- failure must not crash the pipeline

### 14. Build the Streamlit UI

File: `ui/app.py`

Required UI structure from blueprint:
1. `st.set_page_config(layout="wide")`
2. full `st.session_state` initialization at top
3. tabs:
   - `Generate`
   - `Visuals`
   - `History`
4. left column form
5. right column streaming output and score

### 15. Integrate Lottie animations

Files:
- `ui/app.py`
- `data/lottie/sdxl_loading.json`
- `data/lottie/scraper_pulse.json`

Where to find animations:
1. `lottiefiles.com`
2. search terms:
   - `AI loading`
   - `neural network pulse`
   - `radar pulse`
   - `signal wave`

Placement required by addendum:
1. sidebar scraper pulse
2. Tab 2 SDXL loading state

Loader code:
```python
import json
from streamlit_lottie import st_lottie

def load_lottie(filepath: str):
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)
```

Important UI rule:
- never animate the SSE output container
- inject global CSS once, before streaming starts

### 16. Add `st.status()` and `st.toast()`

File: `ui/app.py`

Purpose:
- reflect pipeline state cleanly without conflicting with live SSE updates

Use:
1. `st.status()` during text generation pipeline
2. `st.toast()` after image generation, Slack success, and auto-improvement

### 17. Add the web scraper after the core app works

Suggested placement:
- `services/web_scraper.py`
- API trigger in `app/main.py`
- optional UI trigger in sidebar or admin control

Integration steps:
1. scrape or ingest external source data
2. normalize it into the same shape as `mock_events.json`
3. push result into `FeatureInput`
4. optionally write new trend records to `mock_trends.json` replacement storage

Minimal structure:
```python
class WebScraperService:
    def fetch_events(self) -> list[dict]:
        ...

    def to_feature_input(self, raw_event: dict) -> dict:
        ...
```

Workflow connection:
1. scraper gathers event
2. FastAPI route returns event payload
3. Streamlit pre-fills form
4. standard `/generate` pipeline continues unchanged

### 18. Run integration testing in blueprint order

Test passes:
1. form submit to SSE generation
2. mock scraper prefill
3. one-platform dynamic schema
4. VRAM release between Ollama and SDXL
5. JSON repair fallback
6. brand score regeneration
7. package download
8. Slack notification
9. Lottie and CSS behavior without Streamlit flashing

## Recommended Build Order Summary

1. Project structure and dependencies
2. `.env` and static data
3. schemas
4. FastAPI bootstrap
5. Chroma memory
6. sanitizer and token counting
7. Ollama chain
8. fallback LLM
9. validators and scorer
10. `/generate` SSE endpoint
11. SDXL Turbo local image generation
12. Fal AI fallback
13. carousel and packaging
14. Streamlit UI
15. Lottie enhancements
16. web scraper
17. testing and Docker

## Most Important Dependency Order

1. Chroma DB before RAG
2. Ollama before `/generate`
3. brand scorer after embeddings
4. SDXL Turbo only after Ollama unload is confirmed
5. web scraper only after the core generation path is stable
6. Lottie only after the base Streamlit layout is stable

## Common Failure Points

1. Ollama keeps VRAM allocated and blocks SDXL.
   Fix: verify `keep_alive=0`, force cache cleanup, add sleep.

2. SSE hangs in Streamlit.
   Fix: use async generator, set `X-Accel-Buffering: no`, keep timeouts at `120`.

3. Streamlit reruns wipe results.
   Fix: write every generated artifact into `st.session_state` immediately.

4. CSS or animation causes flashing during token streaming.
   Fix: keep the streaming output area static; animate only Lottie and post-generation score containers.

5. Chroma retrieval returns weak examples.
   Fix: filter by platform and `engagement_score >= 0.6`, keep top-3 only.
