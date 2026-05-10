from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

# Keep project-local configuration first. The copied file lives here.
load_dotenv(PROJECT_ROOT / "backend" / ".env")


class Settings:
    llm_base_url: str = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "gpt-4o")
    rag_temperature: float = float(os.getenv("RAG_TEMPERATURE", "0.2"))
    rag_max_tokens: int = int(os.getenv("RAG_MAX_TOKENS", "2000"))
    rag_timeout_seconds: float = float(os.getenv("RAG_TIMEOUT_SECONDS", "45"))
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-zh-v1.5")
    chroma_db_dir: Path = Path(os.getenv("CHROMA_DB_DIR", str(PROJECT_ROOT / "backend" / "chroma_db")))
    external_chroma_db_dir: Path | None = Path(os.getenv("EXTERNAL_CHROMA_DB_DIR", "")) if os.getenv("EXTERNAL_CHROMA_DB_DIR") else None
    # Production: set these to /data/xxx when running in Docker
    data_dir: Path = Path(os.getenv("DATA_DIR", str(PROJECT_ROOT / "backend")))
    upload_dir: Path = Path(os.getenv("UPLOAD_DIR", str(PROJECT_ROOT / "uploads")))


settings = Settings()
