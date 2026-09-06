from fastapi.testclient import TestClient
from apps.api.aiopt_web.database import make_engine
from apps.api.aiopt_web.main import app

def test_railway_postgresql_urls_select_psycopg():
    engine=make_engine("postgresql://user:password@localhost/database")
    assert engine.url.drivername=="postgresql+psycopg"
    engine.dispose()

def test_spa_fallback_and_api_404_are_separate():
    with TestClient(app) as client:
        for path in ("/","/login","/dashboard","/settings"):
            response=client.get(path);assert response.status_code==200;assert "text/html" in response.headers["content-type"]
        response=client.get("/api/v1/not-a-real-route")
        assert response.status_code==404;assert response.headers["content-type"].startswith("application/json");assert response.json()=={"detail":"Not Found"}
        assert client.post("/api/v1/auth/login",json={"identity":"missing","password":"invalid"}).status_code==401
