"""Benchmark an existing benchmark user's endpoints with 10 samples."""
import statistics,time,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from fastapi.testclient import TestClient
from apps.api.aiopt_web.auth import CSRF_COOKIE
from apps.api.aiopt_web.main import app

def sample(call,runs=10):
    values=[]
    for _ in range(runs):
        started=time.perf_counter();response=call();response.raise_for_status();values.append((time.perf_counter()-started)*1000)
    return {"median_ms":round(statistics.median(values),2),"p95_ms":round(sorted(values)[-1],2)}
def main():
    with TestClient(app) as client:
        response=client.post("/api/v1/auth/login",json={"identity":"benchmark","password":"SyntheticBenchmark123"});response.raise_for_status();headers={"X-CSRF-Token":client.cookies.get(CSRF_COOKIE)}
        for path in ("/api/v1/overview","/api/v1/usage","/api/v1/costs","/api/v1/models","/api/v1/optimization","/api/v1/anomalies","/api/v1/budgets"):print(path,sample(lambda path=path:client.get(path)))
        print("forecast",sample(lambda:client.post("/api/v1/forecasts?metric=spend&horizon=30",headers=headers)))
if __name__=="__main__":main()
