from __future__ import annotations

import sqlite3
from typing import Any

from pydantic import BaseModel, Field

from config import get_settings

class BrandTemplate(BaseModel):
    brand_name: str
    core_voice: str
    mission: str = ""
    tone_words: list[str]
    forbidden_words: list[str]
    competitors: list[str]
    required_cta: str
    visual_aesthetic: str
    linkedin_rules: str
    twitter_rules: str
    instagram_rules: str
    enriched_context: str = ""
    top_performing_posts: list[str] = Field(default_factory=list)
    platform_examples: dict[str, list[str]] = Field(default_factory=dict)
    onboarding_summary: dict[str, Any] = Field(default_factory=dict)

class TemplateStore:
    def __init__(self):
        self.settings = get_settings()
        self.conn = sqlite3.connect(self.settings.sqlite_path, check_same_thread=False)
        self._init_db()

    def _init_db(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS brand_templates (
                brand_name TEXT PRIMARY KEY,
                payload TEXT
            )
        """)
        self.conn.commit()

    def save_template(self, template: BrandTemplate):
        self.conn.execute(
            "INSERT OR REPLACE INTO brand_templates (brand_name, payload) VALUES (?, ?)",
            (template.brand_name.strip(), template.model_dump_json())
        )
        self.conn.commit()

    def load_template(self, brand_name: str) -> BrandTemplate | None:
        cursor = self.conn.execute("SELECT payload FROM brand_templates WHERE brand_name = ?", (brand_name.strip(),))
        row = cursor.fetchone()
        if row:
            return BrandTemplate.model_validate_json(row[0])
        return None

    def list_brands(self) -> list[str]:
        cursor = self.conn.execute("SELECT brand_name FROM brand_templates ORDER BY brand_name ASC")
        return [row[0] for row in cursor.fetchall()]
