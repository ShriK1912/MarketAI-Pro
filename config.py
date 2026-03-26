from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    llm_provider: str = "ollama"
    image_provider: str = "local"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "mistral"
    groq_model: str = "llama-3.1-8b-instant"
    groq_api_key: str = ""
    fal_api_key: str = ""
    slack_webhook_url: str = ""
    fastapi_host: str = "0.0.0.0"
    fastapi_port: int = 8000
    streamlit_port: int = 8501
    chroma_dir: str = "./data/chroma"
    sqlite_path: str = "./data/history.db"
    output_dir: str = "./output"
    brand_guidelines_path: str = "./data/brand_guidelines.json"
    seed_posts_path: str = "./data/seed_posts.json"
    mock_trends_path: str = "./data/mock_trends.json"
    mock_events_path: str = "./data/mock_events.json"
    lottie_sdxl_path: str = "./data/lottie/sdxl_loading.json"
    lottie_scraper_path: str = "./data/lottie/scraper_pulse.json"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    def ensure_directories(self) -> None:
        for raw_path in (self.chroma_dir, self.output_dir, Path(self.sqlite_path).parent):
            Path(raw_path).mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
