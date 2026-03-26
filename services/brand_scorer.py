from __future__ import annotations

from services.memory_service import get_memory_service
from services.template_store import BrandTemplate


class BrandScorer:
    def __init__(self) -> None:
        self.memory = get_memory_service()

    def score(self, text: str, template: BrandTemplate) -> float:
        lowered = text.lower()
        anchors = [template.core_voice, template.mission] + template.top_performing_posts[:2]
        anchors = [anchor for anchor in anchors if anchor]
        if anchors:
            embeddings = self.memory.embed_texts([text] + anchors)
            vector = embeddings[0]
            anchor_vectors = embeddings[1:]
            similarity = sum(
                sum(a * b for a, b in zip(vector, anchor_vector)) for anchor_vector in anchor_vectors
            ) / len(anchor_vectors)
            score = similarity * 55
        else:
            score = 30.0

        if template.required_cta and template.required_cta.lower() in lowered:
            score += 12

        if template.mission and any(word in lowered for word in template.mission.lower().split()[:4]):
            score += 8

        tone_matches = sum(1 for word in template.tone_words if word.lower() in lowered)
        if template.tone_words:
            score += (tone_matches / len(template.tone_words)) * 15

        if template.brand_name and template.brand_name.lower() in lowered:
            score += 5

        if any(word.lower() in lowered for word in template.forbidden_words):
            score -= 20
        if any(name.lower() in lowered for name in template.competitors):
            score -= 15

        return max(0.0, min(100.0, round(score, 2)))
