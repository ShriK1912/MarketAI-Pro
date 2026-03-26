from __future__ import annotations

from models.schemas import PlatformCopy


def _normalize_hashtags(hashtags: list[str], minimum: int, maximum: int) -> list[str]:
    cleaned: list[str] = []
    for tag in hashtags:
        candidate = tag if tag.startswith("#") else f"#{tag}"
        if candidate not in cleaned:
            cleaned.append(candidate)
    if not cleaned:
        cleaned = ["#AI", "#Marketing"]
    while len(cleaned) < minimum:
        cleaned.append(cleaned[len(cleaned) % len(cleaned)])
    return cleaned[:maximum]


def _sentence_parts(text: str) -> list[str]:
    normalized = text.replace("\n", " ").strip()
    parts = [part.strip() for part in normalized.split(".") if part.strip()]
    return parts or [normalized]


class PlatformAdapter:
    def adapt_linkedin(self, text: str, hashtags: list[str], cta: str) -> PlatformCopy:
        parts = _sentence_parts(text)
        intro = parts[0]
        middle = parts[1] if len(parts) > 1 else "Teams need launch messaging that makes the business impact obvious"
        takeaway = parts[2] if len(parts) > 2 else "That makes it easier to align stakeholders and move faster"
        tags = _normalize_hashtags(hashtags, minimum=3, maximum=5)
        caption = (
            f"{intro}.\n\n"
            f"{middle}.\n\n"
            f"{takeaway}.\n\n"
            f"{cta}"
        ).strip()
        return PlatformCopy(platform="linkedin", caption=caption[:1300], hashtags=tags, cta=cta, compliant=True)

    def adapt_twitter(self, text: str, hashtags: list[str], cta: str) -> PlatformCopy:
        tags = _normalize_hashtags(hashtags, minimum=2, maximum=3)
        parts = _sentence_parts(text)
        hook = parts[0]
        punch = parts[1] if len(parts) > 1 else "Built for faster launches"
        caption = f"{hook}. {punch}. {' '.join(tags[:2])}".strip()
        caption = caption[:280].rstrip()
        thread = [caption[i : i + 260].strip() for i in range(0, len(caption), 260)] if len(caption) > 140 else []
        return PlatformCopy(platform="twitter", caption=caption, hashtags=tags, cta=cta, compliant=True, thread=thread)

    def adapt_instagram(self, text: str, hashtags: list[str], cta: str) -> PlatformCopy:
        all_tags = _normalize_hashtags(hashtags, minimum=10, maximum=15)
        emoji_text = text if any(char in text for char in "😀✨🚀📈🎯") else f"{text} ✨"
        caption = (
            f"{emoji_text[:700].rstrip()}\n\n"
            "Built to feel visual, polished, and easy to imagine in the real world.\n\n"
            f"{cta}"
        ).strip()
        return PlatformCopy(
            platform="instagram",
            caption=caption[:2200],
            hashtags=all_tags,
            hashtags_comment=all_tags,
            cta=cta,
            compliant=True,
        )
