from datetime import datetime,timedelta,timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from apps.api.aiopt_web.auth import CSRF_COOKIE
from apps.api.aiopt_web.database import Base,SessionLocal,engine
from apps.api.aiopt_web.main import app
from apps.api.aiopt_web.models import ImportJob,TelemetryEvent,User
from apps.api.aiopt_web.worker import claim_next,execute,recover_stale_jobs
from apps.api.aiopt_web.telemetry_import import cancellation_path,storage_path
PASSWORD="ValidPassword123"
@pytest.fixture(autouse=True)
def clean():Base.metadata.drop_all(engine);Base.metadata.create_all(engine);yield;Base.metadata.drop_all(engine)
@pytest.fixture
def client():
    with TestClient(app) as value:yield value
def login(client,name):
    client.post('/api/v1/auth/register',json={'display_name':name,'username':name,'email':f'{name}@example.com','password':PASSWORD,'confirm_password':PASSWORD});client.post('/api/v1/auth/login',json={'identity':name,'password':PASSWORD})
def csrf(client):return {'X-CSRF-Token':client.cookies.get(CSRF_COOKIE)}
def seed(name):
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.username==name))
        for day in range(10):db.add(TelemetryEvent(user_id=user.id,timestamp=datetime.now(timezone.utc)-timedelta(days=day),provider='openai',model='gpt',application='app',input_tokens=100,output_tokens=20,total_tokens=120,estimated_cost=day+1,duration_ms=100))
        db.commit()
def test_forecast_optimization_anomaly_budget_scenario_report_integration_and_ownership(client):
    login(client,'owner');seed('owner');headers=csrf(client)
    forecast=client.post('/api/v1/forecasts?metric=spend&horizon=30',headers=headers);assert forecast.status_code==201;forecast_id=forecast.json()['id']
    assert client.get('/api/v1/optimization').status_code==200;assert client.get('/api/v1/anomalies').status_code==200
    budget=client.post('/api/v1/budgets',headers=headers,json={'name':'Monthly','monthly_amount':100,'period':'monthly','warning_threshold':80,'is_active':True});assert budget.status_code==201;budget_id=budget.json()['id']
    scenario=client.post('/api/v1/scenarios',headers=headers,json={'name':'Plan','monthly_requests':1000,'input_tokens_per_request':100,'output_tokens_per_request':20,'input_price_per_million':2,'output_price_per_million':4});assert scenario.status_code==201;scenario_id=scenario.json()['id']
    integration=client.post('/api/v1/integrations',headers=headers,json={'name':'OTel','kind':'opentelemetry','endpoint':'https://collector.invalid','secret_env_name':'OTEL_API_KEY'});assert integration.status_code==201;integration_id=integration.json()['id'];assert 'API_KEY' not in integration.text
    assert client.get('/api/v1/reports/executive').json()['requests']==10;csv=client.get('/api/v1/reports/executive.csv');assert csv.status_code==200 and 'text/csv' in csv.headers['content-type']
    client.cookies.clear();login(client,'other')
    assert client.get(f'/api/v1/forecasts/runs/{forecast_id}').status_code==404;assert client.get(f'/api/v1/scenarios/{scenario_id}').status_code==404
    assert client.patch(f'/api/v1/budgets/{budget_id}',headers=csrf(client),json={'name':'X','monthly_amount':1,'period':'monthly','warning_threshold':80,'is_active':True}).status_code==404
    assert client.delete(f'/api/v1/integrations/{integration_id}',headers=csrf(client)).status_code==404
    assert client.get('/api/v1/budgets').json()['items']==[];assert client.get('/api/v1/scenarios').json()['items']==[];assert client.get('/api/v1/integrations').json()['items']==[]
def test_forecast_requires_history(client):login(client,'owner');assert client.post('/api/v1/forecasts',headers=csrf(client)).status_code==422
def test_worker_claim_is_atomic_and_stale_jobs_requeue():
    with SessionLocal() as db:
        user=User(username='workeruser',email='w@example.com',display_name='W',password_hash='x');db.add(user);db.flush();job=ImportJob(user_id=user.id,filename='x.csv',file_size=1,file_format='csv',storage_id='storage',status='QUEUED');db.add(job);db.commit();job_id=job.id
    assert claim_next('one')==job_id;assert claim_next('two') is None
    with SessionLocal() as db:job=db.get(ImportJob,job_id);job.claimed_at=datetime.now(timezone.utc)-timedelta(hours=1);db.commit()
    assert recover_stale_jobs(15)==1
    with SessionLocal() as db:assert db.get(ImportJob,job_id).status=='QUEUED'
def test_worker_cancellation_checkpoint_rolls_back_all_rows():
    content='application,provider,model,input_tokens\n'+''.join('a,p,m,1\n' for _ in range(500))
    with SessionLocal() as db:
        user=User(username='canceluser',email='c@example.com',display_name='C',password_hash='x');db.add(user);db.flush();job=ImportJob(user_id=user.id,filename='x.csv',file_size=len(content),file_format='csv',storage_id='cancel-storage',status='QUEUED',mapping={'application':'application','provider':'provider','model':'model','input_tokens':'input_tokens'},detected_encoding='utf-8',detected_delimiter=',');db.add(job);db.commit();job_id=job.id
    storage_path('cancel-storage').write_text(content,encoding='utf-8');assert claim_next('cancel-worker')==job_id;cancellation_path('cancel-storage').touch();assert execute(job_id,'cancel-worker') is False
    with SessionLocal() as db:assert db.get(ImportJob,job_id).status=='CANCELLED';assert db.scalar(select(TelemetryEvent).where(TelemetryEvent.import_job_id==job_id)) is None
