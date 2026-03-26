from __future__ import annotations

import time
import random
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse
from fastapi.responses import StreamingResponse

from config import get_settings
from models.schemas import FeatureInput, HistoryRecord, ImageRequest, VariantRequest
from services.carousel_service import CarouselService
from services.data_loader import load_mock_events, load_mock_trends
from services.history_service import HistoryService
from services.image_service import ImageService
from services.memory_service import get_memory_service
from services.notification_service import NotificationService
from services.package_builder import PackageBuilder
from services.rag_chain import RAGChain
from services.session_store import SessionStore
from services.web_scraper import WebScraperService


@asynccontextmanager
async def lifespan(_: FastAPI):
    get_memory_service().pre_warm()
    yield


settings = get_settings()
app = FastAPI(title="Automated Marketing Content System", lifespan=lifespan)
rag_chain = RAGChain()
scraper_service = WebScraperService()
image_service = ImageService()
history_service = HistoryService()
package_builder = PackageBuilder()
carousel_service = CarouselService()
notification_service = NotificationService()
session_store = SessionStore()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[f"http://localhost:{settings.streamlit_port}"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, object]:
    memory = get_memory_service()
    ollama_ok = False
    try:
        response = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=2.0)
        ollama_ok = response.status_code == 200
    except Exception:
        ollama_ok = False
    return {
        "ok": True,
        "llm_provider": settings.llm_provider,
        "image_provider": settings.image_provider,
        "ollama_reachable": ollama_ok,
        "fal_key_configured": bool(settings.fal_api_key),
        "sdxl_lottie_present": __import__("pathlib").Path(settings.lottie_sdxl_path).exists(),
        "scraper_lottie_present": __import__("pathlib").Path(settings.lottie_scraper_path).exists(),
        "posts_collection_count": memory.posts_collection.count(),
        "brand_collection_count": memory.brand_collection.count(),
    }


@app.get("/mock-events")
async def mock_event() -> dict[str, str]:
    return random.choice(load_mock_events())


@app.get("/trends")
async def trends() -> dict[str, list[str]]:
    return load_mock_trends()


from pydantic import BaseModel


class OnboardRequest(BaseModel):
    document_text: str


@app.post("/onboard-brand")
async def onboard_brand(request: Request, file: UploadFile | None = File(default=None)) -> dict:
    from services.template_builder import TemplateBuilder

    builder = TemplateBuilder()
    if file is not None:
        content = await file.read()
        template = builder.build_from_upload(file.filename or "document.txt", content)
    else:
        payload = OnboardRequest.model_validate(await request.json())
        template = builder.build_from_document(payload.document_text)
    event = notification_service.notify_template_created(
        brand_name=template.brand_name,
        mission=template.mission,
        used_web_context=bool(template.enriched_context and "No verified public web context found" not in template.enriched_context),
    )
    return {
        "brand_name": template.brand_name,
        "mission": template.mission,
        "stored": True,
        "notification": event,
        "onboarding_summary": template.onboarding_summary,
    }

@app.get("/list-brands")
async def list_brands() -> list[str]:
    from services.template_store import TemplateStore
    store = TemplateStore()
    return store.list_brands()


@app.get("/backend-events")
async def backend_events() -> list[dict[str, object]]:
    return notification_service.list_backend_events()


