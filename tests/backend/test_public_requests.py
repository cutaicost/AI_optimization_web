import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from apps.api.aiopt_web.auth import CSRF_COOKIE
from apps.api.aiopt_web.database import Base, SessionLocal, engine
from apps.api.aiopt_web.main import app
from apps.api.aiopt_web.models import AuditEvent, User


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def client():
    with TestClient(app) as value:
        yield value


def demo_payload():
    return {"request_type": "DEMO", "name": "Demo Buyer", "email": "BUYER@example.com", "company": "Example Co", "company_size": "51–200", "role": "FinOps Lead", "ai_spend_range": "$10,000–$50,000", "preferred_contact": "Video call", "providers": "OpenAI, Anthropic", "goals": "Reduce model spend without lowering quality.", "message": "Tuesday afternoons work best."}


def test_demo_request_is_persisted_without_creating_an_account(client):
    response = client.post("/api/v1/public/requests", json=demo_payload())
    assert response.status_code == 202
    with SessionLocal() as db:
        row = db.scalar(select(AuditEvent).where(AuditEvent.action == "public.demo_requested"))
        assert row.metadata_json["email"] == "buyer@example.com"
        assert row.metadata_json["company_size"] == "51–200"
        assert row.metadata_json["message"] == "Tuesday afternoons work best."
        assert db.scalar(select(func.count()).select_from(User)) == 2


def test_demo_admin_api_requires_platform_admin_and_supports_completed(client):
    ticket_number = client.post("/api/v1/public/requests", json=demo_payload()).json()["ticket_number"]
    assert client.get("/api/v1/platform/request-tickets").status_code == 401
    with SessionLocal() as db:
        admin = db.scalar(select(User).where(User.username == "Sith"))
        admin.must_change_password = False
        db.commit()
    assert client.post("/api/v1/auth/login", json={"identity": "Sith", "password": os.environ["ADMIN_SITH_PASSWORD"]}).status_code == 200
    rows = client.get("/api/v1/platform/request-tickets?request_type=DEMO")
    assert rows.status_code == 200
    ticket = rows.json()["items"][0]
    assert ticket["ticket_number"] == ticket_number
    assert ticket["company_size"] == "51–200"
    updated = client.patch(f"/api/v1/platform/request-tickets/{ticket['id']}", headers={"X-CSRF-Token": client.cookies.get(CSRF_COOKIE)}, json={"status": "COMPLETED", "admin_notes": "Demo delivered."})
    assert updated.status_code == 200
    assert updated.json()["ticket"]["status"] == "COMPLETED"
