from datetime import timedelta
import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func,select
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable
from apps.api.aiopt_web.auth import CSRF_COOKIE,SESSION_COOKIE,bootstrap_admins
from apps.api.aiopt_web.database import Base,SessionLocal,engine
from apps.api.aiopt_web.main import app
import apps.api.aiopt_web.main as main_module
from apps.api.aiopt_web.models import Session as UserSession,TelemetryEvent,User
from apps.api.aiopt_web.security import utcnow,verify_password

PASSWORD="ValidPassword123"
@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(engine);Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)

@pytest.fixture
def client():
    with TestClient(app) as value:yield value

def register(client,username="ordinary",email="ordinary@example.com"):
    return client.post("/api/v1/auth/register",json={"display_name":"Ordinary User","username":username,"email":email,"password":PASSWORD,"confirm_password":PASSWORD})
def login(client,identity="ordinary",password=PASSWORD):return client.post("/api/v1/auth/login",json={"identity":identity,"password":password})
def csrf(client):return {"X-CSRF-Token":client.cookies.get(CSRF_COOKIE)}

def test_registration_normalizes_email_hashes_password_and_forces_user_role(client):
    response=register(client,email="Ordinary@Example.Com");assert response.status_code==201;assert response.json()["user"]["role"]=="ANALYST"
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.username=="ordinary"));assert user.email=="ordinary@example.com";assert user.password_hash!=PASSWORD;assert verify_password(user.password_hash,PASSWORD)
    payload={"display_name":"Bad","username":"badadmin","email":"bad@example.com","password":PASSWORD,"confirm_password":PASSWORD,"role":"ADMIN"}
    assert client.post("/api/v1/auth/register",json=payload).status_code==422

def test_registration_rejects_duplicates_malformed_and_password_mismatch(client):
    assert register(client).status_code==201;assert register(client).status_code==409
    assert client.post("/api/v1/auth/register",json={"display_name":"X","username":"other","email":"bad","password":PASSWORD,"confirm_password":PASSWORD}).status_code==422
    assert client.post("/api/v1/auth/register",json={"display_name":"X","username":"other","email":"other@example.com","password":PASSWORD,"confirm_password":"DifferentPassword123"}).status_code==422
    assert register(client,"Sith","reserved@example.com").status_code==409

def test_production_self_registration_is_closed_by_default(client,monkeypatch):
    monkeypatch.setattr(main_module,"cfg",main_module.cfg.__class__(**{**main_module.cfg.__dict__,"environment":"production"}))
    monkeypatch.delenv("SELF_REGISTRATION_ENABLED",raising=False)
    assert register(client).status_code==404

def test_login_session_me_logout_and_csrf(client):
    register(client);result=login(client);assert result.status_code==200;assert result.json()["redirect_to"]=="/app/overview";assert client.cookies.get(SESSION_COOKIE);assert client.cookies.get(CSRF_COOKIE)
    cookie_headers=result.headers.get_list("set-cookie");session_cookie=next(value for value in cookie_headers if value.startswith(f"{SESSION_COOKIE}="));csrf_cookie=next(value for value in cookie_headers if value.startswith(f"{CSRF_COOKIE}="));assert "HttpOnly" in session_cookie and "SameSite=lax" in session_cookie and "Path=/" in session_cookie and "Domain=" not in session_cookie;assert "HttpOnly" not in csrf_cookie and "SameSite=lax" in csrf_cookie and "Path=/" in csrf_cookie and "Domain=" not in csrf_cookie
    assert client.get("/api/v1/auth/me").status_code==200
    assert client.post("/api/v1/auth/logout").status_code==403
    assert client.post("/api/v1/auth/logout",headers=csrf(client)).status_code==200
    assert client.get("/api/v1/auth/me").status_code==401

def test_login_is_generic_disabled_accounts_are_rejected_and_rate_limited(client):
    register(client)
    assert login(client,"missing","wrong").status_code==401
    with SessionLocal() as db:user=db.scalar(select(User).where(User.username=="ordinary"));user.is_active=False;db.commit()
    assert login(client).status_code==403
    for _ in range(8):login(client,"attacker","wrong")
    assert login(client,"attacker","wrong").status_code==429

def test_session_expiry(client):
    register(client);login(client)
    with SessionLocal() as db:session=db.scalar(select(UserSession));session.expires_at=utcnow()-timedelta(seconds=1);db.commit()
    assert client.get("/api/v1/auth/me").status_code==401

