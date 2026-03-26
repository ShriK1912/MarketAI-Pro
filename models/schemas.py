from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


PlatformName = Literal["linkedin", "twitter", "instagram"]


class FeatureInput(BaseModel):
    feature_name: str = Field(min_length=3, max_length=120)
    description: str = Field(min_length=10, max_length=500)
    target_audience: str = Field(min_length=3, max_length=180)
    tone: str = Field(default="professional", min_length=3, max_length=60)
    platforms: list[PlatformName] = Field(min_length=1)
    brand_name: str | None = None

    @field_validator("platforms")
    @classmethod
    def validate_unique_platforms(cls, value: list[PlatformName]) -> list[PlatformName]:
        return list(dict.fromkeys(value))


class PlatformCopy(BaseModel):
    platform: PlatformName
    caption: str
    hashtags: list[str] = Field(default_factory=list)
    cta: str = ""
    hashtags_comment: list[str] = Field(default_factory=list)
    compliant: bool = True
    thread: list[str] = Field(default_factory=list)


class CarouselSlide(BaseModel):
    title: str
    body: str


class GeneratedCopy(BaseModel):
    feature_name: str
    summary: str
    image_prompt: str
    linkedin: PlatformCopy | None = None
    twitter: PlatformCopy | None = None
    instagram: PlatformCopy | None = None
    carousel: list[CarouselSlide] = Field(default_factory=list, max_length=5)
    raw_output: str | None = None


class ValidationResult(BaseModel):
    hallucination_flags: list[str] = Field(default_factory=list)
    competitor_flags: list[str] = Field(default_factory=list)
    forbidden_flags: list[str] = Field(default_factory=list)
    similarity_flags: list[str] = Field(default_factory=list)
    regenerated: bool = False
    original_score: float | None = None


class TokenStats(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    generation_time_ms: int = 0
    retries_used: int = 0
    provider: str = "ollama"
    model: str = "mistral"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class GenerateResponse(BaseModel):
    session_id: str
    generated_copy: GeneratedCopy = Field(alias="copy")
    validation: ValidationResult
    brand_score: float
    token_stats: TokenStats

    model_config = ConfigDict(populate_by_name=True)


class VariantRequest(BaseModel):
    original_copy: str = Field(min_length=20)
    original_tone: str = Field(min_length=3, max_length=60)
    variant_tone: str = Field(min_length=3, max_length=60)


class ImageRequest(BaseModel):
    session_id: str
    prompt: str
    platforms: list[PlatformName] = Field(default_factory=lambda: ["linkedin", "instagram"])


class ImageResponse(BaseModel):
    image_path: str
    image_paths_by_platform: dict[str, str] = Field(default_factory=dict)


class OnboardingSummary(BaseModel):
    extracted_preview: str = ""
    parsed_fields: dict[str, str] = Field(default_factory=dict)
    detected_brand_name: str = ""
    search_status: str = "not_attempted"
    rate_limited: bool = False
    search_errors: list[str] = Field(default_factory=list)
    search_queries: list[str] = Field(default_factory=list)
    snippet_count: int = 0
    snippets: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    page_summaries: list[str] = Field(default_factory=list)
    social_post_highlights: dict[str, list[str]] = Field(default_factory=dict)
    used_web_context: bool = False


class MockEvent(BaseModel):
    feature_name: str
    description: str
    target_audience: str


class HistoryRecord(BaseModel):
    session_id: str
    feature_name: str
    brand_score: float
    token_count: int
    generation_time_ms: int
    platforms: list[str]
    zip_path: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
