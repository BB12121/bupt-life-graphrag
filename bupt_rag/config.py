import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)

REPOSITORY = "byrdocs/bupt-survival-guide"
SOURCE_PREFIX = "src/content/docs/"
REFERENCE_COMMIT = "417fc690834fbc4406f48e503f5ef1f832d495db"
EXCLUDED = {"index.mdx", "contributing.md", "acknowledgments.md"}


@dataclass
class Settings:
    frontend_dist: Path = field(
        default_factory=lambda: Path(
            os.getenv(
                "BUPT_FRONTEND_DIST",
                str(Path(__file__).resolve().parents[1] / "bupt-graphrag-frontend" / "dist"),
            )
        )
    )
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("BUPT_DATA_DIR", "data")))
    embedding_model: str = field(
        default_factory=lambda: os.getenv("BUPT_EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
    )
    embedding_revision: str = field(
        default_factory=lambda: os.getenv(
            "BUPT_EMBEDDING_REVISION", "7999e1d3359715c523056ef9478215996d62a620"
        )
    )
    cors_origins: list[str] = field(
        default_factory=lambda: os.getenv(
            "BUPT_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        ).split(",")
    )
    admin_key: str = field(default_factory=lambda: os.getenv("BUPT_ADMIN_KEY", ""))
    llm_base_url: str = field(default_factory=lambda: os.getenv("BUPT_LLM_BASE_URL", ""))
    llm_model: str = field(default_factory=lambda: os.getenv("BUPT_LLM_MODEL", "qwen3.8-27b"))
    llm_api_key: str = field(default_factory=lambda: os.getenv("BUPT_LLM_API_KEY", ""), repr=False)
    max_paths: int = 50
    max_expansions: int = 1000
    context_chars: int = 12000
