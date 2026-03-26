from __future__ import annotations

import concurrent.futures
import json
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from models.schemas import OnboardingSummary
from services.rag_chain import RAGChain
from services.template_store import BrandTemplate, TemplateStore
from services.web_scraper import WebScraperService

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover
    PdfReader = None


class TemplateBuilder:
    def __init__(self) -> None:
        self.rag = RAGChain()
        self.store = TemplateStore()
        self.scraper = WebScraperService()

    def build_from_upload(self, filename: str, content: bytes) -> BrandTemplate:
        document_text = self.extract_document_text(filename, content)
        return self.build_from_document(document_text)

    def extract_document_text(self, filename: str, content: bytes) -> str:
        suffix = Path(filename or "document.txt").suffix.lower()
        if suffix in {".txt", ".md"}:
            return content.decode("utf-8", errors="ignore")
        if suffix == ".docx":
            return self._extract_docx_text(content)
        if suffix == ".pdf":
            return self._extract_pdf_text(content)
        raise ValueError(f"Unsupported file type: {suffix or 'unknown'}")

    def build_from_document(self, document_text: str) -> BrandTemplate:
        base_data = self._extract_structured_template(document_text)
        if not self._looks_complete(base_data):
            llm_data = self._extract_base_template(document_text)
            base_data = self._merge_template_data(base_data, llm_data)
        brand_name = base_data.get("brand_name", "").strip() or "Unknown Brand"
        brand_context = self._gather_brand_context(brand_name) if brand_name != "Unknown Brand" else None

        if brand_context and brand_context.found:
            enriched_data = self._enrich_template(base_data, brand_context.as_text())
            enriched_data = self._merge_web_examples(enriched_data, brand_context)
            enriched_context = brand_context.as_text()
        else:
            enriched_data = dict(base_data)
            enriched_context = "No verified public web context found. Keep the brand template document-led and generic."

        template = BrandTemplate(
            brand_name=enriched_data.get("brand_name", brand_name),
            core_voice=enriched_data.get("core_voice", base_data.get("core_voice", "")),
            mission=enriched_data.get("mission", base_data.get("mission", "")),
            tone_words=self._as_list(enriched_data.get("tone_words", base_data.get("tone_words", []))),
            forbidden_words=self._as_list(enriched_data.get("forbidden_words", base_data.get("forbidden_words", []))),
            competitors=self._as_list(enriched_data.get("competitors", base_data.get("competitors", []))),
            required_cta=enriched_data.get("required_cta", base_data.get("required_cta", "")),
            visual_aesthetic=enriched_data.get("visual_aesthetic", base_data.get("visual_aesthetic", "")),
            linkedin_rules=enriched_data.get("linkedin_rules", base_data.get("linkedin_rules", "Professional, 3-4 short paragraphs.")),
            twitter_rules=enriched_data.get("twitter_rules", base_data.get("twitter_rules", "Short, punchy, under 280 characters.")),
            instagram_rules=enriched_data.get("instagram_rules", base_data.get("instagram_rules", "Visual, spaced, emoji-friendly, 10-15 hashtags.")),
            enriched_context=enriched_context,
            top_performing_posts=self._as_list(
                enriched_data.get("top_performing_posts", base_data.get("top_performing_posts", []))
            ),
            platform_examples=self._normalize_platform_examples(
                enriched_data.get("platform_examples", base_data.get("platform_examples", {}))
            ),
            onboarding_summary=self._build_onboarding_summary(document_text, enriched_data, brand_context).model_dump(),
        )

        self.store.save_template(template)
        return template

    def _build_onboarding_summary(self, document_text: str, data: dict, brand_context) -> OnboardingSummary:
        parsed_fields = {
            "brand_name": str(data.get("brand_name", "")).strip(),
            "mission": str(data.get("mission", "")).strip(),
            "core_voice": str(data.get("core_voice", "")).strip(),
            "visual_aesthetic": str(data.get("visual_aesthetic", "")).strip(),
            "required_cta": str(data.get("required_cta", "")).strip(),
        }
        return OnboardingSummary(
            extracted_preview=document_text[:800].strip(),
            parsed_fields={key: value for key, value in parsed_fields.items() if value},
            detected_brand_name=parsed_fields.get("brand_name", ""),
            search_status=(brand_context.status if brand_context else "not_attempted"),
            rate_limited=bool(brand_context.rate_limited) if brand_context else False,
            search_errors=(brand_context.errors[:5] if brand_context else []),
            search_queries=(brand_context.queries[:6] if brand_context else []),
            snippet_count=len(brand_context.snippets) if brand_context else 0,
            snippets=(brand_context.snippets[:3] if brand_context else []),
            sources=(brand_context.sources[:5] if brand_context else []),
            page_summaries=(brand_context.page_summaries[:3] if brand_context else []),
            social_post_highlights=(brand_context.grouped_social_posts() if brand_context else {}),
            used_web_context=bool(brand_context and brand_context.found),
        )

    def _merge_web_examples(self, data: dict, brand_context) -> dict:
        merged = dict(data)
        social_groups = brand_context.grouped_social_posts()
        top_posts = self._as_list(merged.get("top_performing_posts", []))
        platform_examples = self._normalize_platform_examples(merged.get("platform_examples", {}), top_posts)

        for platform, posts in social_groups.items():
            platform_examples.setdefault(platform, [])
            for post in posts:
                if post not in platform_examples[platform]:
                    platform_examples[platform].append(post)
                if post not in top_posts:
                    top_posts.append(post)

        merged["top_performing_posts"] = top_posts[:8]
        merged["platform_examples"] = {key: value[:4] for key, value in platform_examples.items()}
        return merged

    def _extract_structured_template(self, document_text: str) -> dict:
        sections = self._parse_sections(document_text)
        top_posts = self._parse_numbered_list(sections.get("top-performing posts", ""))
        platform_examples = self._parse_platform_examples(sections.get("platform examples", ""))
        data = {
            "brand_name": sections.get("brand name", "").strip() or self._infer_brand_name(document_text),
            "core_voice": sections.get("core voice", "").strip(),
            "mission": sections.get("mission", "").strip(),
            "tone_words": self._parse_simple_list(sections.get("tone words", "")),
            "forbidden_words": self._parse_simple_list(sections.get("forbidden words", "")),
            "competitors": self._parse_simple_list(sections.get("competitors", "")),
            "required_cta": sections.get("required cta", "").strip(),
            "visual_aesthetic": sections.get("visual aesthetic", "").strip(),
            "linkedin_rules": sections.get("linkedin rules", "").strip(),
            "twitter_rules": sections.get("twitter rules", "").strip(),
            "instagram_rules": sections.get("instagram rules", "").strip(),
            "top_performing_posts": top_posts,
            "platform_examples": platform_examples,
        }
        return self._with_defaults(data, document_text)

    def _extract_base_template(self, document_text: str) -> dict:
        prompt = f"""
Extract a brand template from the document below.
Return JSON only with exactly these keys:
- brand_name: string
- core_voice: string
- mission: string
- tone_words: array of strings
- forbidden_words: array of strings
- competitors: array of strings
- required_cta: string
- visual_aesthetic: string
- linkedin_rules: string
- twitter_rules: string
- instagram_rules: string
- top_performing_posts: array of strings
- platform_examples: object with keys linkedin, twitter, instagram and array-of-string values

Use the document as the primary source of truth. If top-performing posts are present, extract the strongest examples.

Document:
{document_text[:7000]}
        """.strip()
        try:
            raw_json = self._invoke_llm_with_timeout(self.rag.llm_structured or self.rag.llm_creative, prompt, timeout=20)
            data = self.rag.repair_output(raw_json)
        except Exception:
            data = {}
        return self._with_defaults(data, document_text)

    def _enrich_template(self, base_data: dict, web_context: str) -> dict:
        prompt = f"""
You are enriching an existing brand template with verified public web context.
Preserve the original document-led guidance unless the web context adds confidence.
Return JSON only using the same schema as the input template.

Base template JSON:
{json.dumps(base_data, ensure_ascii=True)}

        Verified web context:
{web_context[:4000]}
        """.strip()
        try:
            raw_json = self._invoke_llm_with_timeout(self.rag.llm_structured or self.rag.llm_creative, prompt, timeout=12)
            data = self.rag.repair_output(raw_json)
        except Exception:
            data = dict(base_data)
        return self._with_defaults(data, "")

    def _with_defaults(self, data: dict, document_text: str) -> dict:
        default_examples = self._extract_candidate_examples(document_text)
        return {
            "brand_name": data.get("brand_name", "Unknown Brand"),
            "core_voice": data.get("core_voice", "Professional, clear, and grounded in product value."),
            "mission": data.get("mission", ""),
            "tone_words": self._as_list(data.get("tone_words", ["professional", "clear"])),
            "forbidden_words": self._as_list(data.get("forbidden_words", [])),
            "competitors": self._as_list(data.get("competitors", [])),
            "required_cta": data.get("required_cta", "Learn more on our website."),
            "visual_aesthetic": data.get("visual_aesthetic", "Modern brand-safe marketing visuals."),
            "linkedin_rules": data.get("linkedin_rules", "3-4 short paragraphs, executive-ready, business value first."),
            "twitter_rules": data.get("twitter_rules", "Under 280 characters, sharp hook, one clear takeaway."),
            "instagram_rules": data.get("instagram_rules", "Visually descriptive, spacious line breaks, emojis, 10-15 hashtags."),
            "top_performing_posts": self._as_list(data.get("top_performing_posts", default_examples)),
            "platform_examples": self._normalize_platform_examples(data.get("platform_examples", {}), default_examples),
        }

    def _extract_candidate_examples(self, document_text: str) -> list[str]:
        lines = [line.strip() for line in document_text.splitlines() if len(line.strip()) >= 40]
        return lines[:5]

    def _parse_sections(self, document_text: str) -> dict[str, str]:
        matches = list(
            re.finditer(
                r"(?im)^(Brand Name|Mission|Core Voice|Tone Words|Forbidden Words|Competitors|Required CTA|Visual Aesthetic|LinkedIn Rules|Twitter Rules|Instagram Rules|Top-Performing Posts|Platform Examples)\s*:\s*",
                document_text,
            )
        )
        sections: dict[str, str] = {}
        for index, match in enumerate(matches):
            key = match.group(1).strip().lower()
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(document_text)
            sections[key] = document_text[start:end].strip()
        return sections

    def _parse_simple_list(self, text: str) -> list[str]:
        items = []
        for line in text.splitlines():
            cleaned = line.strip().lstrip("-").strip()
            if cleaned:
                items.append(cleaned)
        return items

    def _parse_numbered_list(self, text: str) -> list[str]:
        items = []
        for line in text.splitlines():
            cleaned = re.sub(r"^\s*\d+\.\s*", "", line).strip()
            if cleaned:
                items.append(cleaned)
        return items

    def _parse_platform_examples(self, text: str) -> dict[str, list[str]]:
        examples = {"linkedin": [], "twitter": [], "instagram": []}
        current_platform = None
        buffer: list[str] = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            lowered = line.rstrip(":").lower()
            if lowered in examples:
                if current_platform and buffer:
                    examples[current_platform] = ["\n".join(buffer).strip()]
                current_platform = lowered
                buffer = []
                continue
            if current_platform is not None and line:
                buffer.append(line)
        if current_platform and buffer:
            examples[current_platform] = ["\n".join(buffer).strip()]
        return examples

    def _infer_brand_name(self, document_text: str) -> str:
        for line in document_text.splitlines():
            cleaned = line.strip()
            if cleaned:
                return cleaned[:120]
        return "Unknown Brand"

    def _looks_complete(self, data: dict) -> bool:
        return bool(data.get("brand_name") and data.get("core_voice") and data.get("mission"))

    def _merge_template_data(self, base_data: dict, llm_data: dict) -> dict:
        merged = dict(base_data)
        for key, value in llm_data.items():
            if key not in merged or not merged[key]:
                merged[key] = value
        return self._with_defaults(merged, "")

    def _gather_brand_context(self, brand_name: str):
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = executor.submit(self.scraper.gather_brand_context, brand_name)
        try:
            return future.result(timeout=20)
        except Exception:
            future.cancel()
            executor.shutdown(wait=False, cancel_futures=True)
            return None
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    def _invoke_llm_with_timeout(self, llm, prompt: str, timeout: int) -> str:
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = executor.submit(self.rag._invoke_llm, llm, prompt)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError as exc:
            future.cancel()
            executor.shutdown(wait=False, cancel_futures=True)
            raise TimeoutError(f"Template LLM call timed out after {timeout}s") from exc
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    def _normalize_platform_examples(self, value: object, fallback_examples: list[str] | None = None) -> dict[str, list[str]]:
        fallback_examples = fallback_examples or []
        if not isinstance(value, dict):
            value = {}
        normalized: dict[str, list[str]] = {}
        for platform in ("linkedin", "twitter", "instagram"):
            normalized[platform] = self._as_list(value.get(platform, fallback_examples[:2]))
        return normalized

    def _as_list(self, value: object) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str) and value.strip():
            return [part.strip() for part in value.splitlines() if part.strip()]
        return []

    def _extract_docx_text(self, content: bytes) -> str:
        with zipfile.ZipFile(__import__("io").BytesIO(content)) as archive:
            xml = archive.read("word/document.xml")
        root = ElementTree.fromstring(xml)
        namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        parts = [node.text for node in root.findall(".//w:t", namespace) if node.text]
        return "\n".join(parts)

    def _extract_pdf_text(self, content: bytes) -> str:
        if PdfReader is None:
            raise ValueError("PDF parsing requires the optional 'pypdf' dependency.")
        reader = PdfReader(__import__("io").BytesIO(content))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
