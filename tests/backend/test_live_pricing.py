import base64
from datetime import datetime,timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func,select
from apps.api.aiopt_web.auth import CSRF_COOKIE
from apps.api.aiopt_web.database import Base,SessionLocal,engine
from apps.api.aiopt_web.main import app
from apps.api.aiopt_web.models import AuditEvent,Budget,LiveTelemetrySession,PriceOverride,PricingCatalogModel,PricingRecord,PricingRefresh,ProviderCredential,TelemetryEvent,User
from apps.api.aiopt_web.providers import OpenAIAdapter
from apps.api.aiopt_web.providers import ProviderError
from apps.api.aiopt_web.cost_engine import CostCalculator
from apps.api.aiopt_web.pricing_catalog import ALIASES,CATALOG,category,lifecycle
import apps.api.aiopt_web.pricing_api as pricing_api

PASSWORD="ValidPassword123";KEY="sk-live-sensitive-1234"
@pytest.fixture(autouse=True)
def clean(monkeypatch):
    monkeypatch.setenv("PROVIDER_CREDENTIAL_MASTER_KEY",base64.urlsafe_b64encode(b"z"*32).decode());Base.metadata.drop_all(engine);Base.metadata.create_all(engine);yield;Base.metadata.drop_all(engine)
@pytest.fixture
def client():
    with TestClient(app) as value:yield value
def login(client,name,role="ANALYST"):
    client.post("/api/v1/auth/register",json={"display_name":name,"username":name,"email":f"{name}@example.com","password":PASSWORD,"confirm_password":PASSWORD})
    with SessionLocal() as db:user=db.scalar(select(User).where(User.username==name));user.role=role;user.is_platform_admin=role=="ADMIN";db.commit();user_id=user.id
    client.post("/api/v1/auth/login",json={"identity":name,"password":PASSWORD});return user_id,{"X-CSRF-Token":client.cookies.get(CSRF_COOKIE)}
def models(_self,_key):return ([{"id":"gpt-5.6-luna","created":1_700_000_000,"owned_by":"openai"}],4.5)

def test_live_gateway_metrics_owner_isolation(client,monkeypatch):
    monkeypatch.setattr(OpenAIAdapter,"_models",models);owner,headers=login(client,"liveowner")
    with SessionLocal() as db:db.add(PricingRecord(provider="openai",model="gpt-5.6-luna",effective_from=datetime(2025,1,1,tzinfo=timezone.utc),input_price=.2,output_price=1.2,cached_input_price=.02,currency="USD",provenance="official-test",last_verified_at=datetime.now(timezone.utc)));db.commit()
    response=client.post("/api/v1/providers/openai/connect",headers=headers,json={"credential":KEY});assert KEY not in response.text
    assert client.post("/api/v1/live/start",headers=headers).json()["mode"]=="GATEWAY"
    event={"provider":"openai","model":"gpt-5.6-luna","application":"gateway","input_tokens":100,"output_tokens":20,"duration_ms":250,"metadata":{"status":"ok"}}
    assert client.post("/api/v1/telemetry",headers=headers,json=event).json()["cost"]["pricing_known"]
    snapshot=client.get("/api/v1/live/snapshot").json();assert snapshot["metrics"]["requests"]==1;assert snapshot["items"][0]["metric_sources"]=={"tokens":"observed","latency":"locally_measured","cost":"estimated"}
    client.cookies.clear();login(client,"other");assert client.get("/api/v1/live/snapshot").json()["items"]==[]
    with SessionLocal() as db:assert db.scalar(select(TelemetryEvent).where(TelemetryEvent.user_id==owner)) is not None

def test_clear_blocks_live_then_preserves_configuration(client,monkeypatch):
    monkeypatch.setattr(OpenAIAdapter,"_models",models);owner,headers=login(client,"clearowner");client.post("/api/v1/providers/openai/connect",headers=headers,json={"credential":KEY});client.post("/api/v1/live/start",headers=headers)
    with SessionLocal() as db:db.add(Budget(user_id=owner,name="Keep",monthly_amount=10));db.commit()
    assert client.delete("/api/v1/telemetry",headers=headers).status_code==409
    client.post("/api/v1/live/stop",headers=headers);assert client.delete("/api/v1/telemetry",headers=headers).status_code==200
    with SessionLocal() as db:
        assert db.get(User,owner);assert db.scalar(select(ProviderCredential).where(ProviderCredential.user_id==owner));assert db.scalar(select(Budget).where(Budget.user_id==owner));assert db.scalar(select(func.count()).select_from(LiveTelemetrySession).where(LiveTelemetrySession.user_id==owner))==0

