from __future__ import annotations

import re
from itertools import combinations

from services.data_loader import load_brand_guidelines
from services.memory_service import get_memory_service


class ContentValidator:
    HALLUCINATION_PATTERNS = [
        re.compile(r"\d+\s*%"),
        re.compile(r"\d+[,.]?\d*\s*(million|billion|thousand|users|customers|downloads)", re.IGNORECASE),
        re.compile(r"over\s+\d+", re.IGNORECASE),
    ]

    def __init__(self) -> None:
        self.memory = get_memory_service()

    def check_hallucinations(self, text: str) -> list[str]:
        flags: list[str] = []
        for pattern in self.HALLUCINATION_PATTERNS:
            flags.extend(match.group(0) for match in pattern.finditer(text))
        return flags

    def check_competitors(self, text: str, template) -> list[str]:
        lowered = text.lower()
        return [name for name in template.competitors if name.lower() in lowered]

    def check_forbidden_words(self, text: str, template) -> list[str]:
        lowered = text.lower()
        return [word for word in template.forbidden_words if word.lower() in lowered]

    def check_platform_rules(self, posts: dict[str, str]) -> list[str]:
        flags = []
        if "twitter" in posts and len(posts["twitter"]) > 280:
            flags.append("Twitter post exceeds 280 characters.")
        if "linkedin" in posts:
            paragraph_count = len([part for part in posts["linkedin"].split("\n\n") if part.strip()])
            if paragraph_count < 3 or paragraph_count > 4:
                flags.append("LinkedIn post should contain 3-4 short paragraphs.")
        if "instagram" in posts and "\n\n" not in posts["instagram"]:
            flags.append("Instagram post should use spaced formatting.")
        return flags

    def validate_hashtags(self, hashtags: list[str]) -> list[str]:
        pattern = re.compile(r"^#[A-Za-z0-9_]{1,29}$")
        return [tag for tag in hashtags if not pattern.match(tag)]

    def check_platform_similarity(self, posts: dict[str, str]) -> list[str]:
        similarity_flags: list[str] = []
        pairs = [(left, right) for left, right in combinations(posts.keys(), 2)]
        if not pairs:
            return similarity_flags
        vectors = self.memory.embed_texts([posts[key] for key in posts])
        keys = list(posts.keys())
        vector_map = dict(zip(keys, vectors))
        for left, right in pairs:
            score = sum(a * b for a, b in zip(vector_map[left], vector_map[right]))
            if score > 0.85:
                similarity_flags.append(f"{left} vs {right}: {score:.2f}")
        return similarity_flags
