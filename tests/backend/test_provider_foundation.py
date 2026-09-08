import base64,logging
from datetime import datetime,timedelta,timezone
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from apps.api.aiopt_web.auth import CSRF_COOKIE
from apps.api.aiopt_web.cost_engine import CostCalculator
from apps.api.aiopt_web.database import Base,SessionLocal,engine
from apps.api.aiopt_web.main import app
from apps.api.aiopt_web.models import PricingRecord,ProviderCredential,User
from apps.api.aiopt_web.provider_credentials import CredentialConfigurationError,decrypt_credential,encrypt_credential
from apps.api.aiopt_web.providers import OpenAIAdapter,ProviderError

PASSWORD="ValidPassword123";KEY="sk-test-sensitive-value-1234"
@pytest.fixture(autouse=True)
def clean(monkeypatch):
    monkeypatch.setenv("PROVIDER_CREDENTIAL_MASTER_KEY",base64.urlsafe_b64encode(b"x"*32).decode());Base.metadata.drop_all(engine);Base.metadata.create_all(engine);yield;Base.metadata.drop_all(engine)
@pytest.fixture
def client():
    with TestClient(app) as value:yield value
def login(client,name,role="ADMIN"):
    client.post("/api/v1/auth/register",json={"display_name":name,"username":name,"email":f"{name}@example.com","password":PASSWORD,"confirm_password":PASSWORD})
    with SessionLocal() as db:user=db.scalar(select(User).where(User.username==name));user.role=role;db.commit()
    client.post("/api/v1/auth/login",json={"identity":name,"password":PASSWORD});return {"X-CSRF-Token":client.cookies.get(CSRF_COOKIE)}
def visible_models(_self,_key):return ([{"id":"gpt-test","created":1_700_000_000,"owned_by":"openai"}],12.5)

def test_encryption_is_authenticated_versioned_and_requires_master_key(monkeypatch):
    encrypted=encrypt_credential(KEY,"owner","openai");assert KEY not in encrypted;assert decrypt_credential(encrypted,"owner","openai")==KEY
    with pytest.raises(Exception):decrypt_credential(encrypted,"other","openai")
    monkeypatch.delenv("PROVIDER_CREDENTIAL_MASTER_KEY")
    with pytest.raises(CredentialConfigurationError):encrypt_credential(KEY,"owner","openai")

def test_connect_validate_models_isolation_redaction_and_disconnect(client,monkeypatch,caplog):
    monkeypatch.setattr(OpenAIAdapter,"_models",visible_models);headers=login(client,"owner");caplog.set_level(logging.DEBUG)
    connected=client.post("/api/v1/providers/openai/connect",headers=headers,json={"credential":KEY});assert connected.status_code==200;assert KEY not in connected.text;assert connected.json()["status"]=="CONNECTED"
    with SessionLocal() as db:row=db.scalar(select(ProviderCredential));assert KEY not in row.encrypted_credential;assert decrypt_credential(row.encrypted_credential,row.user_id,row.provider)==KEY
    assert client.post("/api/v1/providers/openai/validate",headers=headers).status_code==200;models=client.get("/api/v1/providers/openai/models");assert models.json()["items"][0]["id"]=="gpt-test";assert models.json()["items"][0]["context_window"] is None
    client.cookies.clear();other=login(client,"other");assert client.get("/api/v1/providers/openai").json()["status"]=="NOT_CONNECTED";assert client.delete("/api/v1/providers/openai",headers=other).status_code==404
    client.cookies.clear();headers=login(client,"owner");assert client.delete("/api/v1/providers/openai",headers=headers).json()["revocation_required"] is True
    with SessionLocal() as db:assert db.scalar(select(ProviderCredential)) is None
    assert KEY not in caplog.text

def test_provider_controls_are_owner_available_and_public_payload_is_sanitized(client,monkeypatch):
    monkeypatch.setattr(OpenAIAdapter,"_models",visible_models);analyst=login(client,"analyst","ANALYST")
    assert client.get("/api/v1/providers").status_code==200
    assert client.post("/api/v1/providers/openai/connect",headers=analyst,json={"credential":KEY}).status_code==200
    assert client.get("/api/v1/providers/openai/models").status_code==200
    payload=client.get("/api/telemetry").json();assert payload["status"]=="AVAILABLE";assert payload["usage_available"] is False;assert KEY not in str(payload);assert "masked_identifier" not in payload

def test_encrypted_connection_persists_across_database_sessions(client,monkeypatch):
    monkeypatch.setattr(OpenAIAdapter,"_models",visible_models);headers=login(client,"restartadmin");client.post("/api/v1/providers/openai/connect",headers=headers,json={"credential":KEY})
    with SessionLocal() as first:credential_id=first.scalar(select(ProviderCredential)).id
    with SessionLocal() as restarted:row=restarted.get(ProviderCredential,credential_id);assert decrypt_credential(row.encrypted_credential,row.user_id,row.provider)==KEY;assert row.last_successful_connection_at is not None

def test_invalid_provider_credential_fails_safely_without_storage(client,monkeypatch):
    def invalid(*_):raise ProviderError("OpenAI rejected this credential.","INVALID")
    monkeypatch.setattr(OpenAIAdapter,"_models",invalid);response=client.post("/api/v1/providers/openai/connect",headers=login(client,"invaliduser"),json={"credential":KEY});assert response.status_code==401;assert KEY not in response.text
    with SessionLocal() as db:assert db.scalar(select(ProviderCredential)) is None

def price(db,id_,model,start,end,input_price,output_price,cached=None):
    db.add(PricingRecord(id=id_,provider="openai",model=model,effective_from=start,effective_to=end,input_price=Decimal(input_price),output_price=Decimal(output_price),cached_input_price=Decimal(cached) if cached else None,currency="USD",region=None,provenance="authoritative-test",last_verified_at=start))
def test_decimal_costs_versions_boundaries_unknown_zero_and_large_values():
    start=datetime(2025,1,1,tzinfo=timezone.utc);boundary=start+timedelta(days=30)
    with SessionLocal() as db:
        price(db,"old","model",start,boundary,"2","4","1");price(db,"new","model",boundary,None,"3","6","1.5");db.commit();calculator=CostCalculator(db)
        old=calculator.calculate("openai","model",start,100,20);assert old.input_cost==Decimal("0.0002");assert old.output_cost==Decimal("0.00008");assert old.total_cost==Decimal("0.00028")
        assert calculator.calculate("openai","model",boundary,1_000_000,1_000_000).total_cost==Decimal("9")
        assert calculator.calculate("openai","model",boundary,0,0).total_cost==Decimal("0")
        assert calculator.calculate("openai","model",boundary,10**15,10**15).total_cost==Decimal("9000000000")
        cached=calculator.calculate("openai","model",boundary,100,20,40);assert cached.total_cost==Decimal("0.00036")
        assert calculator.calculate("openai","unknown",boundary,1,1) is None
