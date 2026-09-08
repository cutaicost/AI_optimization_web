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
    oidc_issuer: str
    oidc_client_id: str
    oidc_client_secret: str
    oidc_redirect_uri: str
    oidc_role_claim: str
    oidc_role_map: dict[str,str]
    model_refresh_enabled: bool
    model_refresh_hour: int

def settings() -> Settings:
    environment = os.getenv("APP_ENV", "development").lower()
    raw_database_url = os.environ.get("DATABASE_URL")
    database_url = raw_database_url or f"sqlite:///{(ROOT / 'development.sqlite').as_posix()}"
    if environment == "production" and not raw_database_url:
        raise RuntimeError("DATABASE_URL is required in production")
    if environment == "production" and not database_url.startswith(("postgres://", "postgresql://", "postgresql+psycopg://")):
        raise RuntimeError("Production DATABASE_URL must use PostgreSQL")
    secret = os.getenv("SESSION_SECRET", "")
    if environment == "production" and len(secret) < 32:
        raise RuntimeError("SESSION_SECRET must contain at least 32 characters in production")
    origins = tuple(value.strip() for value in os.getenv("ALLOWED_ORIGINS", "http://127.0.0.1:3000").split(",") if value.strip())
    if environment == "production" and (not origins or "*" in origins):
        raise RuntimeError("Production ALLOWED_ORIGINS must be explicit")
    role_map={}
    for pair in os.getenv("OIDC_ROLE_MAP","viewer=VIEWER,analyst=ANALYST,administrator=ADMIN").split(","):
        if "=" in pair:key,value=pair.split("=",1);role_map[key.strip()]=value.strip().upper()
    refresh_hour=int(os.getenv("MODEL_REFRESH_HOUR","6"))
    if not 0<=refresh_hour<=23:raise RuntimeError("MODEL_REFRESH_HOUR must be between 0 and 23")
    return Settings(environment, database_url, secret, origins, int(os.getenv("SESSION_TTL_SECONDS", "28800")), os.getenv("COOKIE_SECURE", "false").lower() == "true" or environment == "production",os.getenv("OIDC_ISSUER","").rstrip("/"),os.getenv("OIDC_CLIENT_ID",""),os.getenv("OIDC_CLIENT_SECRET",""),os.getenv("OIDC_REDIRECT_URI","http://127.0.0.1:8000/api/v1/auth/oidc/callback"),os.getenv("OIDC_ROLE_CLAIM","roles"),role_map,os.getenv("MODEL_REFRESH_ENABLED","true").lower()=="true",refresh_hour)
