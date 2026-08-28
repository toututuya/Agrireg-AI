from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env.local", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = Field("127.0.0.1", alias="AGENT_HOST")
    port: int = Field(8091, alias="AGENT_PORT")
    cors_origins: str = Field(
        "http://127.0.0.1:8082,http://localhost:8082",
        alias="AGENT_CORS_ORIGINS",
    )
    graph_api_base_url: str = Field(
        "http://127.0.0.1:4399", alias="AGENT_GRAPH_API_BASE_URL"
    )
    data_dir: Path = Field(Path("./data"), alias="AGENT_DATA_DIR")
    request_timeout_seconds: float = Field(20.0, alias="AGENT_REQUEST_TIMEOUT_SECONDS")
    max_tool_steps: int = Field(6, alias="AGENT_MAX_TOOL_STEPS")

    deepseek_enabled: bool = Field(False, alias="DEEPSEEK_ENABLED")
    deepseek_api_key: str = Field("", alias="DEEPSEEK_API_KEY")
    deepseek_base_url: str = Field("https://api.deepseek.com", alias="DEEPSEEK_BASE_URL")
    deepseek_model: str = Field("deepseek-v4-flash", alias="DEEPSEEK_MODEL")

    @property
    def allowed_origins(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    def prepare(self) -> "Settings":
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings().prepare()