@app.post("/generate")
async def generate(feature: FeatureInput) -> StreamingResponse:
    async def token_generator():
        try:
            started = time.time()
            print(f"[generate-stream-start] feature={feature.feature_name} brand={feature.brand_name or 'Mock Brand'} platforms={feature.platforms}")
            response = rag_chain.generate(feature)
            history_service.record(
                HistoryRecord(
                    session_id=response.session_id,
                    feature_name=response.generated_copy.feature_name,
                    brand_score=response.brand_score,
                    token_count=response.token_stats.total_tokens,
                    generation_time_ms=response.token_stats.generation_time_ms,
                    platforms=[platform for platform in feature.platforms],
                )
            )
            session_store.save_response(response)
            payload = response.model_dump(mode="json", by_alias=True)
            import json

            print(
                "[generate-stream-complete] "
                f"feature={feature.feature_name} "
                f"duration_ms={int((time.time() - started) * 1000)} "
                f"score={response.brand_score}"
            )
            yield f"data: {json.dumps({'event': 'final', 'data': payload})}\n\n"
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    return StreamingResponse(
        token_generator(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


@app.post("/generate-sync")
async def generate_sync(feature: FeatureInput) -> JSONResponse:
    started = time.time()
    print(f"[generate-sync-start] feature={feature.feature_name} brand={feature.brand_name or 'Mock Brand'} platforms={feature.platforms}")
    response = rag_chain.generate(feature)
    history_service.record(
        HistoryRecord(
            session_id=response.session_id,
            feature_name=response.generated_copy.feature_name,
            brand_score=response.brand_score,
            token_count=response.token_stats.total_tokens,
            generation_time_ms=response.token_stats.generation_time_ms,
            platforms=[platform for platform in feature.platforms],
        )
    )
    session_store.save_response(response)
    print(
        "[generate-sync-complete] "
        f"feature={feature.feature_name} "
        f"duration_ms={int((time.time() - started) * 1000)} "
        f"score={response.brand_score}"
    )
    return JSONResponse(response.model_dump(mode="json", by_alias=True))


@app.post("/generate-variant")
async def generate_variant(request: VariantRequest) -> dict[str, str]:
    rewritten = (
        f"Tone shift to {request.variant_tone}: "
        f"{request.original_copy.strip()} "
        f"(kept factual and CTA-preserving from the {request.original_tone} version)."
    )
    return {"rewritten": rewritten}


@app.get("/scraper/events")
async def scraper_events() -> dict[str, object]:
    events = scraper_service.fetch_events()
    return {"count": len(events), "events": events}


@app.post("/generate-image")
async def generate_image(request: ImageRequest) -> dict[str, object]:
    artifacts = session_store.get(request.session_id)
    if artifacts is None:
        raise HTTPException(status_code=404, detail="Unknown session_id")
    generated_copy = artifacts.response.generated_copy
    image_paths = image_service.generate_hero(
        request.prompt,
        request.session_id,
        headline=generated_copy.feature_name,
        supporting_text=generated_copy.summary,
    )
    slide_paths = carousel_service.render_slides(
        request.session_id,
        artifacts.response.generated_copy.carousel,
        hero_image_path=image_paths.get("instagram") or image_paths.get("linkedin"),
    )
    gif_path = carousel_service.generate_gif(request.session_id, slide_paths)
    mp4_path = carousel_service.generate_mp4(request.session_id, slide_paths)
    session_store.update_assets(
        request.session_id,
        image_paths=image_paths,
        carousel_paths=slide_paths,
        gif_path=gif_path,
        mp4_path=mp4_path,
    )
    return {
        "image_path": image_paths.get("linkedin", ""),
        "image_paths_by_platform": image_paths,
        "carousel_paths": slide_paths,
        "gif_path": gif_path,
        "mp4_path": mp4_path,
    }


@app.get("/history")
async def history() -> list[dict[str, object]]:
    return [record.model_dump(mode="json") for record in history_service.list_records()]


@app.get("/package/{session_id}")
async def get_package(session_id: str) -> FileResponse:
    artifacts = session_store.get(session_id)
    if artifacts is None:
        raise HTTPException(status_code=404, detail="Unknown session_id")
    zip_path = package_builder.build(
        session_id=session_id,
        generated_copy=artifacts.response.generated_copy,
        asset_paths=artifacts.image_paths,
        validation_result=artifacts.response.validation,
        token_stats=artifacts.response.token_stats,
        extra_assets={
            "gif_path": artifacts.gif_path or "",
            "mp4_path": artifacts.mp4_path or "",
        },
    )
    session_store.update_assets(session_id, zip_path=zip_path)
    return FileResponse(zip_path, filename=f"{session_id}.zip")


@app.post("/notify/{session_id}")
async def notify(session_id: str) -> dict[str, object]:
    artifacts = session_store.get(session_id)
    if artifacts is None:
        raise HTTPException(status_code=404, detail="Unknown session_id")
    zip_path = artifacts.zip_path or str(settings.output_dir)
    response = notification_service.send(
        feature_name=artifacts.response.generated_copy.feature_name,
        score=artifacts.response.brand_score,
        platforms=[
            name
            for name in ("linkedin", "twitter", "instagram")
            if getattr(artifacts.response.generated_copy, name) is not None
        ],
        zip_path=zip_path,
    )
    return response
