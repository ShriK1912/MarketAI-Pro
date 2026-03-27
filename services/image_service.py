from __future__ import annotations

import gc
import os
import traceback
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

from config import get_settings
from services.data_loader import load_brand_guidelines

try:
    import torch
except Exception:  # pragma: no cover
    torch = None

try:
    from diffusers import AutoPipelineForText2Image
except Exception:  # pragma: no cover
    AutoPipelineForText2Image = None

try:
    import fal_client
except Exception:  # pragma: no cover
    fal_client = None


class ImageService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.guidelines = load_brand_guidelines()
        Path(self.settings.output_dir).mkdir(parents=True, exist_ok=True)
        self._pipeline = None
        print(f"[ImageService] torch={'available (v' + torch.__version__ + ')' if torch else 'MISSING'}")
        print(f"[ImageService] diffusers={'available' if AutoPipelineForText2Image else 'MISSING'}")
        print(f"[ImageService] fal_client={'available' if fal_client else 'MISSING'}")
        if torch is not None:
            cuda_available = torch.cuda.is_available()
            print(
                f"[ImageService] CUDA="
                f"{'available (' + torch.cuda.get_device_name(0) + ')' if cuda_available else 'not available (CPU mode)'}"
            )
        print(f"[ImageService] image_provider={self.settings.image_provider}")

    def generate_hero(
        self,
        prompt: str,
        session_id: str,
        headline: str = "",
        supporting_text: str = "",
        provider_override: str | None = None,
    ) -> dict[str, str]:
        active_provider = provider_override or self.settings.image_provider
        print(f"[ImageService] generate_hero called | provider={active_provider} | prompt='{prompt[:80]}...'")
        self._sequential_cleanup()
        session_dir = Path(self.settings.output_dir) / session_id / "images"
        session_dir.mkdir(parents=True, exist_ok=True)

        base_image = None
        # Priority: HF (if token) -> Fal -> Local -> Placeholder
        if self.settings.hf_token and active_provider != "local":
            print("[ImageService] Attempting Hugging Face Flux Schnell generation...")
            base_image = self._generate_hf_image(prompt)

        if base_image is None and active_provider != "local":
            print("[ImageService] Attempting fal.ai Flux Schnell generation...")
            base_image = self._generate_fal_image(prompt)

        if base_image is None:
            print("[ImageService] Attempting local SDXL Turbo generation fallback...")
            base_image = self._generate_local_image(prompt)

        if base_image is None:
            print("[ImageService] WARNING: All providers failed - using placeholder")
            base_image = self._create_placeholder_hero(prompt)
        else:
            print(f"[ImageService] Image generated successfully ({base_image.size[0]}x{base_image.size[1]})")

        linkedin_path = session_dir / "hero_linkedin_1200x628.png"
        instagram_path = session_dir / "hero_instagram_1080x1080.png"

        linkedin_base = self.resize_for_platform(base_image, "linkedin")
        linkedin_branded = self.apply_brand_overlay(linkedin_base, headline=headline, supporting_text=supporting_text)
        linkedin_branded.save(linkedin_path, quality=95)

        instagram_base = self.resize_for_platform(base_image, "instagram")
        instagram_branded = self.apply_brand_overlay(instagram_base, headline=headline, supporting_text=supporting_text)
        instagram_branded.save(instagram_path, quality=95)
        print(f"[ImageService] Saved: {linkedin_path} | {instagram_path}")
        return {"linkedin": str(linkedin_path), "instagram": str(instagram_path)}

    def _sequential_cleanup(self) -> None:
        import requests

        try:
            requests.post(
                f"{self.settings.ollama_base_url}/api/generate",
                json={"model": self.settings.ollama_model, "keep_alive": 0},
                timeout=2,
            )
        except Exception as exc:
            print(f"[ImageService] Cleanup warning: Ollama unload request failed: {exc}")

        gc.collect()

        try:
            if torch is not None and torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
        except Exception as exc:
            print(f"[ImageService] Cleanup warning: CUDA cache cleanup failed: {exc}")

    def _enhance_prompt(self, prompt: str) -> tuple[str, str]:
        scene = prompt.strip()
        positive = (
            "cinematic product-launch hero photograph, professional photography, "
            "dramatic studio lighting with teal and purple accent lights, dark moody backdrop, "
            "shallow depth of field, bokeh background, ultra-sharp foreground subject, "
            "clean minimalist composition, premium corporate aesthetic, "
            "photorealistic, 8K detail, "
            f"concept: {scene}"
        )
        # Flux is extremely good at text, so we can be less aggressive with negative prompts
        # but we still want to avoid generic 'UI' screenshots.
        negative = (
            "text, letters, words, typography, font, caption, watermark, label, "
            "user interface, UI, website, web page, browser, browser chrome, navigation, "
            "blurry, out of focus, low quality, low resolution, jpeg artifacts, "
            "stock photo style, cheesy, generic"
        )
        return positive, negative

    def _post_process_image(self, image: Image.Image) -> Image.Image:
        processed = image.convert("RGB")
        # Slight contrast lift for dark-mode marketing aesthetic
        processed = ImageEnhance.Contrast(processed).enhance(1.08)
        # Gentle saturation boost — more pop without neon look
        processed = ImageEnhance.Color(processed).enhance(1.12)
        # Mild unsharp mask for crispness
        processed = processed.filter(ImageFilter.UnsharpMask(radius=1.2, percent=100, threshold=4))
        processed = ImageEnhance.Sharpness(processed).enhance(1.05)
        # Subtle brightness lift (SDXL Turbo sometimes runs slightly dark on CPU)
        processed = ImageEnhance.Brightness(processed).enhance(1.04)
        return processed

    def _generate_local_image(self, prompt: str) -> Image.Image | None:
        if AutoPipelineForText2Image is None:
            print("[ImageService] SKIP local: diffusers not installed")
            return None
        if torch is None:
            print("[ImageService] SKIP local: torch not installed")
            return None

        enhanced_prompt, negative_prompt = self._enhance_prompt(prompt)

        try:
            use_cuda = torch.cuda.is_available()
            dtype = torch.float16 if use_cuda else torch.float32
            device = "cuda" if use_cuda else "cpu"
            print(f"[ImageService] Loading SDXL Turbo | device={device} dtype={dtype} attention_slicing=on")

            pipeline_kwargs: dict[str, Any] = {"torch_dtype": dtype}
            if use_cuda:
                pipeline_kwargs["variant"] = "fp16"

            self._pipeline = AutoPipelineForText2Image.from_pretrained(
                "stabilityai/sdxl-turbo",
                **pipeline_kwargs,
            )
            print("[ImageService] Model loaded successfully")

            if hasattr(self._pipeline, "enable_attention_slicing"):
                self._pipeline.enable_attention_slicing()
            if not use_cuda and hasattr(self._pipeline, "vae") and hasattr(self._pipeline.vae, "enable_slicing"):
                self._pipeline.vae.enable_slicing()

            self._pipeline = self._pipeline.to(device)

            # SDXL Turbo: 4 steps = fastest, 8 steps = better quality (+~2x time)
            # guidance_scale 0.0 = pure turbo speed, 0.5-1.0 = slightly more prompt-adherent
            steps = 8 if not use_cuda else 4   # CPU gets 8 for quality; GPU fast enough for more
            print(f"[ImageService] Running inference (num_steps={steps}, guidance_scale=0.5)...")
            result = self._pipeline(
                prompt=enhanced_prompt,
                negative_prompt=negative_prompt,
                num_inference_steps=steps,
                guidance_scale=0.5,
            )
            image = self._post_process_image(result.images[0])
            return image
        except Exception as exc:
            print(f"[ImageService] ERROR local generation failed: {exc}")
            print(traceback.format_exc())
            return None
        finally:
            self._pipeline = None
            self._sequential_cleanup()

    def _create_placeholder_hero(self, prompt: str) -> Image.Image:
        image = Image.new("RGB", (1080, 1080))
        draw = ImageDraw.Draw(image)
        for y in range(1080):
            r = int(25 + (15 * y / 1080))
            g = int(25 + (25 * y / 1080))
            b = int(35 + (35 * y / 1080))
            draw.line([(0, y), (1080, y)], fill=(r, g, b))

        draw.rectangle((0, 0, 1080, 16), fill=self.guidelines["color_primary"])

        font_title = self._load_font(72)
        font_body = self._load_font(42)

        draw.text((80, 100), "Campaign Visual", fill="white", font=font_title)

        import textwrap

        wrapped = textwrap.wrap(prompt, width=40)
        y_text = 260
        for line in wrapped[:12]:
            draw.text((80, y_text), line, fill="#F0F0F0", font=font_body)
            y_text += 60

        return image

    def _load_font(self, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        font_dir = Path("data/fonts")
        preferred = list(font_dir.glob("*.ttf"))
        if preferred:
            return ImageFont.truetype(str(preferred[0]), size=size)
        return ImageFont.load_default()

    def _wrap_text(self, text: str, width: int) -> list[str]:
        import textwrap

        cleaned = " ".join(text.split())
        return textwrap.wrap(cleaned, width=width)

    def apply_brand_overlay(self, image: Image.Image, headline: str = "", supporting_text: str = "") -> Image.Image:
        branded = image.convert("RGBA")
        overlay = Image.new("RGBA", branded.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        gradient_top = branded.height - 360
        for y in range(gradient_top, branded.height):
            alpha = int(175 * ((y - gradient_top) / max(1, branded.height - gradient_top)))
            draw.line([(0, y), (branded.width, y)], fill=(8, 14, 20, alpha))

        branded = Image.alpha_composite(branded, overlay)
        draw = ImageDraw.Draw(branded)
        kicker_font = self._load_font(24)
        headline_font = self._load_font(52)
        body_font = self._load_font(26)
        cta_font = self._load_font(24)

        kicker = self.guidelines["brand_name"].upper()
        headline_text = headline.strip() or "Launch your next campaign with clarity"
        support_text = supporting_text.strip() or self.guidelines["required_cta"]

        x = 54
        kicker_y = branded.height - 245
        accent = self.guidelines["color_primary"]
        draw.text((x, kicker_y), kicker, fill=accent, font=kicker_font, stroke_width=1, stroke_fill=(0, 0, 0, 75))
        draw.line((x, kicker_y + 34, x + 118, kicker_y + 34), fill=accent, width=3)

        headline_lines = self._wrap_text(headline_text, width=30)[:2]
        y_cursor = kicker_y + 48
        for line in headline_lines:
            draw.text((x, y_cursor), line, fill="white", font=headline_font, stroke_width=2, stroke_fill=(0, 0, 0, 100))
            y_cursor += 58

        support_lines = self._wrap_text(support_text, width=48)[:2]
        y_cursor += 10
        for line in support_lines:
            draw.text((x, y_cursor), line, fill="#E7EDF2", font=body_font, stroke_width=1, stroke_fill=(0, 0, 0, 90))
            y_cursor += 34

        cta_text = self.guidelines["required_cta"]
        draw.text(
            (x, branded.height - 46),
            cta_text,
            fill="#F6F8FA",
            font=cta_font,
            stroke_width=1,
            stroke_fill=(0, 0, 0, 100),
        )
        return branded.convert("RGB")

    def resize_for_platform(self, image: Image.Image, platform: str) -> Image.Image:
        target_size = (1200, 628) if platform == "linkedin" else (1080, 1080)
        fitted = ImageOps.fit(image.convert("RGB"), target_size, method=Image.Resampling.LANCZOS)
        return fitted

    def _generate_fal_image(self, prompt: str) -> Image.Image | None:
        if fal_client is None:
            print("[ImageService] SKIP fal: fal_client not installed")
            return None
        if not self.settings.fal_api_key:
            print("[ImageService] SKIP fal: FAL_API_KEY not configured")
            return None

        enhanced_prompt, _ = self._enhance_prompt(prompt)

        try:
            print("[ImageService] Calling fal.ai flux/schnell API...")
            os.environ["FAL_KEY"] = self.settings.fal_api_key
            # Flux Schnell typically requires 4 steps for optimal speed/quality trade-off
            result = fal_client.subscribe(
                "fal-ai/flux/schnell",
                arguments={
                    "prompt": enhanced_prompt,
                    "image_size": "landscape_4_3",
                    "num_inference_steps": 4,
                    "enable_safety_checker": False
                },
                with_logs=False,
            )
            images = result.get("images") or []
            if not images or not images[0].get("url"):
                print(f"[ImageService] ERROR fal API returned no image URL: {result}")
                return None

            image_url = images[0]["url"]
            print(f"[ImageService] Fal success: {image_url}")
            
            import requests
            from io import BytesIO
            resp = requests.get(image_url, timeout=20)
            resp.raise_for_status()
            return self._post_process_image(Image.open(BytesIO(resp.content)).convert("RGB"))
        except Exception as exc:
            print(f"[ImageService] ERROR fal.ai failed: {exc}")
            return None

    def _generate_hf_image(self, prompt: str) -> Image.Image | None:
        """Generates image using Hugging Face Inference API with Flux Schnell."""
        if not self.settings.hf_token:
            return None

        enhanced_prompt, _ = self._enhance_prompt(prompt)
        import requests
        from io import BytesIO

        # Flux Schnell on HF Inference API
        API_URL = "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell"
        headers = {"Authorization": f"Bearer {self.settings.hf_token}"}

        try:
            print("[ImageService] Calling Hugging Face Inference API (black-forest-labs/FLUX.1-schnell)...")
            response = requests.post(
                API_URL,
                headers=headers,
                json={"inputs": enhanced_prompt, "parameters": {"num_inference_steps": 4}},
                timeout=45
            )
            if response.status_code != 200:
                print(f"[ImageService] HF Error: {response.status_code} {response.text}")
                return None

            return self._post_process_image(Image.open(BytesIO(response.content)).convert("RGB"))
        except Exception as exc:
            print(f"[ImageService] ERROR Hugging Face failed: {exc}")
            return None



    def generate_via_fal(self, prompt: str, session_id: str) -> dict[str, Any]:
        return {
            "provider": "fal",
            "note": "Fal path attempted when configured; local placeholder remains available.",
            "paths": self.generate_hero(prompt, session_id),
        }
