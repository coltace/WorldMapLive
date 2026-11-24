import math
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=False)

database_url = os.getenv(
    "DATABASE_URL",
    "sqlite:///worldmap.db"
)

# Normalize Render PostgreSQL URLs for Psycopg 3
if database_url.startswith("postgres://"):
    database_url = database_url.replace(
        "postgres://",
        "postgresql+psycopg://",
        1
    )
elif database_url.startswith("postgresql://"):
    database_url = database_url.replace(
        "postgresql://",
        "postgresql+psycopg://",
        1
    )


def _env_float(name, default):
    try:
        value = float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default
    return max(0.0, value) if math.isfinite(value) else default


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY")

    SQLALCHEMY_DATABASE_URI = database_url

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    MAX_CONTENT_LENGTH = 5 * 1024 * 1024

    UPLOAD_FOLDER = os.getenv(
        "UPLOAD_FOLDER",
        str(BASE_DIR / "instance" / "uploads")
    )

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    SESSION_COOKIE_SECURE = os.getenv(
        "SESSION_COOKIE_SECURE",
        "false"
    ).strip().lower() in {"1", "true", "yes", "on"}

    NOMINATIM_BASE_URL = os.getenv(
        "NOMINATIM_BASE_URL",
        "https://nominatim.openstreetmap.org",
    ).rstrip("/")
    NOMINATIM_MIN_REQUEST_INTERVAL = _env_float(
        "NOMINATIM_MIN_REQUEST_INTERVAL",
        1.1,
    )

    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")

    ASSISTANT_ENABLED = os.getenv("ASSISTANT_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
    ASSISTANT_BASE_URL = os.getenv("ASSISTANT_BASE_URL", "https://api.openai.com/v1")
    ASSISTANT_MODEL = os.getenv("ASSISTANT_MODEL", "")
    ASSISTANT_API_KEY = os.getenv("ASSISTANT_API_KEY", "")
    ASSISTANT_MAX_INPUT_CHARS = 2000
    ASSISTANT_MAX_OUTPUT_TOKENS = 400
    ASSISTANT_MAX_OUTPUT_CHARS = 4000
