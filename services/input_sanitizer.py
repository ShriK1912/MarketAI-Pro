from __future__ import annotations

import re

try:
    import tiktoken
except ImportError:  # pragma: no cover
    tiktoken = None


INJECTION_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"\bignore\b",
        r"\bforget\b",
        r"\bsystem prompt\b",
        r"\bdeveloper message\b",
        r"\bignore all previous instructions\b",
    ]
]


class SanitizationError(ValueError):
    pass


def sanitize_text(value: str, max_length: int | None = None) -> str:
    cleaned = value.strip()
    found_patterns: list[str] = []
    for pattern in INJECTION_PATTERNS:
        if pattern.search(cleaned):
            found_patterns.append(pattern.pattern)
            cleaned = pattern.sub("", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        raise SanitizationError("Input became empty after sanitization.")
    if max_length is not None and len(cleaned) > max_length:
        raise SanitizationError(f"Input exceeds {max_length} characters.")
    if found_patterns:
        cleaned = f"{cleaned} [sanitized]"
    return cleaned


def wrap_user_block(value: str) -> str:
    return f"---DATA START---\n{value}\n---DATA END---"


def count_tokens(value: str) -> int:
    if tiktoken is None:
        return len(value.split())
    encoder = tiktoken.get_encoding("cl100k_base")
    return len(encoder.encode(value))
