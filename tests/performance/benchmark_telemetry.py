"""Opt-in synthetic telemetry benchmark: python tests/performance/benchmark_telemetry.py."""
import os,time,tracemalloc,tempfile,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
DB=Path(tempfile.gettempdir())/"aiopt-benchmark.sqlite"
os.environ.update(APP_ENV="benchmark",DATABASE_URL=f"sqlite:///{DB.as_posix()}")
os.environ["".join(("SESSION","_SECRET"))]="".join(("local","benchmark","session","material"))
from fastapi.testclient import TestClient
from apps.api.aiopt_web.auth import CSRF_COOKIE
from apps.api.aiopt_web.database import Base,engine
from apps.api.aiopt_web.main import app
from apps.api.aiopt_web.worker import process_next

PASSWORD="SyntheticBenchmark123"
HEADER="timestamp,application,provider,model,input_tokens,output_tokens,cost,latency_ms,padding\n"
def fixture(rows):
    handle=tempfile.NamedTemporaryFile("w",suffix=".csv",delete=False,encoding="utf-8",newline="")
    handle.write(HEADER)
    for i in range(rows):handle.write(f"2026-01-{i%28+1:02d}T00:00:00Z,app-{i%8},provider-{i%3},model-{i%12},{i%500},{i%100},{i%100/10000:.4f},{i%2000},{'x'*180}\n")
    handle.close();return Path(handle.name)
def timed(client,path):
    start=time.perf_counter();response=client.get(path);response.raise_for_status();return round((time.perf_counter()-start)*1000,2)
def main():
    DB.unlink(missing_ok=True);Base.metadata.create_all(engine)
    with TestClient(app) as client:
        client.post("/api/v1/auth/register",json={"display_name":"Benchmark","username":"benchmark","email":"benchmark@example.com","password":PASSWORD,"confirm_password":PASSWORD});client.post("/api/v1/auth/login",json={"identity":"benchmark","password":PASSWORD});headers={"X-CSRF-Token":client.cookies.get(CSRF_COOKIE)}
        print("rows=0",{p:timed(client,p) for p in ("/api/v1/overview","/api/v1/usage","/api/v1/costs","/api/v1/models")})
        for count in (1200,18000,150000):
            client.delete("/api/v1/telemetry",headers=headers).raise_for_status()
            path=fixture(count);size=path.stat().st_size;tracemalloc.start();started=time.perf_counter()
            job=client.post("/api/v1/import/start",headers=headers,json={"filename":"synthetic.csv","file_size":size,"format":"csv"}).json()["import"]["id"]
            with path.open("rb") as source:client.post(f"/api/v1/import/{job}/upload",headers=headers,files={"file":("synthetic.csv",source,"text/csv")}).raise_for_status()
            analyzed=client.post(f"/api/v1/import/{job}/analyze",headers=headers).json();queued=time.perf_counter();result=client.post(f"/api/v1/import/{job}/commit",headers=headers,json={"mapping":analyzed["suggested_mapping"]});result.raise_for_status();enqueue_ms=(time.perf_counter()-queued)*1000;worker_started=time.perf_counter();process_next("benchmark-worker");worker_seconds=time.perf_counter()-worker_started;_,peak=tracemalloc.get_traced_memory();tracemalloc.stop();path.unlink(missing_ok=True)
            print(f"rows={count} size_mb={size/1_000_000:.2f} enqueue_ms={enqueue_ms:.2f} worker_s={worker_seconds:.2f} total_s={time.perf_counter()-started:.2f} peak_python_mb={peak/1_000_000:.1f}",{p:timed(client,p) for p in ("/api/v1/overview","/api/v1/usage","/api/v1/costs","/api/v1/models","/api/v1/optimization","/api/v1/anomalies","/api/v1/budgets")})
            forecast_started=time.perf_counter();forecast=client.post("/api/v1/forecasts?metric=spend&horizon=30",headers=headers);print("forecast_ms",round((time.perf_counter()-forecast_started)*1000,2),"status",forecast.status_code)
    engine.dispose();DB.unlink(missing_ok=True)
if __name__=="__main__":main()
