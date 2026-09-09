import json,os,time
import jwt,pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import select
from apps.api.aiopt_web.auth import CSRF_COOKIE,SESSION_COOKIE
from apps.api.aiopt_web.database import Base,SessionLocal,engine
from apps.api.aiopt_web.main import app
from apps.api.aiopt_web.models import Session,User
from apps.api.aiopt_web.oidc import mapped_role,validate_id_token
from apps.api.aiopt_web.security import digest,hash_password,opaque_token,utcnow

ISSUER="https://identity.example.test";AUDIENCE="tokenscope"
@pytest.fixture(autouse=True)
def oidc_config(monkeypatch):
    monkeypatch.setenv("OIDC_ISSUER",ISSUER);monkeypatch.setenv("OIDC_CLIENT_ID",AUDIENCE);monkeypatch.setenv("OIDC_ROLE_CLAIM","realm.roles");monkeypatch.setenv("OIDC_ROLE_MAP","readers=VIEWER,operators=ANALYST,admins=ADMIN");Base.metadata.drop_all(engine);Base.metadata.create_all(engine);yield;Base.metadata.drop_all(engine)
@pytest.fixture
def client():
    with TestClient(app) as value:yield value
@pytest.fixture
def signing():
    private=rsa.generate_private_key(public_exponent=65537,key_size=2048);jwk=json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private.public_key()));jwk["kid"]="test-key";return private,{"keys":[jwk]}
def token(private,**overrides):
    now=int(time.time());claims={"iss":ISSUER,"aud":AUDIENCE,"sub":"subject-1","iat":now,"exp":now+300,"nonce":"nonce","realm":{"roles":["operators"]}};claims.update(overrides);return jwt.encode(claims,private,algorithm="RS256",headers={"kid":"test-key"})
def test_oidc_signature_issuer_audience_expiration_nonce_and_roles(signing):
    private,jwks=signing;document={"issuer":ISSUER};assert validate_id_token(token(private),document,jwks,"nonce")["sub"]=="subject-1"
    other=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    for invalid in (token(other),token(private,iss="https://wrong"),token(private,aud="wrong"),token(private,exp=int(time.time())-1),token(private,nonce="wrong")):
        with pytest.raises(jwt.PyJWTError):validate_id_token(invalid,document,jwks,"nonce")
    with pytest.raises(jwt.PyJWTError):validate_id_token("",document,jwks,"nonce")
    assert mapped_role({"realm":{"roles":["readers"]}})=="VIEWER";assert mapped_role({"realm":{"roles":["operators"]}})=="ANALYST";assert mapped_role({"realm":{"roles":["admins"]}})=="ADMIN";assert mapped_role({})=="VIEWER"
def authenticate(client,role):
    with SessionLocal() as db:
        user=User(username=role.lower(),email=f"{role.lower()}@example.com",display_name=role,password_hash=hash_password(opaque_token()),role=role);db.add(user);db.flush();raw=opaque_token();csrf=opaque_token();db.add(Session(user_id=user.id,token_hash=digest(raw),csrf_hash=digest(csrf),expires_at=utcnow().replace(year=utcnow().year+1)));db.commit()
    client.cookies.set(SESSION_COOKIE,raw);client.cookies.set(CSRF_COOKIE,csrf);return {"X-CSRF-Token":csrf}
def test_backend_enforces_viewer_analyst_administrator_permissions(client):
    headers=authenticate(client,"VIEWER");assert client.get("/api/v1/overview").status_code==200;assert client.post("/api/v1/import/start",headers=headers,json={"filename":"x.csv","file_size":1,"format":"csv"}).status_code==403;client.cookies.clear()
    headers=authenticate(client,"ANALYST");assert client.post("/api/v1/import/start",headers=headers,json={"filename":"x.csv","file_size":1,"format":"csv"}).status_code==201;assert client.get("/api/v1/admin/system").status_code==403;assert client.post("/api/v1/integrations",headers=headers,json={"name":"x","kind":"generic"}).status_code==403;client.cookies.clear()
    headers=authenticate(client,"ADMIN");assert client.get("/api/v1/admin/system").status_code==403;assert client.post("/api/v1/integrations",headers=headers,json={"name":"x","kind":"generic"}).status_code==201
