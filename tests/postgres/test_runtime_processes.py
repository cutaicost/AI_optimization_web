"""Opt-in destructive PostgreSQL process validation.

Run only against a disposable database:
RUN_POSTGRES_RUNTIME=1 pytest -q tests/postgres/test_runtime_processes.py
"""
import os,signal,subprocess,sys,time
from pathlib import Path
import pytest
from sqlalchemy import func,select,update
from sqlalchemy.exc import SQLAlchemyError

if os.getenv("RUN_POSTGRES_RUNTIME")!="1":pytest.skip("opt-in PostgreSQL runtime test",allow_module_level=True)
from apps.api.aiopt_web.database import Base,SessionLocal,engine
from apps.api.aiopt_web.import_storage import get_import_storage
from apps.api.aiopt_web.models import ImportJob,TelemetryEvent,User
from apps.api.aiopt_web.security import utcnow
from apps.api.aiopt_web.worker import recover_stale_jobs

pytestmark=pytest.mark.skipif(engine.dialect.name!="postgresql",reason="PostgreSQL required")
MAPPING={"timestamp":"timestamp","application":"application","provider":"provider","model":"model","input_tokens":"input_tokens","output_tokens":"output_tokens","cost":"estimated_cost","latency_ms":"duration_ms"}
PYTHON=sys.executable

def wait_for(predicate,timeout=60):
    deadline=time.time()+timeout
    while time.time()<deadline:
        try:value=predicate()
        except SQLAlchemyError:value=None
        if value:return value
        time.sleep(.1)
    raise AssertionError("runtime condition timed out")
def status(job_id):
    with SessionLocal() as db:return db.get(ImportJob,job_id).status
def event_count(job_id):
    with SessionLocal() as db:return db.scalar(select(func.count()).select_from(TelemetryEvent).where(TelemetryEvent.import_job_id==job_id))
def job(rows=5_000):
    with SessionLocal() as db:
        user=db.scalar(select(User).limit(1))
        if not user:user=User(username="runtime",email="runtime@example.com",display_name="Runtime",password_hash="x");db.add(user);db.flush()
        item=ImportJob(user_id=user.id,filename="runtime.csv",file_size=1,file_format="csv",storage_id=os.urandom(16).hex(),status="QUEUED",mapping=MAPPING,detected_encoding="utf-8",detected_delimiter=",");db.add(item);db.commit();job_id=item.id
    with get_import_storage().open_writer(item.storage_id) as handle:
        handle.write(b"timestamp,application,provider,model,input_tokens,output_tokens,cost,latency_ms\n")
        line=b"2026-01-01T00:00:00Z,app,provider,model,1,1,0.001,10\n"
        for _ in range(rows):handle.write(line)
    return job_id
def worker():
    env={**os.environ,"WORKER_HEARTBEAT_SECONDS":"1","WORKER_LEASE_SECONDS":"4"}
    return subprocess.Popen([PYTHON,"-m","apps.api.aiopt_web.worker"],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
def stop(*processes):
    for process in processes:
        if process.poll() is not None:continue
        if os.name=="nt":subprocess.run(["taskkill","/PID",str(process.pid),"/T","/F"],capture_output=True)
        else:
            process.send_signal(signal.SIGKILL)
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:process.kill()

@pytest.fixture(autouse=True)
def clean():
    Base.metadata.drop_all(engine);Base.metadata.create_all(engine);yield
    wait_for(lambda:_drop_tables(),60)
def _drop_tables():Base.metadata.drop_all(engine);return True

def test_two_real_workers_claim_once_and_renew_leases():
    ids=[job(20_000),*[job() for _ in range(4)]];first=worker();second=worker()
    try:
        active=ids[0];wait_for(lambda:status(active)=="IMPORTING")
        with SessionLocal() as db:initial=db.get(ImportJob,active).lease_expires_at
        wait_for(lambda:_lease_renewed(active,initial))
        wait_for(lambda:all(status(x)=="COMPLETED" for x in ids),180)
        with SessionLocal() as db:
            rows=db.scalars(select(ImportJob).where(ImportJob.id.in_(ids))).all()
            assert len({x.id for x in rows})==5 and sum(x.rows_imported for x in rows)==40_000
            assert len({x.executor_id for x in rows})==2
    finally:stop(first,second)
def _lease_renewed(job_id,initial):
    with SessionLocal() as db:
        value=db.get(ImportJob,job_id).lease_expires_at;return value is not None and initial is not None and value>initial

def test_crash_recovery_preparing_importing_and_cancelling():
    preparing=job(1);env={**os.environ,"WORKER_LEASE_SECONDS":"4"}
    claimer=subprocess.Popen([PYTHON,"-c","from apps.api.aiopt_web.worker import claim_next;import time;claim_next('crash-preparing');time.sleep(60)"],env=env)
    wait_for(lambda:status(preparing)=="PREPARING");stop(claimer);time.sleep(4.2);assert recover_stale_jobs()==1 and status(preparing)=="QUEUED"

    importing=job(20_000);process=worker();wait_for(lambda:status(importing)=="IMPORTING");stop(process);assert event_count(importing)==0;time.sleep(4.2);recover_stale_jobs();replacement=worker()
    try:wait_for(lambda:status(importing)=="COMPLETED",180);assert event_count(importing)==20_000
    finally:stop(replacement)

    cancelling=job(1);claimer=subprocess.Popen([PYTHON,"-c","from apps.api.aiopt_web.worker import claim_next;from apps.api.aiopt_web.database import SessionLocal;from apps.api.aiopt_web.models import ImportJob;import time;j=claim_next('crash-cancelling');d=SessionLocal();x=d.get(ImportJob,j);x.status='CANCELLING';d.commit();d.close();time.sleep(60)"],env=env)
    wait_for(lambda:status(cancelling)=="CANCELLING");stop(claimer);time.sleep(4.2);assert recover_stale_jobs()==1 and status(cancelling)=="CANCELLED";assert event_count(cancelling)==0

def test_postgresql_restart_during_active_transaction():
    job_id=job(150_000);process=worker()
    try:
        wait_for(lambda:status(job_id)=="IMPORTING")
        data=Path(os.getenv("POSTGRES_DATA",r"C:\Program Files\PostgreSQL\17\data"));binary=Path(os.getenv("POSTGRES_BIN",r"C:\Program Files\PostgreSQL\17\bin"))
        stopped=subprocess.run([str(binary/"pg_ctl.exe"),"stop","-D",str(data),"-m","immediate","-w"],capture_output=True,text=True,timeout=60);assert stopped.returncode==0,stopped.stderr
        launch=f'''$c='"{binary/"pg_ctl.exe"}" start -D "{data}" -w';$r=Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{{CommandLine=$c}};if($r.ReturnValue -ne 0){{exit $r.ReturnValue}}'''
        started=subprocess.run(["powershell","-NoProfile","-Command",launch],capture_output=True,text=True,timeout=30);assert started.returncode==0,started.stderr
        wait_for(lambda:process.poll() is not None,60);replacement=worker()
        try:wait_for(lambda:status(job_id)=="COMPLETED",240);assert event_count(job_id)==150_000
        finally:stop(replacement)
    finally:stop(process)
