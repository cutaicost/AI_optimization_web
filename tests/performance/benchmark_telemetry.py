"""Opt-in synthetic telemetry benchmark: python tests/performance/benchmark_telemetry.py."""
import os,time,tracemalloc,tempfile,sys,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
DB=Path(tempfile.gettempdir())/"aiopt-benchmark.sqlite"
os.environ["APP_ENV"]="benchmark";os.environ.setdefault("DATABASE_URL",f"sqlite:///{DB.as_posix()}")
os.environ["".join(("SESSION","_SECRET"))]="".join(("local","benchmark","session","material"))
from fastapi.testclient import TestClient
from apps.api.aiopt_web.auth import CSRF_COOKIE
from apps.api.aiopt_web.database import Base,engine
from apps.api.aiopt_web.database import SessionLocal
from apps.api.aiopt_web.main import app
from apps.api.aiopt_web.models import ImportJob
from apps.api.aiopt_web.worker import process_next
from sqlalchemy import text

PASSWORD="SyntheticBenchmark123"
HEADER="timestamp,application,provider,model,input_tokens,output_tokens,cost,latency_ms,padding\n"
def fixture(rows):
    handle=tempfile.NamedTemporaryFile("w",suffix=".csv",delete=False,encoding="utf-8",newline="")
    handle.write(HEADER)
    for i in range(rows):handle.write(f"2026-01-{i%28+1:02d}T00:00:00Z,app-{i%8},provider-{i%3},model-{i%12},{i%500},{i%100},{i%100/10000:.4f},{i%2000},{'x'*180}\n")
    handle.close();return Path(handle.name)
def timed(client,path):
    start=time.perf_counter();response=client.get(path);response.raise_for_status();return round((time.perf_counter()-start)*1000,2)
def database_bytes():
    if engine.dialect.name=="sqlite":return DB.stat().st_size if DB.exists() else 0
    with engine.connect() as connection:return connection.scalar(text("select pg_database_size(current_database())"))
def distribution(client,path,runs=5):
    values=[timed(client,path) for _ in range(runs)];return {"median_ms":round(statistics.median(values),2),"p95_ms":round(max(values),2)}
def main():
    if engine.dialect.name=="sqlite":DB.unlink(missing_ok=True)
    Base.metadata.drop_all(engine);Base.metadata.create_all(engine)
    with TestClient(app) as client:
        client.post("/api/v1/auth/register",json={"display_name":"Benchmark","username":"benchmark","email":"benchmark@example.com","password":PASSWORD,"confirm_password":PASSWORD});client.post("/api/v1/auth/login",json={"identity":"benchmark","password":PASSWORD});headers={"X-CSRF-Token":client.cookies.get(CSRF_COOKIE)}
        print("rows=0",{p:timed(client,p) for p in ("/api/v1/overview","/api/v1/usage","/api/v1/costs","/api/v1/models")})
        counts=(1200,18000,150000,500000,1000000) if os.getenv("BENCHMARK_LARGE")=="1" else (1200,18000,150000)
        for count in counts:
            client.delete("/api/v1/telemetry",headers=headers).raise_for_status()
            path=fixture(count);size=path.stat().st_size;before_bytes=database_bytes();tracemalloc.start();started=time.perf_counter()
            job=client.post("/api/v1/import/start",headers=headers,json={"filename":"synthetic.csv","file_size":size,"format":"csv"}).json()["import"]["id"]
            upload_started=time.perf_counter()
            with path.open("rb") as source:client.post(f"/api/v1/import/{job}/upload",headers=headers,files={"file":("synthetic.csv",source,"text/csv")}).raise_for_status()
            upload_seconds=time.perf_counter()-upload_started;analyzed=client.post(f"/api/v1/import/{job}/analyze",headers=headers).json();queued=time.perf_counter();result=client.post(f"/api/v1/import/{job}/commit",headers=headers,json={"mapping":analyzed["suggested_mapping"]});result.raise_for_status();enqueue_ms=(time.perf_counter()-queued)*1000;worker_started=time.perf_counter();queue_ms=(worker_started-queued)*1000;process_next("benchmark-worker");worker_seconds=time.perf_counter()-worker_started;_,peak=tracemalloc.get_traced_memory();tracemalloc.stop();path.unlink(missing_ok=True)
            with SessionLocal() as db:finished=db.get(ImportJob,job);committed=finished.rows_imported;rejected=finished.rows_rejected
            growth=database_bytes()-before_bytes;endpoints={p:distribution(client,p) for p in ("/api/v1/overview","/api/v1/usage","/api/v1/costs","/api/v1/models","/api/v1/optimization","/api/v1/anomalies","/api/v1/budgets")}
            forecast_values=[]
            for _ in range(5):forecast_started=time.perf_counter();forecast=client.post("/api/v1/forecasts?metric=spend&horizon=30",headers=headers);forecast.raise_for_status();forecast_values.append((time.perf_counter()-forecast_started)*1000)
            print(f"rows={count} size_mb={size/1_000_000:.2f} upload_s={upload_seconds:.2f} enqueue_ms={enqueue_ms:.2f} queue_ms={queue_ms:.2f} worker_s={worker_seconds:.2f} total_s={time.perf_counter()-started:.2f} peak_python_mb={peak/1_000_000:.1f} committed={committed} rejected={rejected} db_growth_mb={growth/1_000_000:.2f}",endpoints,"forecast",{"median_ms":round(statistics.median(forecast_values),2),"p95_ms":round(max(forecast_values),2)})
    engine.dispose()
    if DB.exists() and engine.dialect.name=="sqlite":DB.unlink(missing_ok=True)
if __name__=="__main__":main()
