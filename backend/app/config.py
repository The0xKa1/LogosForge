from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

# Keep project-local configuration first. The copied file lives here.
load_dotenv(PROJECT_ROOT / "backend" / ".env")

# Optional compatibility fallback for local development if the copied file is
# missing. Existing environment variables are not overwritten.
load_dotenv(Path("/Users/zhangjinkai/textbooks/medical-rag/.env"), override=False)


class Settings:
    llm_base_url: str = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "gpt-4o")
    rag_temperature: float = float(os.getenv("RAG_TEMPERATURE", "0.2"))
    rag_max_tokens: int = int(os.getenv("RAG_MAX_TOKENS", "1200"))
    rag_timeout_seconds: float = float(os.getenv("RAG_TIMEOUT_SECONDS", "45"))
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-zh-v1.5")
    chroma_db_dir: Path = Path(os.getenv("CHROMA_DB_DIR", str(PROJECT_ROOT / "backend" / "chroma_db")))
    external_chroma_db_dir: Path = Path(
        os.getenv("EXTERNAL_CHROMA_DB_DIR", "/Users/zhangjinkai/textbooks/medical-rag/chroma_db")
    )


settings = Settings()
