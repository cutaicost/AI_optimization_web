from datetime import timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func,select
from apps.api.aiopt_web.auth import CSRF_COOKIE
from apps.api.aiopt_web.database import Base,SessionLocal,engine
from apps.api.aiopt_web.main import app
from apps.api.aiopt_web.models import AuditEvent,Budget,EnterpriseSetting,TelemetryEvent,User
from apps.api.aiopt_web.security import hash_password,utcnow
PASSWORD="EnterpriseControl123"
@pytest.fixture(autouse=True)
def clean():Base.metadata.drop_all(engine);Base.metadata.create_all(engine);yield;Base.metadata.drop_all(engine)
@pytest.fixture
def client():
    with TestClient(app) as value:
        with SessionLocal() as db:db.add(User(username="controladmin",email="control@example.com",display_name="Control",password_hash=hash_password(PASSWORD),role="ADMIN"));db.commit()
        value.post("/api/v1/auth/login",json={"identity":"controladmin","password":PASSWORD});yield value
def csrf(client):return {"X-CSRF-Token":client.cookies.get(CSRF_COOKIE)}
def seed():
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.username=="controladmin"));db.add(Budget(user_id=user.id,name="Preserved",monthly_amount=100));db.add_all([TelemetryEvent(user_id=user.id,provider="p",model="m",application="a",timestamp=utcnow()-timedelta(days=days)) for days in (10,40,100,200,400)]);db.add(AuditEvent(actor_user_id=user.id,actor_role="ADMIN",action="seed",resource_type="test"));db.commit()
def test_retention_preview_execution_preserves_settings_and_audit(client):
    seed();assert client.get("/api/v1/admin/retention/preview?days=90").json()["rows_to_delete"]==3;result=client.post("/api/v1/admin/retention",headers=csrf(client),json={"days":90});assert result.status_code==200 and result.json()["deleted"]==3
    with SessionLocal() as db:assert db.scalar(select(func.count()).select_from(TelemetryEvent))==2;assert db.scalar(select(func.count()).select_from(Budget))==1;assert db.get(EnterpriseSetting,"telemetry_retention").value_json=={"days":90};assert db.scalar(select(func.count()).select_from(AuditEvent))>=2
    assert client.post("/api/v1/admin/retention",headers=csrf(client),json={"days":None}).json()["deleted"]==0;assert client.get("/api/v1/admin/retention/preview?days=7").status_code==422
def test_audit_and_diagnostics_exports_are_safe(client):
    seed();json_export=client.get("/api/v1/admin/audit/export.json");csv_export=client.get("/api/v1/admin/audit/export.csv");diagnostics=client.get("/api/v1/admin/system/export");assert json_export.status_code==csv_export.status_code==diagnostics.status_code==200;combined=json_export.text+csv_export.text+diagnostics.text
    for forbidden in ("SESSION_SECRET","OIDC_CLIENT_SECRET","postgresql+psycopg://"):assert forbidden not in combined
    assert "frontend_version" in diagnostics.json() and "storage" in diagnostics.json()
