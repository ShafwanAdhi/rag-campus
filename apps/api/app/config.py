from dataclasses import dataclass
import os
from pathlib import Path
from typing import Optional


BACKEND_DIR = Path(__file__).resolve().parents[1]


def load_dotenv(path: Path = BACKEND_DIR / ".env") -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and key not in os.environ:
            os.environ[key] = value


def env_str(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


def env_int(key: str, default: int) -> int:
    try:
        return int(env_str(key, str(default)))
    except ValueError:
        return default


def env_float(key: str, default: float) -> float:
    try:
        return float(env_str(key, str(default)))
    except ValueError:
        return default


def env_bool(key: str, default: bool) -> bool:
    value = env_str(key, str(default)).lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return default


def resolve_backend_path(value: str, default: Path) -> Path:
    if not value:
        return default

    path = Path(value)
    if path.is_absolute():
        return path

    return BACKEND_DIR / path


def is_local_origin(origin: str) -> bool:
    normalized = origin.lower()
    return "localhost" in normalized or "127.0.0.1" in normalized


@dataclass(frozen=True)
class Settings:
    backend_dir: Path
    app_env: str
    groq_api_key: str
    groq_base_url: str
    groq_router_model: str
    groq_router_fallback_model: str
    groq_analyzer_model: str
    groq_analyzer_fallback_model: str
    groq_answer_model: str
    groq_answer_fallback_model: str
    groq_timeout_seconds: int
    groq_max_retries: int
    embedding_provider: str
    embedding_model: str
    embedding_timeout_seconds: int
    embedding_batch_size: int
    embedding_min_request_interval_seconds: float
    embedding_max_retries: int
    voyage_api_key: str
    voyage_base_url: str
    ollama_embedding_model: str
    ollama_embedding_timeout_seconds: int
    tesseract_cmd: str
    chroma_dir: Path
    structured_facts_path: Path
    frontend_origins: tuple[str, ...]
    cors_allow_origin_regex: Optional[str]
    structured_cache_enabled: bool
    structured_cache_max_entries: int


def build_settings() -> Settings:
    load_dotenv()
    app_env = env_str("APP_ENV", "development").lower() or "development"

    configured_frontend_origins = tuple(
        origin.strip()
        for origin in env_str("FRONTEND_ORIGINS", "").split(",")
        if origin.strip()
    )
    default_dev_origins = (
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    )
    if app_env == "production":
        frontend_origins = tuple(
            origin
            for origin in configured_frontend_origins
            if origin != "*" and not is_local_origin(origin)
        )
        cors_allow_origin_regex = None
    else:
        frontend_origins = tuple(
            dict.fromkeys((*configured_frontend_origins, *default_dev_origins))
        )
        cors_allow_origin_regex = r"https?://(localhost|127\.0\.0\.1)(:\d+)?"

    return Settings(
        backend_dir=BACKEND_DIR,
        app_env=app_env,
        groq_api_key=env_str("GROQ_API_KEY"),
        groq_base_url=env_str(
            "GROQ_BASE_URL",
            "https://api.groq.com/openai/v1",
        ).rstrip("/"),
        groq_router_model=env_str("GROQ_ROUTER_MODEL", "groq/compound-mini"),
        groq_router_fallback_model=env_str(
            "GROQ_ROUTER_FALLBACK_MODEL",
            "openai/gpt-oss-20b",
        ),
        groq_analyzer_model=env_str("GROQ_ANALYZER_MODEL", "groq/compound-mini"),
        groq_analyzer_fallback_model=env_str(
            "GROQ_ANALYZER_FALLBACK_MODEL",
            "qwen/qwen3.8-27b",
        ),
        groq_answer_model=env_str("GROQ_ANSWER_MODEL", "groq/compound"),
        groq_answer_fallback_model=env_str(
            "GROQ_ANSWER_FALLBACK_MODEL",
            "groq/compound-mini",
        ),
        groq_timeout_seconds=env_int("GROQ_TIMEOUT_SECONDS", 60),
        groq_max_retries=env_int("GROQ_MAX_RETRIES", 2),
        embedding_provider=env_str("EMBEDDING_PROVIDER", "voyage"),
        embedding_model=env_str("EMBEDDING_MODEL", "voyage-multilingual-2"),
        embedding_timeout_seconds=env_int("EMBEDDING_TIMEOUT_SECONDS", 60),
        embedding_batch_size=env_int("EMBEDDING_BATCH_SIZE", 8),
        embedding_min_request_interval_seconds=env_float(
            "EMBEDDING_MIN_REQUEST_INTERVAL_SECONDS",
            21.0,
        ),
        embedding_max_retries=env_int("EMBEDDING_MAX_RETRIES", 5),
        voyage_api_key=env_str("VOYAGE_API_KEY"),
        voyage_base_url=env_str(
            "VOYAGE_BASE_URL",
            "https://api.voyageai.com/v1",
        ).rstrip("/"),
        ollama_embedding_model=env_str("OLLAMA_EMBEDDING_MODEL", "bge-m3"),
        ollama_embedding_timeout_seconds=env_int(
            "OLLAMA_EMBEDDING_TIMEOUT_SECONDS",
            60,
        ),
        tesseract_cmd=env_str("TESSERACT_CMD"),
        chroma_dir=resolve_backend_path(
            env_str("CHROMA_DIR", "../../data/chroma"),
            BACKEND_DIR.parent.parent / "data" / "chroma",
        ),
        structured_facts_path=resolve_backend_path(
            env_str("STRUCTURED_FACTS_PATH", "../../data/structured_facts.json"),
            BACKEND_DIR.parent.parent / "data" / "structured_facts.json",
        ),
        frontend_origins=frontend_origins,
        cors_allow_origin_regex=cors_allow_origin_regex,
        structured_cache_enabled=env_bool("STRUCTURED_CACHE_ENABLED", True),
        structured_cache_max_entries=env_int("STRUCTURED_CACHE_MAX_ENTRIES", 256),
    )


settings = build_settings()
