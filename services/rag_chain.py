from __future__ import annotations

import concurrent.futures
import json
import time
import uuid
from dataclasses import dataclass
from typing import AsyncGenerator

from config import get_settings
from models.schemas import FeatureInput, GenerateResponse, GeneratedCopy, PlatformCopy, TokenStats, ValidationResult
from services.brand_scorer import BrandScorer
from services.content_validator import ContentValidator
from services.data_loader import load_brand_guidelines, load_mock_trends
from services.input_sanitizer import count_tokens, sanitize_text, wrap_user_block
from services.memory_service import get_memory_service
from services.platform_adapter import PlatformAdapter
from services.template_store import BrandTemplate

try:
    from langchain_community.llms import Ollama
except ImportError:  # pragma: no cover
    Ollama = None

try:
    from langchain_groq import ChatGroq
except ImportError:  # pragma: no cover
    ChatGroq = None

try:
    from json_repair import repair_json
except ImportError:  # pragma: no cover
    repair_json = None


@dataclass
class PromptBundle:
    prompt: str
    rag_examples: list[str]
    trends: list[str]


class RAGChain:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.memory = get_memory_service()
        self.adapter = PlatformAdapter()
        self.validator = ContentValidator()
        self.scorer = BrandScorer()
        self.guidelines = load_brand_guidelines()
        self.trends = load_mock_trends()
        self.llm_creative = self._build_llm(temperature=0.75, max_tokens=1200)
        self.llm_structured = self._build_llm(temperature=0.1, max_tokens=400)

    def _build_llm(self, temperature: float, max_tokens: int):
        if self.settings.llm_provider == "groq" and self.settings.groq_api_key and ChatGroq is not None:
            return ChatGroq(
                api_key=self.settings.groq_api_key,
                model=self.settings.groq_model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        if Ollama is not None:
            return Ollama(
                base_url=self.settings.ollama_base_url,
                model=self.settings.ollama_model,
                temperature=temperature,
                num_predict=max_tokens,
                keep_alive=0,
            )
        return None

    def _invoke_llm(self, llm, prompt: str) -> str:
        if llm is None:
            raise RuntimeError("LLM provider is unavailable.")
        if hasattr(llm, "invoke"):
            response = llm.invoke(prompt)
            if isinstance(response, str):
                return response
            if hasattr(response, "content"):
                return str(response.content)
        raise RuntimeError("LLM invocation did not return usable content.")

    def _invoke_llm_with_timeout(self, llm, prompt: str, timeout: int) -> str:
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = executor.submit(self._invoke_llm, llm, prompt)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError as exc:
            future.cancel()
            executor.shutdown(wait=False, cancel_futures=True)
            raise TimeoutError(f"LLM call timed out after {timeout}s") from exc
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    def build_prompt(self, feature: FeatureInput, template: BrandTemplate) -> PromptBundle:
        example_blocks = []
        for platform in ("linkedin", "twitter", "instagram"):
            examples = template.platform_examples.get(platform, [])[:2]
            if examples:
                example_blocks.append(f"{platform.title()} examples:\n- " + "\n- ".join(examples))
        top_posts_block = "\n".join(f"- {post}" for post in template.top_performing_posts[:3])
        image_prompt_seed = self._build_image_prompt(feature, template)
        prompt = f"""
System brand voice: {template.core_voice}
Brand mission: {template.mission}
Tone words: {', '.join(template.tone_words)}
Forbidden words: {', '.join(template.forbidden_words)}
Competitors to avoid: {', '.join(template.competitors)}
Required CTA: {template.required_cta}
Visual aesthetic: {template.visual_aesthetic}

Recent Brand Context: {template.enriched_context}
Top-performing post examples:
{top_posts_block or '- None provided'}

Platform examples:
{chr(10).join(example_blocks) or '- No platform-specific examples provided'}

STRICT PLATFORM RULES:
- linkedin: {template.linkedin_rules}. Must be 3-4 short paragraphs, highly professional, business value focused, and sound executive-ready. Do not reuse Twitter phrasing.
- twitter: {template.twitter_rules}. Must stay under 280 characters including hashtags, open with a punchy hook, and read like a distinct short-form post.
- instagram: {template.instagram_rules}. Must use visual language, spaced line breaks, and 10-15 related hashtags. It should feel expressive and not read like LinkedIn.

Cross-platform rule: do not copy sentences across platforms. Each platform needs a distinct opening line, rhythm, and formatting pattern.

Do not invent statistics, customer counts, percentages, or external facts.

Feature input:
{wrap_user_block(feature.description)}

Generate marketing copy for the following platforms only: {', '.join(feature.platforms)}.
Return JSON with keys: summary, image_prompt, linkedin, twitter, instagram, carousel.
The 'image_prompt' must stay realistic, specific, premium, and visually cinematic.
Base the 'image_prompt' on this seed and improve it without contradicting it:
{image_prompt_seed}

Carousel requirements:
- 5 slides maximum
- each slide should tell a progression, not repeat the same sentence
- titles should sound like campaign headlines, not placeholders

Each platform object needs: caption, hashtags, cta.
        """.strip()
        return PromptBundle(prompt=prompt, rag_examples=[], trends=[])

    def _build_image_prompt(self, feature: FeatureInput, template: BrandTemplate, campaign_summary: str = "") -> str:
        context_lines = []
        for post in template.top_performing_posts[:3]:
            if post:
                context_lines.append(post)
        for platform in ("linkedin", "twitter", "instagram"):
            examples = template.platform_examples.get(platform, [])[:1]
            context_lines.extend(examples)

        social_cues = " | ".join(context_lines[:3]) if context_lines else "No public social post signals available"
        campaign_note = campaign_summary.strip() or feature.description.strip()
        return (
            f"Create a premium B2B marketing hero visual for {feature.feature_name}. "
            f"Audience: {feature.target_audience}. Tone: {feature.tone}. "
            f"Brand aesthetic: {template.visual_aesthetic or 'modern enterprise technology campaign'}. "
            f"Campaign message: {campaign_note}. "
            f"Real-world brand context cues: {social_cues}. "
            "Show a believable product marketing scene with people, modern interfaces, strong composition, cinematic lighting, "
            "editorial-grade typography space, and a clear enterprise story. Avoid empty offices, random stock-photo setups, "
            "wall-mounted screens with unrelated content, obvious text artifacts, and clutter."
        )

    def _fallback_generate(self, feature: FeatureInput, template: BrandTemplate) -> GeneratedCopy:
        brand_name = template.brand_name if template.brand_name and template.brand_name != "Unknown Brand" else "your brand"
        base_text = (
            f"{feature.feature_name} helps {feature.target_audience.lower()} turn product updates into launch-ready messaging with a workflow that feels clearer, faster, and more strategic for {brand_name}."
        )
        hashtags = ["#AI", "#Marketing", "#Automation", "#ProductLaunch", "#B2B"]
        cta = template.required_cta or self.guidelines["required_cta"]
        linkedin_text = (
            f"{feature.feature_name} gives {feature.target_audience.lower()} a clearer path from product context to polished launch messaging. "
            f"It supports {template.mission or 'more consistent campaigns and smoother stakeholder alignment'}. "
            f"The result is a workflow that feels strategic, practical, and easier to approve."
        )
        twitter_text = (
            f"Messy launch inputs slow teams down. {feature.feature_name} turns them into a clear campaign brief for {feature.target_audience.lower()}."
        )
        instagram_text = (
            f"{feature.feature_name} turns scattered launch inputs into something your team can actually picture and ship. "
            f"Clear brief. Polished message. Smoother handoff from product to marketing."
        )
        generated = GeneratedCopy(
            feature_name=feature.feature_name,
            summary=base_text,
            image_prompt=self._build_image_prompt(feature, template, base_text),
            carousel=[
                {"title": "Launch teams need a clearer starting point", "body": "Scattered release notes and brand rules slow down the moment when momentum matters most."},
                {"title": "Turn raw updates into a campaign narrative", "body": "Shape one feature brief into messaging that feels consistent, useful, and ready for every stakeholder."},
                {"title": "Keep every channel on the same story", "body": "Make LinkedIn, X, Instagram, and visuals feel aligned without sounding copied."},
                {"title": "Move from concept to package faster", "body": "Generate posts, visuals, and shareable assets from a single campaign brief."},
                {"title": "Bring the launch to market", "body": cta},
            ],
        )
        if "linkedin" in feature.platforms:
            generated.linkedin = self.adapter.adapt_linkedin(linkedin_text, hashtags, cta)
        if "twitter" in feature.platforms:
            generated.twitter = self.adapter.adapt_twitter(twitter_text, hashtags[:3], cta)
        if "instagram" in feature.platforms:
            generated.instagram = self.adapter.adapt_instagram(instagram_text, hashtags * 6, cta)
        return generated

    def _structured_prompt(self, feature: FeatureInput, draft_text: str) -> str:
        return f"""
Convert the following marketing draft into valid JSON only.
Required top-level keys: feature_name, summary, image_prompt, linkedin, twitter, instagram, carousel.
Each platform object should include caption, hashtags, cta.
Each carousel item should include title and body.
LinkedIn caption must be 3-4 short paragraphs.
Twitter caption must be under 280 characters.
Instagram caption must feel visual and include 10-15 hashtags in the hashtags array.
Feature name: {feature.feature_name}
Platforms: {', '.join(feature.platforms)}
Draft:
{draft_text}
        """.strip()

    def _try_provider_generate(self, feature: FeatureInput, prompt_bundle: PromptBundle) -> GeneratedCopy | None:
        try:
            print(f"[llm-attempt-start] feature={feature.feature_name}")
            creative_text = self._invoke_llm_with_timeout(self.llm_creative, prompt_bundle.prompt, timeout=20)
            structured_prompt = self._structured_prompt(feature, creative_text)
            structured_text = self._invoke_llm_with_timeout(self.llm_structured, structured_prompt, timeout=12)
            payload = self.repair_output(structured_text)
            generated = GeneratedCopy.model_validate(payload)
            print(f"[llm-attempt-success] feature={feature.feature_name}")
            return generated
        except Exception:
            print(f"[llm-attempt-fallback] feature={feature.feature_name}")
            return None

    def _ensure_platform_shapes(self, feature: FeatureInput, generated: GeneratedCopy, template: BrandTemplate) -> GeneratedCopy:
        cta = template.required_cta or self.guidelines["required_cta"]
        if "linkedin" in feature.platforms and generated.linkedin is None:
            generated.linkedin = self.adapter.adapt_linkedin(generated.summary, ["#AI", "#Marketing", "#B2B"], cta)
        if "twitter" in feature.platforms and generated.twitter is None:
            generated.twitter = self.adapter.adapt_twitter(generated.summary, ["#AI", "#Launch"], cta)
        if "instagram" in feature.platforms and generated.instagram is None:
            generated.instagram = self.adapter.adapt_instagram(generated.summary, ["#AI", "#Marketing"] * 12, cta)
        if not generated.carousel:
            generated.carousel = self._fallback_generate(feature, template).carousel
        return self._enforce_platform_rules(generated, template)

    def _enforce_platform_rules(self, generated: GeneratedCopy, template: BrandTemplate) -> GeneratedCopy:
        cta = template.required_cta or self.guidelines["required_cta"]
        if generated.linkedin is not None:
            generated.linkedin = self.adapter.adapt_linkedin(
                generated.linkedin.caption,
                generated.linkedin.hashtags or ["#B2B", "#Marketing", "#Leadership"],
                generated.linkedin.cta or cta,
            )
        if generated.twitter is not None:
            generated.twitter = self.adapter.adapt_twitter(
                generated.twitter.caption,
                generated.twitter.hashtags or ["#Launch", "#AI"],
                generated.twitter.cta or cta,
            )
        if generated.instagram is not None:
            instagram_seed = f"{generated.instagram.caption}\n\nVisual cue: {generated.image_prompt}"
            generated.instagram = self.adapter.adapt_instagram(
                instagram_seed,
                generated.instagram.hashtags or ["#Marketing", "#Brand", "#Creative"] * 4,
                generated.instagram.cta or cta,
            )
        return generated

    def generate(self, feature: FeatureInput) -> GenerateResponse:
        start = time.time()
        feature = FeatureInput(
            feature_name=sanitize_text(feature.feature_name, 120),
            description=sanitize_text(feature.description, 500),
            target_audience=sanitize_text(feature.target_audience, 180),
            tone=sanitize_text(feature.tone, 60),
            platforms=feature.platforms,
            brand_name=feature.brand_name
        )
        
        from services.template_store import TemplateStore
        store = TemplateStore()
        template = None
        if feature.brand_name:
            template = store.load_template(feature.brand_name)
            
        if not template:
            template = BrandTemplate(
                brand_name="Mock Brand",
                core_voice=self.guidelines['voice_description'],
                tone_words=self.guidelines['tone_words'],
                forbidden_words=self.guidelines['forbidden_words'],
                competitors=self.guidelines['competitors'],
                required_cta=self.guidelines['required_cta'],
                visual_aesthetic="Modern corporate tech",
                linkedin_rules="Professional tone",
                twitter_rules="Short hook",
                instagram_rules="Visual emojis"
            )
            
        prompt_bundle = self.build_prompt(feature, template)
        base_input_tokens = count_tokens(prompt_bundle.prompt)
        
        best_generated = None
        best_score = -1.0
        retries_used = 0
        total_input_tokens = 0
        total_output_tokens = 0
        
        for attempt in range(1):
            total_input_tokens += base_input_tokens
            generated = self._try_provider_generate(feature, prompt_bundle) or self._fallback_generate(feature, template)
            generated = self._ensure_platform_shapes(feature, generated, template)
            if generated.feature_name == feature.feature_name and generated.summary.startswith(feature.feature_name):
                print(f"[generation-attempt] feature={feature.feature_name} attempt={attempt + 1} mode={'fallback-or-shaped'}")
            current_output_tokens = count_tokens(generated.model_dump_json())
            total_output_tokens += current_output_tokens
            
            current_score = self.scorer.score(self._combined_text(generated), template)
            
            if current_score > best_score:
                best_score = current_score
                best_generated = generated
                
            if best_score >= 70.0:
                break
                
        best_generated = self._enforce_platform_rules(best_generated, template)
        best_generated.image_prompt = self._build_image_prompt(feature, template, best_generated.summary)
        validation = self.validate_generated_copy(best_generated, template)
        token_stats = TokenStats(
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
            total_tokens=total_input_tokens + total_output_tokens,
            generation_time_ms=int((time.time() - start) * 1000),
            retries_used=retries_used,
            provider=self.settings.llm_provider,
            model=self.settings.ollama_model if self.settings.llm_provider == "ollama" else self.settings.groq_model,
        )
        return GenerateResponse(
            session_id=str(uuid.uuid4()),
            generated_copy=best_generated,
            validation=validation,
            brand_score=best_score,
            token_stats=token_stats,
        )

    async def stream_generate(self, feature: FeatureInput) -> AsyncGenerator[str, None]:
        response = self.generate(feature)
        dump = response.model_dump()
        payload = json.dumps({"event": "final", "data": dump}, default=str)
        for chunk_start in range(0, len(payload), 180):
            yield payload[chunk_start : chunk_start + 180]

    def validate_generated_copy(self, generated: GeneratedCopy, template) -> ValidationResult:
        texts = {}
        for platform in ("linkedin", "twitter", "instagram"):
            item = getattr(generated, platform)
            if isinstance(item, PlatformCopy):
                texts[platform] = item.caption
        combined = " ".join(texts.values())
        platform_flags = self.validator.check_platform_rules(texts)
        return ValidationResult(
            hallucination_flags=self.validator.check_hallucinations(combined) + platform_flags,
            competitor_flags=self.validator.check_competitors(combined, template),
            forbidden_flags=self.validator.check_forbidden_words(combined, template),
            similarity_flags=self.validator.check_platform_similarity(texts),
        )

    def _combined_text(self, generated: GeneratedCopy) -> str:
        parts = [generated.summary]
        for platform in ("linkedin", "twitter", "instagram"):
            item = getattr(generated, platform)
            if isinstance(item, PlatformCopy):
                parts.append(item.caption)
        return " ".join(parts)

    def repair_output(self, raw_json: str) -> dict:
        if repair_json is not None:
            return json.loads(repair_json(raw_json))
        return json.loads(raw_json)