def test_pricing_refresh_rbac_audit_and_override(client,monkeypatch):
    monkeypatch.setattr(OpenAIAdapter,"_models",models)
    _owner,headers=login(client,"analyst");assert client.post("/api/v1/admin/pricing/refresh",headers=headers,json={"apply":False}).status_code==403
    client.cookies.clear();admin,headers=login(client,"priceadmin","ADMIN")
    assert client.post("/api/v1/providers/openai/connect",headers=headers,json={"credential":KEY}).status_code==200
    with SessionLocal() as db:db.add(PriceOverride(user_id=admin,provider="openai",model="gpt-5.6-luna",input_price=99,output_price=100));db.commit()
    assert client.post("/api/v1/admin/pricing/refresh",headers=headers,json={"apply":False}).json()["applied"] is False
    assert client.post("/api/v1/admin/pricing/refresh",headers=headers,json={"apply":True}).status_code==200
    with SessionLocal() as db:assert db.scalar(select(PriceOverride).where(PriceOverride.user_id==admin)).input_price==99;assert db.scalar(select(PricingRefresh).where(PricingRefresh.admin_user_id==admin)).success

def test_malformed_pricing_rejected_atomically(client,monkeypatch):
    monkeypatch.setattr(OpenAIAdapter,"_models",models)
    _admin,headers=login(client,"badprices","ADMIN")
    client.post("/api/v1/providers/openai/connect",headers=headers,json={"credential":KEY})
    with SessionLocal() as db:before=db.scalar(select(func.count()).select_from(pricing_api.PricingRecord))
    monkeypatch.setattr(pricing_api,"CATALOG",(("openai","bad","-1","2","0"),))
    assert client.post("/api/v1/admin/pricing/refresh",headers=headers,json={"apply":True}).status_code==422
    with SessionLocal() as db:assert db.scalar(select(func.count()).select_from(pricing_api.PricingRecord))==before;assert db.scalar(select(PricingRefresh)).success is False

def test_refresh_resolves_only_admin_stored_key_and_catalog_is_independent(client,monkeypatch,caplog):
    seen=[]
    def capture(_self,key):seen.append(key);return models(_self,key)
    monkeypatch.setattr(OpenAIAdapter,"_models",capture)
    _user,user_headers=login(client,"customer");client.post("/api/v1/providers/openai/connect",headers=user_headers,json={"credential":"sk-customer-private"})
    client.cookies.clear();admin,headers=login(client,"catalogadmin","ADMIN")
    missing=client.post("/api/v1/admin/pricing/refresh",headers=headers,json={"provider":"openai","apply":False});assert missing.status_code==409;assert "not configured" in missing.json()["detail"]
    client.post("/api/v1/providers/openai/connect",headers=headers,json={"credential":KEY});seen.clear();result=client.post("/api/v1/admin/pricing/refresh",headers=headers,json={"provider":"openai","apply":True});assert result.status_code==200;assert seen==[KEY]
    assert KEY not in result.text and "sk-customer-private" not in result.text and KEY not in caplog.text
    with SessionLocal() as db:
        catalog=db.scalar(select(PricingCatalogModel));refresh=db.scalar(select(PricingRefresh).where(PricingRefresh.success.is_(True)));assert catalog.model_id=="gpt-5.6-luna";assert refresh.admin_user_id==admin;assert refresh.provider_credential_id;assert KEY not in str(refresh.validation_errors)

def test_signed_in_pricing_catalog_unknown_override_filters_and_sort(client):
    owner,_headers=login(client,"priceviewer")
    with SessionLocal() as db:
        db.add(PricingCatalogModel(provider="openai",model_id="unknown-model",display_name="Unknown Model",catalog_source_reference="provider",retrieved_at=datetime.now(timezone.utc)));db.add(PriceOverride(user_id=owner,provider="openai",model="gpt-5.6-luna",input_price=0.1,output_price=0.5));db.commit()
    data=client.get("/api/v1/pricing?sort=input").json();by_model={x["model"]:x for x in data["items"]};assert data["categories"]==["TEXT_REASONING"];assert set(data["providers"])>={"openai","anthropic","google","xai","mistral","deepseek","cohere","perplexity"};assert by_model["unknown-model"]["status"]=="UNKNOWN";assert by_model["unknown-model"]["pricing_category"]=="UNKNOWN";assert by_model["unknown-model"]["input_price_per_1m"] is None;assert by_model["gpt-5.6-luna"]["status"]=="MANUAL_OVERRIDE";assert by_model["gpt-5.6-luna"]["pricing_category"]=="TEXT_REASONING";assert by_model["gpt-5.6-luna"]["input_price_per_1m"]==.1
    assert {x["model"] for x in client.get("/api/v1/pricing?missing=true").json()["items"]}=={"unknown-model","command-a-plus-05-2026"}

