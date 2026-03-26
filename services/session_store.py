from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from models.schemas import GenerateResponse


@dataclass
class SessionArtifacts:
    response: GenerateResponse
    image_paths: dict[str, str] = field(default_factory=dict)
    carousel_paths: list[str] = field(default_factory=list)
    gif_path: str | None = None
    mp4_path: str | None = None
    zip_path: str | None = None


class SessionStore:
    def __init__(self) -> None:
        self._store: dict[str, SessionArtifacts] = {}

    def save_response(self, response: GenerateResponse) -> None:
        self._store[response.session_id] = SessionArtifacts(response=response)

    def get(self, session_id: str) -> SessionArtifacts | None:
        return self._store.get(session_id)

    def update_assets(self, session_id: str, **kwargs: Any) -> SessionArtifacts | None:
        item = self._store.get(session_id)
        if item is None:
            return None
        for key, value in kwargs.items():
            setattr(item, key, value)
        return item
