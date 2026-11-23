from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
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
    max_tool_steps: int = Field(6, ge=1, le=6, alias="AGENT_MAX_TOOL_STEPS")
    milvus_uri: str = Field("", alias="AGENT_MILVUS_URI")
    milvus_collection: str = Field("agrireg_documents_v1", alias="AGENT_MILVUS_COLLECTION")
    milvus_token: SecretStr = Field(SecretStr(""), alias="AGENT_MILVUS_TOKEN")
    retrieval_device: str = Field("", alias="AGENT_RETRIEVAL_DEVICE")
    embedding_model: str = Field("BAAI/bge-m3", alias="AGENT_EMBEDDING_MODEL")
    reranker_model: str = Field("BAAI/bge-reranker-v2-m3", alias="AGENT_RERANKER_MODEL")
    planner_backend: Literal["deepseek", "qwen3"] = Field("deepseek", alias="AGENT_PLANNER_BACKEND")
    qwen_base: str = Field("Qwen/Qwen3-1.7B", alias="AGENT_QWEN_BASE")
    qwen_adapter: str = Field("", alias="AGENT_QWEN_ADAPTER")
    qwen_device: str = Field("cuda", alias="AGENT_QWEN_DEVICE")
    qwen_four_bit: bool = Field(False, alias="AGENT_QWEN_4BIT")

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

