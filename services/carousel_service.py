from __future__ import annotations

from pathlib import Path

import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

from config import get_settings
from models.schemas import CarouselSlide
from services.data_loader import load_brand_guidelines


class CarouselService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.guidelines = load_brand_guidelines()

    def _load_font(self, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        font_dir = Path("data/fonts")
        preferred = list(font_dir.glob("*.ttf"))
        if preferred:
            return ImageFont.truetype(str(preferred[0]), size=size)
        return ImageFont.load_default()

    def _fit_image(self, image: Image.Image, size: tuple[int, int]) -> Image.Image:
        return ImageOps.fit(image.convert("RGB"), size, method=Image.Resampling.LANCZOS)

    def _load_hero_image(self, hero_image_path: str | None) -> Image.Image | None:
        if not hero_image_path:
            return None
        path = Path(hero_image_path)
        if not path.exists():
            return None
        try:
            return Image.open(path).convert("RGB")
        except Exception:
            return None

    def render_slides(self, session_id: str, slides: list[CarouselSlide], hero_image_path: str | None = None) -> list[str]:
        session_dir = Path(self.settings.output_dir) / session_id / "carousel"
        session_dir.mkdir(parents=True, exist_ok=True)
        hero_image = self._load_hero_image(hero_image_path)
        title_font = self._load_font(70)
        body_font = self._load_font(34)
        kicker_font = self._load_font(26)
        footer_font = self._load_font(24)
        paths: list[str] = []

        import textwrap

        for index, slide in enumerate(slides[:5], start=1):
            if hero_image is not None:
                background = self._fit_image(hero_image, (1080, 1080)).filter(ImageFilter.GaussianBlur(radius=8))
                background = ImageEnhance.Brightness(background).enhance(0.45)
            else:
                background = Image.new("RGB", (1080, 1080), color="#15202B")

            image = background.convert("RGBA")
            overlay = Image.new("RGBA", image.size, (7, 16, 24, 120))
            image = Image.alpha_composite(image, overlay)
            draw = ImageDraw.Draw(image)

            draw.rounded_rectangle((58, 58, 1022, 1022), radius=42, outline=(255, 255, 255, 75), width=2)
            draw.rounded_rectangle((90, 92, 990, 988), radius=36, fill=(255, 255, 255, 224))

            if hero_image is not None:
                hero_panel = self._fit_image(hero_image, (820, 340))
                hero_panel = ImageEnhance.Sharpness(hero_panel).enhance(1.15)
                image.paste(hero_panel, (130, 140))
                draw.rounded_rectangle((130, 140, 950, 480), radius=28, outline=(255, 255, 255, 180), width=3)

            accent = self.guidelines["color_primary"]
            draw.rounded_rectangle((130, 518, 352, 560), radius=20, fill=accent)
            draw.text((152, 528), f"Campaign Story  {index}/5", fill="white", font=kicker_font)

            title_lines = textwrap.wrap(slide.title.strip() or f"Slide {index}", width=24)[:2]
            body_lines = textwrap.wrap(slide.body.strip(), width=38)[:7]
            y_cursor = 600
            for line in title_lines:
                draw.text((130, y_cursor), line, fill="#09141D", font=title_font)
                y_cursor += 74

            y_cursor += 10
            for line in body_lines:
                draw.text((130, y_cursor), line, fill="#24323E", font=body_font)
                y_cursor += 48

            draw.rounded_rectangle((130, 904, 950, 966), radius=24, fill=(9, 20, 29, 235))
            draw.text((158, 922), self.guidelines["required_cta"], fill="white", font=footer_font)
            draw.text((770, 922), self.guidelines["brand_name"], fill="#C9D3DB", font=footer_font)

            slide_path = session_dir / f"slide_{index:02d}.png"
            image.convert("RGB").save(slide_path, quality=95)
            paths.append(str(slide_path))
        return paths

    def _build_gif_frames(self, slide_paths: list[str]) -> list[np.ndarray]:
        frames: list[np.ndarray] = []
        if not slide_paths:
            return frames

        slides = [Image.open(path).convert("RGB") for path in slide_paths]
        for idx, slide in enumerate(slides):
            current = self._fit_image(slide, (1080, 1080))
            next_slide = self._fit_image(slides[(idx + 1) % len(slides)], (1080, 1080))

            for step in range(12):
                progress = step / 11 if 11 else 0
                zoom = 1.0 + (0.035 * progress)
                scaled = current.resize((int(1080 * zoom), int(1080 * zoom)), Image.Resampling.LANCZOS)
                framed = ImageOps.fit(scaled, (1080, 1080), method=Image.Resampling.LANCZOS)
                blended = Image.blend(framed, next_slide, 0.0 if step < 8 else (step - 7) / 4)
                frames.append(np.array(blended))
        return frames

    def generate_gif(self, session_id: str, slide_paths: list[str]) -> str:
        output_path = Path(self.settings.output_dir) / session_id / "carousel" / "carousel.gif"
        frames = self._build_gif_frames(slide_paths)
        if frames:
            imageio.mimsave(output_path, frames, duration=0.12, loop=0)
        return str(output_path)

    def generate_mp4(self, session_id: str, slide_paths: list[str]) -> str:
        output_path = Path(self.settings.output_dir) / session_id / "carousel" / "launch_video.mp4"
        frames = self._build_gif_frames(slide_paths)
        if not frames:
            return ""

        try:
            with imageio.get_writer(output_path, format="FFMPEG", fps=12, macro_block_size=1) as writer:
                for frame in frames:
                    writer.append_data(frame)
            return str(output_path)
        except Exception as exc:
            print(f"[CarouselService] WARNING: MP4 generation failed: {exc}")
            if output_path.exists():
                output_path.unlink(missing_ok=True)
            return ""
