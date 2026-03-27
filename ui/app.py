from __future__ import annotations

import json
from pathlib import Path

import requests
import streamlit as st
from streamlit_lottie import st_lottie

from config import get_settings
from services.data_loader import load_brand_guidelines

settings = get_settings()
FASTAPI_URL = f"http://localhost:{settings.fastapi_port}"

GLOBAL_CSS = """
<style>
div.stButton > button {
    transition: transform 0.15s ease, box-shadow 0.15s ease;
}
div.stButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.18);
}
@keyframes brand-verified-pulse {
    0%   { box-shadow: 0 0 0px 2px rgba(29, 158, 117, 0.0); }
    50%  { box-shadow: 0 0 14px 4px rgba(29, 158, 117, 0.55); }
    100% { box-shadow: 0 0 0px 2px rgba(29, 158, 117, 0.0); }
}
.brand-verified {
    animation: brand-verified-pulse 2.4s ease-in-out infinite;
    border-radius: 8px;
}
.scraper-active-label {
    font-size: 12px;
    color: #0F6E56;
    font-weight: 500;
}
</style>
"""


def load_lottie(filepath: str) -> dict:
    path = Path(filepath)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def init_session_state() -> None:
    defaults = {
        "form_feature_name": "Dark Mode Analytics",
        "form_description": "A new dashboard feature that helps teams compare engagement across dark and light mode experiences.",
        "form_audience": "Product marketers and growth teams",
        "form_tone": "professional",
        "form_platforms": ["linkedin", "twitter", "instagram"],
        "generated_copy": None,
        "brand_score": None,
        "validation_result": None,
        "token_stats": None,
        "session_id": None,
        "image_paths": {},
        "sdxl_image_paths": None,
        "visuals_started": False,
        "carousel_paths": [],
        "gif_path": None,
        "mp4_path": None,
        "zip_path": None,
        "zip_bytes": None,
        "brand_notice": None,
        "brand_notice_kind": "success",
        "generate_error": None,
        "onboarding_summary": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def call_generate(payload: dict) -> tuple[dict | None, str | None]:
    try:
        response = requests.post(f"{FASTAPI_URL}/generate-sync", json=payload, timeout=600)
        response.raise_for_status()
        return response.json(), None
    except requests.exceptions.Timeout:
        return None, "Generation timed out after 600 seconds. The local LLM might be taking longer than 10 minutes."
    except requests.exceptions.HTTPError as exc:
        try:
            detail = exc.response.json()
        except Exception:
            detail = exc.response.text if exc.response is not None else str(exc)
        return None, f"Backend error: {detail}"
    except Exception as exc:
        return None, f"Request failed: {exc}"


st.set_page_config(layout="wide", page_title="MarketAI", page_icon="M")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
init_session_state()
brand = load_brand_guidelines()
lottie_sdxl = load_lottie(settings.lottie_sdxl_path)
lottie_scraper = load_lottie(settings.lottie_scraper_path)

st.title(brand["brand_name"])
tab1, tab2, tab3 = st.tabs(["Generate", "Visuals", "History"])

with st.sidebar:
    st.markdown("---")
    st.markdown('<p class="scraper-active-label">Scraper monitoring active</p>', unsafe_allow_html=True)
    st_lottie(lottie_scraper, height=55, width=55, key="scraper_sidebar_pulse", loop=True, quality="low")
    
    with st.expander("🧠 Brand Knowledge Base", expanded=True):
        try:
            brand_list = requests.get(f"{FASTAPI_URL}/list-brands", timeout=5).json()
        except Exception:
            brand_list = []
        
        st.session_state["selected_brand"] = st.selectbox("Active Brand Profile", ["Mock Brand"] + brand_list)
        
        uploaded_file = st.file_uploader("Onboard via Document (.txt, .md, .pdf, .docx)", type=["txt", "md", "pdf", "docx"])
        if uploaded_file and st.button("Parse & Scrape"):
            with st.spinner("Extracting guidelines & scraping web..."):
                try:
                    response = requests.post(
                        f"{FASTAPI_URL}/onboard-brand",
                        files={"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type or "application/octet-stream")},
                        timeout=30,
                    )
                    response.raise_for_status()
                    resp = response.json()
                    st.session_state["brand_notice"] = f"Template Created: {resp['brand_name']}"
                    st.session_state["brand_notice_kind"] = "success"
                    st.session_state["onboarding_summary"] = resp.get("onboarding_summary")
                    st.rerun()
                except requests.exceptions.Timeout:
                    st.session_state["brand_notice"] = "Brand onboarding timed out. The backend is taking too long to parse or enrich the document."
                    st.session_state["brand_notice_kind"] = "error"
                except Exception as exc:
                    st.session_state["brand_notice"] = f"Brand onboarding failed: {exc}"
                    st.session_state["brand_notice_kind"] = "error"

        if st.session_state.get("brand_notice"):
            if st.session_state.get("brand_notice_kind") == "error":
                st.error(st.session_state["brand_notice"])
            else:
                st.success(st.session_state["brand_notice"])

        summary = st.session_state.get("onboarding_summary")
        if summary:
            with st.expander("Parsed + Search Summary", expanded=True):
                st.caption("Use this to confirm document parsing and DuckDuckGo enrichment are working.")
                search_status = summary.get("search_status", "not_attempted")
                rate_limited = summary.get("rate_limited", False)
                if rate_limited:
                    st.warning(f"Search status: {search_status} (DuckDuckGo rate-limited this request)")
                elif search_status != "success":
                    st.info(f"Search status: {search_status}")
                else:
                    st.success("Search status: success")
                parsed_fields = summary.get("parsed_fields") or {}
                if parsed_fields:
                    st.write("Parsed fields")
                    st.json(parsed_fields)
                if summary.get("extracted_preview"):
                    st.write("Extracted text preview")
                    st.code(summary["extracted_preview"], language="text")
                if summary.get("search_queries"):
                    st.write("DuckDuckGo queries")
                    st.code("\n".join(summary["search_queries"]), language="text")
                if summary.get("search_errors"):
                    st.write("Search errors")
                    for error in summary["search_errors"]:
                        st.caption(error)
                if summary.get("snippets"):
                    st.write("Search snippets")
                    for snippet in summary["snippets"]:
                        st.caption(snippet)
                if summary.get("social_post_highlights"):
                    st.write("Social post signals")
                    st.json(summary["social_post_highlights"])
                if summary.get("sources"):
                    st.write("Sources")
                    for source in summary["sources"]:
                        st.markdown(f"- {source}")
                if summary.get("page_summaries"):
                    st.write("Fetched page excerpts")
                    for excerpt in summary["page_summaries"]:
                        st.caption(excerpt)

    st.markdown("---")
    if st.button("New event detected", key="mock_scraper_btn"):
        event = requests.get(f"{FASTAPI_URL}/mock-events", timeout=30).json()
        st.session_state["form_feature_name"] = event["feature_name"]
        st.session_state["form_description"] = event["description"]
        st.session_state["form_audience"] = event["target_audience"]
        st.rerun()

with tab1:
    left_col, right_col = st.columns([1, 1.4])

    with left_col:
        st.subheader("Campaign Input")
        feature_name = st.text_input("Feature name", value=st.session_state["form_feature_name"])
        description = st.text_area("Description", value=st.session_state["form_description"], max_chars=500)
        st.caption(f"{len(description)}/500")
        audience = st.text_input("Audience", value=st.session_state["form_audience"])
        tone = st.selectbox("Tone", ["professional", "bold", "playful", "analytical"], index=0)
        platforms = st.multiselect(
            "Platforms",
            options=["linkedin", "twitter", "instagram"],
            default=st.session_state["form_platforms"],
        )

        if st.button("Generate", disabled=not feature_name or not description):
            st.session_state["generate_error"] = None
            payload = {
                "feature_name": feature_name,
                "description": description,
                "target_audience": audience,
                "tone": tone,
                "platforms": platforms,
                "brand_name": st.session_state.get("selected_brand", "Mock Brand")
            }
            with st.status("Generating content package...", expanded=True) as status:
                st.write("Sanitizing input...")
                st.write("Retrieving brand memory...")
                st.write("Loading trend context...")
                st.write("Prompting Mistral-7B...")
                data, error = call_generate(payload)
                st.write("Running platform adapter...")
                st.write("Scoring brand alignment...")
                if data:
                    status.update(label="Content package ready!", state="complete", expanded=False)
                else:
                    status.update(label="Content generation failed", state="error", expanded=True)
            if data:
                st.session_state["generated_copy"] = data["copy"]
                st.session_state["brand_score"] = data["brand_score"]
                st.session_state["validation_result"] = data["validation"]
                st.session_state["token_stats"] = data["token_stats"]
                st.session_state["session_id"] = data["session_id"]
                st.rerun()
            else:
                st.session_state["generate_error"] = error or "No content was returned from the backend."

        if st.session_state.get("generate_error"):
            st.error(st.session_state["generate_error"])

    with right_col:
        st.subheader("Generated Output")
        copy = st.session_state["generated_copy"]
        if copy:
            score = st.session_state["brand_score"] or 0
            if score >= 80:
                st.markdown('<div class="brand-verified">', unsafe_allow_html=True)
                st.metric("Brand Alignment Score", f"{score}/100")
                st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.metric("Brand Alignment Score", f"{score}/100")
            st.progress(min(max(score / 100, 0.0), 1.0))
            platform_tabs = st.tabs(["LinkedIn", "X / Twitter", "Instagram"])
            mapping = [("linkedin", platform_tabs[0]), ("twitter", platform_tabs[1]), ("instagram", platform_tabs[2])]
            for key, tab in mapping:
                with tab:
                    item = copy.get(key)
                    if item:
                        new_cap = st.text_area("Edit text before packaging", value=item["caption"], height=150, key=f"edit_{key}")
                        if new_cap != item["caption"]:
                            st.session_state["generated_copy"][key]["caption"] = new_cap
                            # Remove zip bytes so they have to rebuild the package with new text
                            st.session_state["zip_bytes"] = None
                        st.caption(" ".join(item.get("hashtags", [])))
                        if item.get("hashtags_comment"):
                            st.code("\n".join(item["hashtags_comment"]), language="text")
            with st.expander("Generation stats"):
                st.json(st.session_state["token_stats"])
            with st.expander("Validation"):
                st.json(st.session_state["validation_result"])
        else:
            st.info("Generate content to see results here.")

with tab2:
    st.subheader("Visuals")
    if st.session_state["generated_copy"] and st.session_state["session_id"]:
        if st.button("Generate visuals"):
            st.session_state["visuals_started"] = True
            st.session_state["sdxl_image_paths"] = None
            st.session_state["image_paths"] = {}
            st.rerun()

        if st.session_state.get("visuals_started"):
            if not st.session_state.get("sdxl_image_paths"):
                image_placeholder = st.empty()
                with image_placeholder.container():
                    lottie_col, text_col = st.columns([1, 2])
                    with lottie_col:
                        st_lottie(lottie_sdxl, height=180, width=180, key="sdxl_loading_anim", loop=True, quality="medium")
                    with text_col:
                        st.markdown("### 💻 Generating Local SDXL Alternatives...")
                        st.caption("Running a second pass completely offline as a fallback.")
                        st.caption("Estimated: 3-5 minutes on CPU")

                img_response = requests.post(
                    f"{FASTAPI_URL}/generate-image",
                    json={
                        "session_id": st.session_state["session_id"],
                        "prompt": st.session_state["generated_copy"]["image_prompt"],
                        "platforms": ["linkedin", "instagram"],
                        "provider": "local",
                    },
                    timeout=600,
                )
                image_placeholder.empty()
                if img_response.status_code == 200:
                    payload = img_response.json()
                    st.session_state["sdxl_image_paths"] = payload["image_paths_by_platform"]
                    st.toast("Offline SDXL generation complete!", icon="✅")
                st.rerun()

            if st.session_state.get("sdxl_image_paths"):
                st.markdown("---")
                st.markdown("### Local SDXL Turbo")
                for platform, path in st.session_state["sdxl_image_paths"].items():
                    st.write(platform.title())
                    st.image(path)

            if st.session_state.get("carousel_paths"):
                st.markdown("---")
                st.write("Carousel")
                cols = st.columns(min(5, len(st.session_state["carousel_paths"])))
                for col, path in zip(cols, st.session_state["carousel_paths"]):
                    with col:
                        st.image(path)
                        
            if st.session_state.get("gif_path"):
                st.write("Animated GIF Preview")
                st.image(st.session_state["gif_path"])
                
            if st.session_state.get("mp4_path") and Path(st.session_state["mp4_path"]).stat().st_size > 100:
                st.write("Video Preview")
                st.video(st.session_state["mp4_path"])

            if st.button("Build package"):
                package_response = requests.get(f"{FASTAPI_URL}/package/{st.session_state['session_id']}", timeout=120)
                if package_response.status_code == 200:
                    st.session_state["zip_bytes"] = package_response.content
                    st.toast("Package ready!", icon="✅")
                    st.rerun()

            if st.session_state.get("zip_bytes"):
                st.download_button(
                    label="📥 Download Package (.zip)",
                    data=st.session_state["zip_bytes"],
                    file_name=f"marketai_campaign_{st.session_state['session_id'][:8]}.zip",
                    mime="application/zip",
                )
            if st.button("Send Slack notification"):
                notify_response = requests.post(f"{FASTAPI_URL}/notify/{st.session_state['session_id']}", timeout=60)
                if notify_response.status_code == 200 and notify_response.json().get("ok"):
                    st.toast("Content package sent to Slack!", icon="🚀")
                else:
                    st.toast("Slack notification failed or is not configured.", icon="⚠️")
    else:
        st.info("Generate copy first, then create visuals.")

with tab3:
    st.subheader("History")
    try:
        history = requests.get(f"{FASTAPI_URL}/history", timeout=30).json()
        st.json(history)
    except Exception:
        st.info("Backend history is unavailable right now. Start FastAPI to load this tab.")
