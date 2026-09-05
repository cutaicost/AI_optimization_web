from dataclasses import dataclass
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[3]
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()

@dataclass(frozen=True)
class Settings:
    environment: str
    database_url: str
    session_secret: str
    allowed_origins: tuple[str, ...]
    session_ttl_seconds: int
    cookie_secure: bool

def settings() -> Settings:
    environment = os.getenv("APP_ENV", "development").lower()
    database_url = os.getenv("DATABASE_URL") or f"sqlite:///{(ROOT / 'development.sqlite').as_posix()}"
    secret = os.getenv("SESSION_SECRET", "")
    if environment == "production" and len(secret) < 32:
        raise RuntimeError("SESSION_SECRET must contain at least 32 characters in production")
    origins = tuple(value.strip() for value in os.getenv("ALLOWED_ORIGINS", "http://127.0.0.1:3000").split(",") if value.strip())
    if environment == "production" and (not origins or "*" in origins):
        raise RuntimeError("Production ALLOWED_ORIGINS must be explicit")
    return Settings(environment, database_url, secret, origins, int(os.getenv("SESSION_TTL_SECONDS", "28800")), os.getenv("COOKIE_SECURE", "false").lower() == "true" or environment == "production")
