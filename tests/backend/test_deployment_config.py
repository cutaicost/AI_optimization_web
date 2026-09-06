import pytest
from apps.api.aiopt_web.config import settings

def production_environment(monkeypatch):
    monkeypatch.setenv("APP_ENV","production");monkeypatch.setenv("SESSION_SECRET","x"*32);monkeypatch.setenv("ALLOWED_ORIGINS","https://cutaicost.com")

def test_production_requires_database_url(monkeypatch):
    production_environment(monkeypatch);monkeypatch.delenv("DATABASE_URL",raising=False)
    with pytest.raises(RuntimeError,match="DATABASE_URL is required"):settings()

def test_production_rejects_sqlite(monkeypatch):
    production_environment(monkeypatch);monkeypatch.setenv("DATABASE_URL","sqlite:///development.sqlite")
    with pytest.raises(RuntimeError,match="must use PostgreSQL"):settings()

def test_production_accepts_psycopg_url_and_forces_secure_cookies(monkeypatch):
    production_environment(monkeypatch);monkeypatch.setenv("DATABASE_URL","postgresql+psycopg://user:password@db/app");monkeypatch.setenv("COOKIE_SECURE","false")
    configured=settings();assert configured.database_url.startswith("postgresql+psycopg://");assert configured.cookie_secure is True