def test_revoked_admin_key_leaves_previous_catalog_intact(client,monkeypatch):
    monkeypatch.setattr(OpenAIAdapter,"_models",models);_admin,headers=login(client,"revokedadmin","ADMIN");client.post("/api/v1/providers/openai/connect",headers=headers,json={"credential":KEY})
    with SessionLocal() as db:before=PricingRecord(provider="openai",model="gpt-5.6-luna",effective_from=datetime(2025,1,1,tzinfo=timezone.utc),input_price=.2,output_price=1.2,cached_input_price=.02,currency="USD",provenance="official-test",last_verified_at=datetime.now(timezone.utc));db.add(before);db.commit();before_id=before.id
    def revoked(*_):raise ProviderError("OpenAI rejected this credential.","INVALID")
    monkeypatch.setattr(OpenAIAdapter,"_models",revoked);response=client.post("/api/v1/admin/pricing/refresh",headers=headers,json={"provider":"openai","apply":True});assert response.status_code==401;assert KEY not in response.text
    with SessionLocal() as db:assert db.get(PricingRecord,before_id).effective_to is None;assert db.scalar(select(PricingRefresh).where(PricingRefresh.success.is_(False))).validation_errors==["OpenAI rejected this credential."]

def test_cross_provider_repricing_preserves_workload_and_owner_override(client):
    owner,_headers=login(client,"repriceowner")
    with SessionLocal() as db:db.add(PriceOverride(user_id=owner,provider="anthropic",model="claude-sonnet-5",input_price=1,output_price=2));db.commit()
    response=client.post("/api/v1/pricing/compare",json={"provider":"anthropic","model":"claude-sonnet-5","input_tokens":1_000_000,"output_tokens":1_000_000})
    assert response.status_code==200;data=response.json();assert data["workload_preserved"] is True;assert data["current"]["estimated_cost"]==3;assert 1<=len(data["alternatives"])<=8;assert all("quality equivalence" in x["notice"].lower() for x in data["alternatives"])
    assert client.post("/api/v1/pricing/compare",json={"provider":"bad","model":"missing","input_tokens":1,"output_tokens":1}).status_code==404

def test_preview_classifies_price_directions_unknowns_and_override_protection(client,monkeypatch):
    monkeypatch.setattr(OpenAIAdapter,"_models",lambda *_:([{"id":"gpt-5.6-luna"},{"id":"brand-new-unknown"}],3));admin,headers=login(client,"previewadmin","ADMIN");client.post("/api/v1/providers/openai/connect",headers=headers,json={"credential":KEY})
    with SessionLocal() as db:
        db.add(PricingRecord(provider="openai",model="gpt-5.6-luna",effective_from=datetime(2025,1,1,tzinfo=timezone.utc),input_price=.1,output_price=2,cached_input_price=.02,currency="USD",provenance="old",last_verified_at=datetime(2025,1,1,tzinfo=timezone.utc)));db.add(PriceOverride(user_id=admin,provider="openai",model="gpt-5.6-luna",input_price=.05,output_price=.5));db.commit()
    preview=client.post("/api/v1/admin/pricing/refresh",headers=headers,json={"provider":"openai","apply":False}).json();directions={x["dimension"]:x["direction"] for x in preview["changes"][0]["dimensions"]};assert directions["input"]=="INCREASED";assert directions["output"]=="DECREASED";assert preview["models_missing_pricing"]==["brand-new-unknown"];assert preview["manual_overrides_protecting_effective_price"]==["gpt-5.6-luna"]
    client.post("/api/v1/admin/pricing/refresh",headers=headers,json={"provider":"openai","apply":True,"confirm_anomalies":True})
    with SessionLocal() as db:active=db.scalar(select(PricingRecord).where(PricingRecord.model=="gpt-5.6-luna",PricingRecord.effective_to.is_(None)));assert float(active.input_price)==.2;assert db.scalar(select(PriceOverride).where(PriceOverride.user_id==admin)).input_price==.05
    live=client.post("/api/v1/telemetry",headers=headers,json={"provider":"openai","model":"gpt-5.6-luna","application":"effective-price","input_tokens":100,"output_tokens":20});assert live.json()["cost"]["calculated"]==pytest.approx(.000015);assert live.json()["cost"]["pricing_source"]=="MANUAL_OVERRIDE"

