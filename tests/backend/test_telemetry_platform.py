import pytest,time
from fastapi.testclient import TestClient
from sqlalchemy import func,select
from apps.api.aiopt_web.auth import CSRF_COOKIE
from apps.api.aiopt_web.database import Base,SessionLocal,engine
from apps.api.aiopt_web.main import app
from apps.api.aiopt_web.models import AuditEvent,ImportJob,TelemetryEvent

PASSWORD="ValidPassword123"
CSV=b"timestamp,application,vendor,model_name,prompt_tokens,completion_tokens,total_cost,latency\n2026-01-01T00:00:00Z,Assistant,openai,gpt-5,100,25,0.0125,450\n2026-01-02T00:00:00Z,Search,anthropic,claude,80,20,0.02,700\n"

@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(engine);Base.metadata.create_all(engine);yield;Base.metadata.drop_all(engine)
@pytest.fixture
def client():
    with TestClient(app) as value:yield value
def signup(client,name):
    client.post("/api/v1/auth/register",json={"display_name":name,"username":name,"email":f"{name}@example.com","password":PASSWORD,"confirm_password":PASSWORD})
    client.post("/api/v1/auth/login",json={"identity":name,"password":PASSWORD})
def csrf(client):return {"X-CSRF-Token":client.cookies.get(CSRF_COOKIE)}
def start(client,content=CSV,filename="telemetry.csv",fmt="csv"):
    response=client.post("/api/v1/import/start",headers=csrf(client),json={"filename":filename,"file_size":len(content),"format":fmt});assert response.status_code==201
    return response.json()["import"]["id"]
def upload_analyze(client,import_id,content=CSV,filename="telemetry.csv"):
    assert client.post(f"/api/v1/import/{import_id}/upload",headers=csrf(client),files={"file":(filename,content)}).status_code==200
    result=client.post(f"/api/v1/import/{import_id}/analyze",headers=csrf(client));assert result.status_code==200;return result.json()
def wait_status(client,import_id,expected):
    for _ in range(200):
        job=client.get(f"/api/v1/import/{import_id}/status").json()["import"]
        if job["status"] in {"COMPLETED","FAILED","CANCELLED"}:break
        time.sleep(.02)
    assert job["status"]==expected;return job

def test_csv_import_mapping_commit_history_analytics_and_audit(client):
    signup(client,"first");import_id=start(client);analyzed=upload_analyze(client,import_id);assert analyzed["suggested_mapping"]["vendor"]=="provider"
    result=client.post(f"/api/v1/import/{import_id}/commit",headers=csrf(client),json={"mapping":analyzed["suggested_mapping"]});assert result.status_code==202;assert wait_status(client,import_id,"COMPLETED")["inserted_rows"]==2
    assert client.get("/api/v1/import/history").json()["items"][0]["inserted_rows"]==2
    usage=client.get("/api/v1/usage").json();assert usage["requests"]==2;assert usage["total_tokens"]==225
    costs=client.get("/api/v1/costs").json();assert costs["total_spend"]==pytest.approx(.0325)
    models=client.get("/api/v1/models").json();assert len(models["items"])==2
    overview=client.get("/api/v1/overview").json();assert overview["requests"]==2;assert overview["latest_import"]["status"]=="COMPLETED"
    with SessionLocal() as db:assert db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.action=="import.completed"))==1

def test_import_and_analytics_are_strictly_owner_scoped(client):
    signup(client,"first");import_id=start(client);analyzed=upload_analyze(client,import_id);client.post(f"/api/v1/import/{import_id}/commit",headers=csrf(client),json={"mapping":analyzed["suggested_mapping"]})
    client.cookies.clear();signup(client,"second")
    for suffix in ("status","rejected"):
        assert client.get(f"/api/v1/import/{import_id}/{suffix}").status_code==404
    assert client.post(f"/api/v1/import/{import_id}/commit",headers=csrf(client),json={"mapping":{"a":"application","b":"provider","c":"model"}}).status_code==404
    assert client.post(f"/api/v1/import/{import_id}/cancel",headers=csrf(client)).status_code==404
    assert client.get("/api/v1/import/history").json()["items"]==[]
    assert client.get("/api/v1/usage").json()["requests"]==0;assert client.get("/api/v1/costs").json()["total_spend"]==0;assert client.get("/api/v1/models").json()["items"]==[]

def test_false_completed_prevention_and_rejected_rows(client):
    signup(client,"first");bad=b"application,provider,model,input_tokens\napp,p,m,not-a-number\n";import_id=start(client,bad);analyzed=upload_analyze(client,import_id,bad)
    response=client.post(f"/api/v1/import/{import_id}/commit",headers=csrf(client),json={"mapping":analyzed["suggested_mapping"]});assert response.status_code==202
    status=wait_status(client,import_id,"FAILED");assert status["inserted_rows"]==0
    rejected=client.get(f"/api/v1/import/{import_id}/rejected").json();assert rejected["count"]==1
    with SessionLocal() as db:assert db.scalar(select(func.count()).select_from(TelemetryEvent))==0

def test_cancel_and_owner_scoped_reset(client):
    signup(client,"first");import_id=start(client);assert client.post(f"/api/v1/import/{import_id}/cancel",headers=csrf(client)).status_code==200
    second=start(client);analyzed=upload_analyze(client,second);client.post(f"/api/v1/import/{second}/commit",headers=csrf(client),json={"mapping":analyzed["suggested_mapping"]});wait_status(client,second,"COMPLETED")
    response=client.delete("/api/v1/telemetry",headers=csrf(client));assert response.json()=={"deleted":2,"imports_deleted":2,"forecasts_deleted":0}
    assert client.get("/api/v1/import/history").json()["items"]==[]

def test_clear_is_blocked_while_import_is_active(client):
    signup(client,"active");start(client)
    response=client.delete("/api/v1/telemetry",headers=csrf(client));assert response.status_code==409;assert "import is active" in response.json()["detail"]

def test_rejects_oversize_traversal_duplicate_and_incomplete_upload(client):
    signup(client,"first")
    assert client.post("/api/v1/import/start",headers=csrf(client),json={"filename":"x.csv","file_size":500_000_001,"format":"csv"}).status_code==422
    assert client.post("/api/v1/import/start",headers=csrf(client),json={"filename":"../x.csv","file_size":1,"format":"csv"}).status_code==400
    import_id=start(client);assert client.post(f"/api/v1/import/{import_id}/upload",headers=csrf(client),files={"file":("x.csv",b"short")}).status_code==400

def test_jsonl_import_and_malformed_input(client):
    signup(client,"first");content=b'{"application":"a","provider":"p","model":"m","input_tokens":2}\n';import_id=start(client,content,"data.jsonl","jsonl");assert upload_analyze(client,import_id,content,"data.jsonl")["import"]["total_rows"]==1
    malformed=b'{no}\n';bad_id=start(client,malformed,"bad.jsonl","jsonl");client.post(f"/api/v1/import/{bad_id}/upload",headers=csrf(client),files={"file":("bad.jsonl",malformed)});assert client.post(f"/api/v1/import/{bad_id}/analyze",headers=csrf(client)).status_code==400
