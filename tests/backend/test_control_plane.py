from datetime import timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func,select
from apps.api.aiopt_web.auth import CSRF_COOKIE
from apps.api.aiopt_web.database import Base,SessionLocal,engine
from apps.api.aiopt_web.entitlements import enforce_limit,entitlement
from apps.api.aiopt_web.main import app
from apps.api.aiopt_web.models import Organization,OrganizationInvitation,OrganizationMember,User
from apps.api.aiopt_web.security import utcnow

PASSWORD="ValidPassword123"
@pytest.fixture(autouse=True)
def clean():Base.metadata.drop_all(engine);Base.metadata.create_all(engine);yield;Base.metadata.drop_all(engine)
@pytest.fixture
def client():
    with TestClient(app) as value:yield value
def register(client,name,email=None):
    email=email or f"{name}@example.com";assert client.post("/api/v1/auth/register",json={"display_name":name,"username":name,"email":email,"password":PASSWORD,"confirm_password":PASSWORD}).status_code==201
    assert client.post("/api/v1/auth/login",json={"identity":name,"password":PASSWORD}).status_code==200
    return {"X-CSRF-Token":client.cookies.get(CSRF_COOKIE)}

def test_registration_creates_default_active_owner_organization(client):
    register(client,"owner");data=client.get("/api/v1/admin/control/organization").json()["organization"]
    assert data["role"]=="OWNER" and data["status"]=="ACTIVE"
    with SessionLocal() as db:assert db.scalar(select(func.count()).select_from(Organization))==1;assert db.scalar(select(OrganizationMember)).role=="OWNER"

def test_organization_update_and_isolation(client):
    headers=register(client,"first");first=client.patch("/api/v1/admin/control/organization",headers=headers,json={"name":"First Org","retention_days":90});assert first.status_code==200
    with SessionLocal() as db:first_org=db.scalar(select(Organization).where(Organization.name=="First Org")).id
    client.cookies.clear();register(client,"second");assert client.get("/api/v1/admin/control/organization").json()["organization"]["id"]!=first_org;assert client.get("/api/v1/admin/control/members").json()["items"][0]["display_name"]=="second"

def test_invite_duplicate_expiry_accept_and_identity(client):
    headers=register(client,"owner")
    with SessionLocal() as db:org=db.scalar(select(Organization));org.plan_id="PROFESSIONAL";db.commit()
    payload={"email":"member@example.com","role":"ANALYST","expires_days":7};created=client.post("/api/v1/admin/control/invitations",headers=headers,json=payload);assert created.status_code==201 and created.json()["delivery"]=="NOT_CONFIGURED";invitation_id=created.json()["id"]
    assert client.post("/api/v1/admin/control/invitations",headers=headers,json=payload).status_code==409
    client.cookies.clear();member_headers=register(client,"member","member@example.com");assert client.post(f"/api/v1/admin/control/invitations/{invitation_id}/accept",headers=member_headers).status_code==200
    with SessionLocal() as db:
        invite=db.get(OrganizationInvitation,invitation_id);assert invite.accepted_at;member_id=db.scalar(select(User.id).where(User.username=="member"));assert db.scalar(select(OrganizationMember).where(OrganizationMember.organization_id==invite.organization_id,OrganizationMember.user_id==member_id))
        expired=OrganizationInvitation(organization_id=invite.organization_id,email="member@example.com",role="VIEWER",invited_by=invite.invited_by,expires_at=utcnow()-timedelta(days=1));db.add(expired);db.commit();expired_id=expired.id
    assert client.post(f"/api/v1/admin/control/invitations/{expired_id}/accept",headers=member_headers).status_code==409

def test_member_owner_protection_and_cross_org_rejection(client):
    headers=register(client,"alpha")
    with SessionLocal() as db:alpha=db.scalar(select(User).where(User.username=="alpha"));alpha_id=db.scalar(select(OrganizationMember.id).where(OrganizationMember.user_id==alpha.id))
    assert client.patch(f"/api/v1/admin/control/members/{alpha_id}",headers=headers,json={"role":"VIEWER"}).status_code==409
    client.cookies.clear();other_headers=register(client,"beta");assert client.patch(f"/api/v1/admin/control/members/{alpha_id}",headers=other_headers,json={"role":"VIEWER"}).status_code==404

