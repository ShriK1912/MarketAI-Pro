from __future__ import annotations

import json
import zipfile
from pathlib import Path

from config import get_settings
from models.schemas import GeneratedCopy, TokenStats, ValidationResult


class PackageBuilder:
    def __init__(self) -> None:
        self.settings = get_settings()

    def build(
        self,
        session_id: str,
        generated_copy: GeneratedCopy,
        asset_paths: dict[str, str],
        validation_result: ValidationResult,
        token_stats: TokenStats,
        extra_assets: dict[str, str] | None = None,
    ) -> str:
        base_dir = Path(self.settings.output_dir) / session_id
        base_dir.mkdir(parents=True, exist_ok=True)
        platforms = {
            "linkedin": generated_copy.linkedin,
            "twitter": generated_copy.twitter,
            "instagram": generated_copy.instagram,
        }
        for name, item in platforms.items():
            if item is None:
                continue
            folder = base_dir / name
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "post.txt").write_text(item.caption, encoding="utf-8")
            (folder / "hashtags.txt").write_text("\n".join(item.hashtags_comment or item.hashtags), encoding="utf-8")
        manifest = {
            "session_id": session_id,
            "feature_name": generated_copy.feature_name,
            "assets": asset_paths,
            "extra_assets": extra_assets or {},
            "validation": validation_result.model_dump(),
            "token_stats": token_stats.model_dump(mode="json"),
        }
        (base_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return self.create_zip(session_id)

    def create_zip(self, session_id: str) -> str:
        base_dir = Path(self.settings.output_dir) / session_id
        zip_path = base_dir / f"{session_id}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in base_dir.rglob("*"):
                if path == zip_path or path.is_dir():
                    continue
                archive.write(path, path.relative_to(base_dir))
        return str(zip_path)
