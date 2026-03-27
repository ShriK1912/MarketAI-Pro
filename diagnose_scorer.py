"""Diagnostic: show exactly what the brand scorer produces step by step."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from services.memory_service import get_memory_service
from services.template_store import BrandTemplate

template = BrandTemplate(
    brand_name="NovaTech AI",
    core_voice="Bold, precise, and forward-thinking. We challenge the status quo and back it with data.",
    mission="Empowering enterprise teams to ship faster, smarter, and with radical clarity through AI-driven automation.",
    tone_words=["bold", "precise", "innovative", "empowering", "clear", "strategic", "trustworthy"],
    forbidden_words=["cheap", "easy", "simple", "guaranteed", "magic", "revolutionary", "disruptive"],
    competitors=["OldStack", "SlowSuite", "ManualOps"],
    required_cta="Discover NovaTech AI at novatech.ai",
    visual_aesthetic="Dark-mode enterprise tech",
    linkedin_rules="3-4 short paragraphs.",
    twitter_rules="Under 280 characters.",
    instagram_rules="Visual, emojis, 10-15 hashtags.",
    top_performing_posts=[
        "The future of enterprise AI isn't just about speed — it's about strategic clarity at every level of the org.",
        "NovaTech AI helped our clients cut campaign build time by 60% without sacrificing brand precision.",
    ],
)

# Simulate a strong LLM output (includes CTA, tone words, brand name, mission words)
sample_text = (
    "NovaTech AI introduces AI Campaign Autopilot — empowering enterprise marketing directors to ship bold, "
    "precise campaigns at scale with strategic clarity. No manual formatting. No brand drift. Just clear, "
    "trustworthy execution that aligns with your mission to move faster with radical clarity. "
    "Discover NovaTech AI at novatech.ai\n\n"
    "AI Campaign Autopilot gives enterprise CMOs a bold new way to publish precise multi-channel campaigns "
    "from a single brief. Strategic and empowering by design.\n\n"
    "Bold moves deserve a precise system. NovaTech AI makes it clear. "
    "Discover NovaTech AI at novatech.ai #NovaTechAI #EnterpriseAI #BoldMarketing"
)

# Simulate weak LLM output (no CTA, no brand name, generic tone)
weak_text = (
    "Introducing AI Campaign Autopilot, a tool that helps marketing teams create content faster. "
    "No more manual work. Publish to all channels from one place. Try it today!"
)

memory = get_memory_service()
lowered_strong = sample_text.lower()
lowered_weak = weak_text.lower()

def diagnose(text, label):
    lowered = text.lower()
    anchors = [template.core_voice, template.mission] + template.top_performing_posts[:2]
    anchors = [a for a in anchors if a]
    embeddings = memory.embed_texts([text] + anchors)
    vector = embeddings[0]
    anchor_vectors = embeddings[1:]
    raw_similarity = sum(
        sum(a * b for a, b in zip(vector, av)) for av in anchor_vectors
    ) / len(anchor_vectors)
    base_score = raw_similarity * 55

    cta_bonus = 12 if template.required_cta and template.required_cta.lower() in lowered else 0
    mission_bonus = 8 if template.mission and any(w in lowered for w in template.mission.lower().split()[:4]) else 0
    tone_matches = sum(1 for w in template.tone_words if w.lower() in lowered)
    tone_bonus = (tone_matches / len(template.tone_words)) * 15 if template.tone_words else 0
    brand_bonus = 5 if template.brand_name and template.brand_name.lower() in lowered else 0
    forbidden_penalty = -20 if any(w.lower() in lowered for w in template.forbidden_words) else 0
    competitor_penalty = -15 if any(c.lower() in lowered for c in template.competitors) else 0

    total = max(0.0, min(100.0, base_score + cta_bonus + mission_bonus + tone_bonus + brand_bonus + forbidden_penalty + competitor_penalty))

    print(f"\n{'='*60}")
    print(f"LABEL: {label}")
    print(f"{'='*60}")
    print(f"  raw_similarity (dot product of normalized vecs): {raw_similarity:.4f}")
    print(f"  base_score (similarity * 55):                    {base_score:.2f}")
    print(f"  cta_bonus:       +{cta_bonus}  (CTA '{template.required_cta[:30]}...' found: {bool(cta_bonus)})")
    print(f"  mission_bonus:   +{mission_bonus:.2f}")
    print(f"  tone_bonus:      +{tone_bonus:.2f}  ({tone_matches}/{len(template.tone_words)} tone words found)")
    print(f"  brand_bonus:     +{brand_bonus}")
    print(f"  forbidden:       {forbidden_penalty}")
    print(f"  competitor:      {competitor_penalty}")
    print(f"  TOTAL SCORE:     {total:.2f}")

diagnose(sample_text, "STRONG (with CTA, brand, tone words, mission)")
diagnose(weak_text, "WEAK (generic, no CTA, no brand name)")
print("\nDone.")