def test_role_policy_and_entitlement_limits_are_centralized(client):
    headers=register(client,"viewer")
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.username=="viewer"));member=db.scalar(select(OrganizationMember).where(OrganizationMember.user_id==user.id));member.role="VIEWER";org=db.get(Organization,member.organization_id);db.commit();assert entitlement(org,"pricing_comparison");assert not entitlement(org,"forecasting")
        with pytest.raises(Exception):enforce_limit(org,"member_limit",1)
        org.plan_id="ENTERPRISE";assert enforce_limit(org,"member_limit",999_999) is None
    assert client.patch("/api/v1/admin/control/organization",headers=headers,json={"name":"Denied","retention_days":30}).status_code==403;assert client.post("/api/v1/providers/openai/connect",headers=headers,json={"credential":"secret"}).status_code==403

def test_sessions_list_no_tokens_and_revoke_others(client):
    register(client,"sessions");client.post("/api/v1/auth/login",json={"identity":"sessions","password":PASSWORD});headers={"X-CSRF-Token":client.cookies.get(CSRF_COOKIE)};listed=client.get("/api/v1/admin/control/sessions");assert listed.status_code==200 and len(listed.json()["items"])==2;assert "token" not in listed.text.casefold();assert client.delete("/api/v1/admin/control/sessions/others",headers=headers).json()["revoked"]==1

def test_audit_scope_and_platform_admin_separation(client):
    headers=register(client,"auditor");client.patch("/api/v1/admin/control/organization",headers=headers,json={"name":"Audited","retention_days":30});data=client.get("/api/v1/admin/control/audit").json()["items"];assert any(x["action"]=="organization.updated" for x in data);assert all("password" not in str(x).casefold() and "credential" not in str(x).casefold() for x in data);assert client.get("/api/v1/platform/feature-flags").status_code==403
    with SessionLocal() as db:user=db.scalar(select(User).where(User.username=="auditor"));user.role="ADMIN";user.is_platform_admin=True;db.commit()
    assert client.get("/api/v1/platform/feature-flags").status_code==200

def test_usage_and_health_are_actual(client):
    register(client,"metrics");usage=client.get("/api/v1/admin/control/usage").json();overview=client.get("/api/v1/admin/control/overview").json();assert usage["telemetry_events"]==0 and usage["imports_this_month"]==0;assert overview["metrics"]["catalog_models"]>=26;assert overview["health"]["database"]=="HEALTHY"

def test_invitation_resend_revoke_and_settings_foundations(client):
    headers=register(client,"configuration")
    with SessionLocal() as db:
        db.scalar(select(Organization)).plan_id="PROFESSIONAL";db.commit()
    created=client.post("/api/v1/admin/control/invitations",headers=headers,json={"email":"pending@example.com","role":"VIEWER","expires_days":7});invitation_id=created.json()["id"]
    assert client.post(f"/api/v1/admin/control/invitations/{invitation_id}/resend",headers=headers).json()["delivery"]=="NOT_CONFIGURED"
    assert client.delete(f"/api/v1/admin/control/invitations/{invitation_id}",headers=headers).json()["status"]=="REVOKED"
    assert client.post(f"/api/v1/admin/control/invitations/{invitation_id}/resend",headers=headers).status_code==409
    preferences={"budget_threshold":True,"worker_unhealthy":False}
    assert client.put("/api/v1/admin/control/notifications",headers=headers,json={"preferences":preferences}).json()["preferences"]==preferences
    temporary=client.put("/api/v1/admin/control/temporary-sessions",headers=headers,json={"enabled":True,"maximum_minutes":30,"maximum_requests":50,"allowed_providers":["openai"],"telemetry_retention":"SESSION_ONLY"})
    assert temporary.status_code==200 and temporary.json()["credential_retention"]=="NEVER" and temporary.json()["backend_status"]=="FOUNDATION_ONLY"