def test_stale_status_uses_documented_180_day_review_policy(client):
    _owner,_headers=login(client,"staleviewer")
    with SessionLocal() as db:db.add(PricingRecord(provider="openai",model="old-model",effective_from=datetime(2024,1,1,tzinfo=timezone.utc),input_price=1,output_price=2,currency="USD",provenance="official",last_verified_at=datetime(2024,1,1,tzinfo=timezone.utc)));db.commit()
    row=next(x for x in client.get("/api/v1/pricing").json()["items"] if x["model"]=="old-model");assert row["status"]=="STALE";assert row["stale_after_days"]==180;assert row["input_price_per_1m"]==1

def test_unknown_live_model_never_fabricates_cost(client):
    _owner,headers=login(client,"unknowncost");response=client.post("/api/v1/telemetry",headers=headers,json={"provider":"openai","model":"no-price-model","application":"gateway","input_tokens":10,"output_tokens":5});assert response.json()["cost"]=={"provider_recorded":None,"calculated":None,"pricing_known":False,"pricing_source":None}

def test_expanded_official_catalog_exact_values_and_existing_four():
    prices={model:(inp,out,cached) for provider,model,inp,out,cached in CATALOG if provider=="openai"};assert len(prices)>=20
    assert prices["gpt-6-astra"]==("10","50","1");assert prices["gpt-5.6-sol"]==("4","20","0.4");assert prices["gpt-5.6-terra"]==("2","12","0.2");assert prices["gpt-5.6-luna"]==("0.2","1.2","0.02")
    assert prices["gpt-4.1"]==("2","8","0.5");assert prices["gpt-4o"]==("2.5","10","1.25");assert prices["gpt-5-nano"]==("0.05","0.4","0.005");assert prices["o4-mini"]==("1.1","4.4","0.275")
    assert prices["gpt-5.4-pro"][2] is None

def test_public_demo_pricing_is_static_sanitized_and_database_independent(client):
    response=client.get("/api/v1/pricing/demo");assert response.status_code==200;data=response.json();assert data["workload"]=="SIMULATED";assert len(data["items"])==8
    assert {x["provider"] for x in data["items"]}=={"openai","anthropic","google","xai","mistral","deepseek","cohere","perplexity"};assert all(x["pricing_unit"]=="USD_PER_MILLION_TOKENS" for x in data["items"])

def test_exact_alias_resolution_no_fuzzy_matching_and_categories():
    assert ALIASES["gpt-5.6"]=="gpt-5.6-sol";assert ALIASES["gpt-4o-2024-08-06"]=="gpt-4o";assert "gpt-4o-made-up" not in ALIASES
    assert category("gpt-realtime-2")=="REALTIME";assert category("gpt-image-2")=="IMAGE";assert category("text-embedding-3-large")=="EMBEDDINGS";assert category("sora-2")=="VIDEO";assert lifecycle("gpt-4o")=="LEGACY";assert lifecycle("gpt-6-astra")=="CURRENT"

def test_cost_engine_resolves_only_explicit_snapshot_alias():
    at=datetime.now(timezone.utc)
    with SessionLocal() as db:
        db.add(PricingRecord(provider="openai",model="gpt-4o",effective_from=datetime(2024,1,1,tzinfo=timezone.utc),input_price=2.5,output_price=10,cached_input_price=1.25,currency="USD",provenance="official",last_verified_at=at));db.commit();calculator=CostCalculator(db)
        assert calculator.calculate("openai","gpt-4o-2024-08-06",at,1_000_000,1_000_000).total_cost==pytest.approx(12.5);assert calculator.calculate("openai","gpt-4o-made-up",at,1,1) is None

def test_admin_preview_category_lifecycle_alias_counts(client,monkeypatch):
    discovered=[{"id":"gpt-5.6"},{"id":"gpt-realtime-2"},{"id":"gpt-4o"},{"id":"unpriced-new"}];monkeypatch.setattr(OpenAIAdapter,"_models",lambda *_:(discovered,2));_admin,headers=login(client,"countadmin","ADMIN");client.post("/api/v1/providers/openai/connect",headers=headers,json={"credential":KEY});preview=client.post("/api/v1/admin/pricing/refresh",headers=headers,json={"provider":"openai","apply":False}).json();assert preview["models_discovered"]==4;assert preview["alias_resolved_models"]==1;assert preview["non_token_models"]==1;assert preview["current_models"]==1;assert preview["legacy_models"]==1;assert set(preview["models_missing_pricing"])=={"gpt-realtime-2","unpriced-new"}
