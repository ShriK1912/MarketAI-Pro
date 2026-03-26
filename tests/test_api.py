from fastapi.testclient import TestClient

from app.main import app
from models.schemas import FeatureInput
from services.platform_adapter import PlatformAdapter
from services.rag_chain import RAGChain
from services.template_builder import TemplateBuilder
from services.template_store import TemplateStore
from services.web_scraper import BrandContext


client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True


def test_mock_event_endpoint():
    response = client.get("/mock-events")
    assert response.status_code == 200
    payload = response.json()
    assert "feature_name" in payload
    assert "description" in payload


def test_generate_variant_endpoint():
    response = client.post(
        "/generate-variant",
        json={
            "original_copy": "A solid launch post with a specific CTA and grounded product value.",
            "original_tone": "professional",
            "variant_tone": "bold",
        },
    )
    assert response.status_code == 200
    assert "rewritten" in response.json()


def test_onboard_brand_upload_endpoint(monkeypatch):
    from services.template_store import BrandTemplate

    def fake_build_from_upload(self, filename, content):
        return BrandTemplate(
            brand_name="UploadTest Brand",
            core_voice="Clear and practical.",
            mission="Help teams launch with confidence.",
            tone_words=["clear", "practical"],
            forbidden_words=[],
            competitors=[],
            required_cta="See how it works.",
            visual_aesthetic="Modern software brand.",
            linkedin_rules="3 short paragraphs.",
            twitter_rules="Sharp hook under 280 characters.",
            instagram_rules="Visual and spacious with hashtags.",
            enriched_context="Verified context",
        )

    monkeypatch.setattr("services.template_builder.TemplateBuilder.build_from_upload", fake_build_from_upload)

    response = client.post(
        "/onboard-brand",
        files={"file": ("brand.txt", b"Brand voice and best posts", "text/plain")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["brand_name"] == "UploadTest Brand"
    assert payload["stored"] is True
    assert payload["notification"]["type"] == "template_created"

    events_response = client.get("/backend-events")
    assert events_response.status_code == 200
    events = events_response.json()
    assert any(event["brand_name"] == "UploadTest Brand" for event in events)


def test_template_builder_enriches_and_stores_template(monkeypatch):
    builder = TemplateBuilder()
    store = TemplateStore()
    brand_name = "Builder Test Brand"
    responses = iter(
        [
            """
            {
              "brand_name": "Builder Test Brand",
              "core_voice": "Confident and practical.",
              "mission": "Make launch communication easier.",
              "tone_words": ["confident", "practical"],
              "forbidden_words": ["disruptive"],
              "competitors": ["Acme"],
              "required_cta": "Book a demo.",
              "visual_aesthetic": "Crisp SaaS visuals.",
              "linkedin_rules": "3-4 short paragraphs for decision-makers.",
              "twitter_rules": "Hook first, under 280 characters.",
              "instagram_rules": "Visual language, spacing, 10-15 hashtags.",
              "top_performing_posts": ["Example post one", "Example post two"],
              "platform_examples": {
                "linkedin": ["LinkedIn exemplar"],
                "twitter": ["Twitter exemplar"],
                "instagram": ["Instagram exemplar"]
              }
            }
            """,
            """
            {
              "brand_name": "Builder Test Brand",
              "core_voice": "Confident and practical.",
              "mission": "Make launch communication easier for modern SaaS teams.",
              "tone_words": ["confident", "practical"],
              "forbidden_words": ["disruptive"],
              "competitors": ["Acme"],
              "required_cta": "Book a demo.",
              "visual_aesthetic": "Crisp SaaS visuals with product UI.",
              "linkedin_rules": "3-4 short paragraphs for decision-makers.",
              "twitter_rules": "Hook first, under 280 characters.",
              "instagram_rules": "Visual language, spacing, 10-15 hashtags.",
              "top_performing_posts": ["Example post one", "Example post two"],
              "platform_examples": {
                "linkedin": ["LinkedIn exemplar"],
                "twitter": ["Twitter exemplar"],
                "instagram": ["Instagram exemplar"]
              }
            }
            """,
        ]
    )

    monkeypatch.setattr(builder.rag, "_invoke_llm", lambda llm, prompt: next(responses))
    monkeypatch.setattr(
        builder.scraper,
        "gather_brand_context",
        lambda brand: BrandContext(
            snippets=["Builder Test Brand helps marketing teams launch faster."],
            sources=["https://example.com/about"],
            page_summaries=["example.com: Product marketing workflow and launch operations platform."],
        ),
    )

    template = builder.build_from_document(
        """
        Builder Test Brand
        Voice: confident and practical.
        Mission: make launch communication easier.
        Best post: Example post one
        Best post: Example post two
        """
    )

    assert template.brand_name == brand_name
    assert "modern SaaS teams" in template.mission
    assert template.top_performing_posts[:2] == ["Example post one", "Example post two"]
    assert template.platform_examples["linkedin"] == ["LinkedIn exemplar"]
    persisted = store.load_template(brand_name)
    assert persisted is not None
    assert persisted.visual_aesthetic == "Crisp SaaS visuals with product UI."


def test_platform_adapter_enforces_distinct_shapes():
    adapter = PlatformAdapter()
    source = "Launch operations become easier for marketing teams. The workflow is faster and clearer. Stakeholders get aligned quickly."

    linkedin = adapter.adapt_linkedin(source, ["#B2B", "#Marketing", "#AI"], "Book a demo.")
    twitter = adapter.adapt_twitter(source, ["#B2B", "#Launch"], "Book a demo.")
    instagram = adapter.adapt_instagram(source, ["#B2B", "#Marketing", "#AI"], "Book a demo.")

    assert 3 <= len([part for part in linkedin.caption.split("\n\n") if part.strip()]) <= 4
    assert len(twitter.caption) <= 280
    assert 10 <= len(instagram.hashtags) <= 15


def test_build_prompt_includes_brand_examples_and_rules():
    from services.template_store import BrandTemplate

    chain = RAGChain()
    template = BrandTemplate(
        brand_name="Prompt Test",
        core_voice="Professional and grounded.",
        mission="Help teams launch with clarity.",
        tone_words=["professional", "grounded"],
        forbidden_words=["disruptive"],
        competitors=["Acme"],
        required_cta="Learn more.",
        visual_aesthetic="Editorial software visuals.",
        linkedin_rules="3-4 short paragraphs.",
        twitter_rules="Under 280 characters.",
        instagram_rules="Visual, spaced, with 10-15 hashtags.",
        enriched_context="Verified public website context.",
        top_performing_posts=["A strong launch post."],
        platform_examples={"linkedin": ["LinkedIn sample"], "twitter": ["Twitter sample"], "instagram": ["Instagram sample"]},
    )
    feature = FeatureInput(
        feature_name="Prompt Builder",
        description="Turns source material into campaign-ready copy.",
        target_audience="Product marketers",
        tone="professional",
        platforms=["linkedin", "twitter", "instagram"],
        brand_name="Prompt Test",
    )

    prompt = chain.build_prompt(feature, template).prompt

    assert "Top-performing post examples" in prompt
    assert "Linkedin examples" in prompt
    assert "Cross-platform rule" in prompt


def test_generate_and_history_flow():
    response = client.post(
        "/generate",
        json={
            "feature_name": "Launch Brief Importer",
            "description": "Turns release notes into structured launch briefs for marketing teams.",
            "target_audience": "Product marketing managers",
            "tone": "professional",
            "platforms": ["linkedin", "twitter"],
        },
    )
    assert response.status_code == 200
    body = response.text
    assert '"event": "final"' in body
    assert '"feature_name": "Launch Brief Importer"' in body

    history = client.get("/history")
    assert history.status_code == 200
    payload = history.json()
    assert isinstance(payload, list)
    assert any(item["feature_name"] == "Launch Brief Importer" for item in payload)


def test_visual_package_and_notify_flow():
    generate = client.post(
        "/generate",
        json={
            "feature_name": "Team Approval Flow",
            "description": "Adds approval checkpoints and publish readiness indicators to campaign workflows.",
            "target_audience": "Marketing operations managers",
            "tone": "professional",
            "platforms": ["linkedin", "instagram"],
        },
    )
    assert generate.status_code == 200
    body = generate.text
    marker = '"session_id": "'
    start = body.find(marker)
    assert start != -1
    start += len(marker)
    end = body.find('"', start)
    session_id = body[start:end]

    image_response = client.post(
        "/generate-image",
        json={
            "session_id": session_id,
            "prompt": "A branded software campaign visual",
            "platforms": ["linkedin", "instagram"],
        },
    )
    assert image_response.status_code == 200
    image_payload = image_response.json()
    assert "image_paths_by_platform" in image_payload
    assert "carousel_paths" in image_payload

    package_response = client.get(f"/package/{session_id}")
    assert package_response.status_code == 200

    notify_response = client.post(f"/notify/{session_id}")
    assert notify_response.status_code == 200
    assert "ok" in notify_response.json()
