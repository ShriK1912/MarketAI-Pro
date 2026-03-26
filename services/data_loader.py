from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from config import get_settings


def _load_json(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


@lru_cache
def load_brand_guidelines() -> dict[str, Any]:
    return _load_json(get_settings().brand_guidelines_path)


@lru_cache
def load_mock_trends() -> dict[str, list[str]]:
    return _load_json(get_settings().mock_trends_path)


def load_mock_events() -> list[dict[str, Any]]:
    return _load_json(get_settings().mock_events_path)


def load_seed_posts() -> list[dict[str, Any]]:
    return _load_json(get_settings().seed_posts_path)