def test_password_change_requires_current_password_and_revokes_session(client):
    register(client);login(client)
    assert client.post("/api/v1/auth/change-password",headers=csrf(client),json={"current_password":"wrong","new_password":"NewValidPassword456"}).status_code==400
    assert client.post("/api/v1/auth/change-password",headers=csrf(client),json={"current_password":PASSWORD,"new_password":"NewValidPassword456"}).status_code==200
    assert client.get("/api/v1/auth/me").status_code==401
    assert login(client,password="NewValidPassword456").status_code==200

def test_profile_update(client):
    register(client);login(client)
    assert client.get("/api/v1/profile").status_code==200
    response=client.patch("/api/v1/profile",headers=csrf(client),json={"display_name":"Updated","email":"updated@example.com","organization":"Example","job_title":"FinOps","preferences":{"theme":"dark"}})
    assert response.status_code==200;assert response.json()["user"]["display_name"]=="Updated"

def test_admin_bootstrap_is_exact_idempotent_and_does_not_reset_password(client):
    with SessionLocal() as db:
        admins=db.scalars(select(User).where(User.role=="ADMIN").order_by(User.username)).all();assert [u.username for u in admins]==["Beyond","Sith"];assert all(u.must_change_password and u.is_active for u in admins)
        original=admins[0].password_hash;admins[0].password_hash="changed-hash";db.commit();assert bootstrap_admins(db)==[];assert db.get(User,admins[0].id).password_hash=="changed-hash";assert original!="changed-hash"

def test_rbac_admin_users_and_final_admin_protection(client):
    register(client);login(client);assert client.get("/api/v1/admin/users").status_code==403
    client.cookies.clear();assert login(client,"Sith",os.environ["ADMIN_SITH_PASSWORD"]).status_code==200
    assert client.get("/api/v1/admin/users").status_code==428
    assert client.post("/api/v1/auth/change-password",headers=csrf(client),json={"current_password":os.environ["ADMIN_SITH_PASSWORD"],"new_password":"ChangedAdminPassword456"}).status_code==200
    admin_login=login(client,"Sith","ChangedAdminPassword456");assert admin_login.status_code==200;assert admin_login.json()["redirect_to"]=="/admin"
    users=client.get("/api/v1/admin/users").json()["items"];ordinary=next(user for user in users if user["username"]=="ordinary")
    detail=client.get(f"/api/v1/admin/users/{ordinary['id']}");assert detail.status_code==200;assert "password_hash" not in detail.text
    system=client.get("/api/v1/admin/system");assert system.status_code==200;assert "session_secret" not in system.text.lower()
    assert client.patch(f"/api/v1/admin/users/{ordinary['id']}",headers=csrf(client),json={"is_active":False}).status_code==200
    with SessionLocal() as db:
        beyond=db.scalar(select(User).where(User.username=="Beyond"));beyond.is_active=False;db.commit();sith=db.scalar(select(User).where(User.username=="Sith"));sith_id=sith.id
    assert client.patch(f"/api/v1/admin/users/{sith_id}",headers=csrf(client),json={"role":"VIEWER"}).status_code==409

def test_admin_page_requires_admin_session(client):
    logged_out=client.get("/admin",follow_redirects=False);assert logged_out.status_code==303;assert logged_out.headers["location"]=="/login"
    register(client);login(client);assert client.get("/admin",follow_redirects=False).status_code in {200,404}
    with SessionLocal() as db:user=db.scalar(select(User).where(User.username=="ordinary"));user.role="ADMIN";db.commit()
    assert client.get("/admin",follow_redirects=False).status_code in {200,404}
    assert client.get("/api/v1/admin/system").status_code==403

def test_user_data_isolation_and_owner_scoped_reset(client):
    register(client,"first","first@example.com");login(client,"first");assert client.post("/api/v1/telemetry",headers=csrf(client),json={"provider":"p","model":"m","application":"a","input_tokens":10}).status_code==201
    client.cookies.clear();register(client,"second","second@example.com");login(client,"second");assert client.get("/api/v1/overview").json()["requests"]==0
    assert client.delete("/api/v1/telemetry",headers=csrf(client)).json()["deleted"]==0
    with SessionLocal() as db:assert db.scalar(select(func.count()).select_from(TelemetryEvent))==1

def test_postgresql_schema_compiles():
    for table in Base.metadata.sorted_tables:assert "CREATE TABLE" in str(CreateTable(table).compile(dialect=postgresql.dialect()))

def test_protected_routes_require_authentication(client):
    for path in ("/api/v1/auth/me","/api/v1/profile","/api/v1/overview","/api/v1/admin/summary","/api/v1/admin/users","/api/v1/admin/audit","/api/v1/admin/system"):assert client.get(path).status_code==401
