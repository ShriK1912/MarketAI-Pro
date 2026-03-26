from __future__ import annotations

from dataclasses import dataclass, field
import time
from urllib.parse import urlparse

import httpx

from services.data_loader import load_mock_events

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover
    BeautifulSoup = None

try:
    from duckduckgo_search import DDGS
except ImportError:  # pragma: no cover
    DDGS = None


@dataclass
class SocialPost:
    platform: str
    title: str
    snippet: str
    url: str

    def as_text(self) -> str:
        parts = [part for part in [self.title.strip(), self.snippet.strip()] if part]
        return " - ".join(parts)[:500]


@dataclass
class BrandContext:
    status: str = "not_attempted"
    rate_limited: bool = False
    errors: list[str] = field(default_factory=list)
    queries: list[str] = field(default_factory=list)
    snippets: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    page_summaries: list[str] = field(default_factory=list)
    social_posts: list[SocialPost] = field(default_factory=list)

    @property
    def found(self) -> bool:
        return bool(self.snippets or self.page_summaries or self.social_posts)

    def grouped_social_posts(self) -> dict[str, list[str]]:
        grouped = {"twitter": [], "linkedin": [], "instagram": []}
        for post in self.social_posts:
            grouped.setdefault(post.platform, [])
            grouped[post.platform].append(post.as_text())
        return {key: value[:3] for key, value in grouped.items() if value}

    def as_text(self) -> str:
        parts: list[str] = []
        if self.queries:
            parts.append("Search queries:\n- " + "\n- ".join(self.queries[:6]))
        if self.snippets:
            parts.append("Search snippets:\n- " + "\n- ".join(self.snippets[:6]))
        social_groups = self.grouped_social_posts()
        if social_groups:
            social_lines: list[str] = []
            for platform, posts in social_groups.items():
                social_lines.append(f"{platform.title()} post signals:")
                social_lines.extend(f"- {post}" for post in posts[:3])
            parts.append("\n".join(social_lines))
        if self.page_summaries:
            parts.append("Website excerpts:\n- " + "\n- ".join(self.page_summaries[:5]))
        if self.sources:
            parts.append("Sources: " + ", ".join(self.sources[:8]))
        return "\n\n".join(parts).strip()


class WebScraperService:
    def fetch_events(self) -> list[dict]:
        return load_mock_events()

    def to_feature_input(self, raw_event: dict) -> dict:
        return {
            "feature_name": raw_event["feature_name"],
            "description": raw_event["description"],
            "target_audience": raw_event["target_audience"],
            "tone": "professional",
            "platforms": ["linkedin", "twitter", "instagram"],
        }

    def gather_brand_context(self, brand_name: str, max_results: int = 4) -> BrandContext:
        if not brand_name.strip() or DDGS is None:
            return BrandContext(status="unavailable")

        queries = [
            f"{brand_name} official site company newsroom about",
            f"{brand_name} site:x.com launch post",
            f"{brand_name} site:twitter.com launch post",
            f"{brand_name} site:linkedin.com/posts announcement",
            f"{brand_name} site:instagram.com/p product launch",
            f'{brand_name} campaign launch product announcement',
        ]

        snippets: list[str] = []
        sources: list[str] = []
        page_summaries: list[str] = []
        social_posts: list[SocialPost] = []
        seen_urls: set[str] = set()
        errors: list[str] = []
        rate_limited = False
        search_attempted = False
        successful_query = False

        for query in queries:
            search_attempted = True
            results, error, hit_rate_limit = self._search_query(query, max_results=max_results)
            if hit_rate_limit:
                rate_limited = True
            if error:
                print(f"[WebScraper] Search failed for query '{query}': {error}")
                errors.append(f"{query}: {error}")
                if hit_rate_limit:
                    break
                continue
            successful_query = True

            for result in results:
                href = (result.get("href") or "").strip()
                title = (result.get("title") or "").strip()
                body = (result.get("body") or "").strip()
                if not href or href in seen_urls:
                    continue
                seen_urls.add(href)

                if body:
                    snippets.append(body[:400])
                sources.append(href)

                platform = self._detect_social_platform(href)
                if platform:
                    social_posts.append(
                        SocialPost(
                            platform=platform,
                            title=title[:220],
                            snippet=body[:350],
                            url=href,
                        )
                    )
                    continue

                page_text = self._fetch_page_text(href)
                if page_text:
                    host = urlparse(href).netloc or href
                    page_summaries.append(f"{host}: {page_text[:700]}")

        status = "success" if successful_query and (snippets or sources or social_posts or page_summaries) else "no_results"
        if not search_attempted:
            status = "not_attempted"
        if rate_limited:
            status = "rate_limited"
        elif errors and not successful_query:
            status = "failed"

        return BrandContext(
            status=status,
            rate_limited=rate_limited,
            errors=errors[:8],
            queries=queries,
            snippets=snippets[:8],
            sources=sources[:10],
            page_summaries=page_summaries[:5],
            social_posts=social_posts[:9],
        )

    def _search_query(self, query: str, max_results: int) -> tuple[list[dict], str, bool]:
        attempts = 2
        last_error = ""
        for attempt in range(attempts):
            try:
                ddgs = DDGS(timeout=10)
                results = list(ddgs.text(query, max_results=max_results))
                return results, "", False
            except Exception as exc:
                message = str(exc)
                last_error = message
                lowered = message.lower()
                rate_limited = "ratelimit" in lowered or "rate limit" in lowered or "202" in lowered
                if rate_limited:
                    if attempt < attempts - 1:
                        time.sleep(2.5)
                        continue
                    return [], message, True
                if attempt < attempts - 1:
                    time.sleep(1.0)
                    continue
                return [], message, False
        return [], last_error or "Unknown search failure", False

    def _detect_social_platform(self, url: str) -> str:
        host = (urlparse(url).netloc or "").lower()
        if "x.com" in host or "twitter.com" in host:
            return "twitter"
        if "linkedin.com" in host:
            return "linkedin"
        if "instagram.com" in host:
            return "instagram"
        return ""

    def _fetch_page_text(self, url: str) -> str:
        try:
            response = httpx.get(
                url,
                timeout=8.0,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; MarketAI/1.0; +https://localhost)"
                },
                follow_redirects=True,
            )
            response.raise_for_status()
        except Exception:
            return ""

        text = response.text
        if BeautifulSoup is None:
            return self._strip_html(text)

        try:
            soup = BeautifulSoup(text, "html.parser")
            for node in soup(["script", "style", "noscript"]):
                node.decompose()
            chunks: list[str] = []
            title = soup.title.get_text(" ", strip=True) if soup.title else ""
            if title:
                chunks.append(title)
            for tag in soup.find_all(["h1", "h2", "p"]):
                content = tag.get_text(" ", strip=True)
                if len(content) >= 40:
                    chunks.append(content)
                if len(" ".join(chunks)) > 1500:
                    break
            return " ".join(chunks)[:1500]
        except Exception:
            return self._strip_html(text)

    def _strip_html(self, text: str) -> str:
        inside_tag = False
        output: list[str] = []
        for char in text:
            if char == "<":
                inside_tag = True
            elif char == ">":
                inside_tag = False
                output.append(" ")
            elif not inside_tag:
                output.append(char)
        collapsed = " ".join("".join(output).split())
        return collapsed[:1500]
