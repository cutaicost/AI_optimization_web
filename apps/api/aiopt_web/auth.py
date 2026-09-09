from datetime import timedelta
from hashlib import sha256
import os,secrets
from fastapi import Depends, HTTPException, Request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from .config import settings
from .database import db_session
from .models import AuditEvent, LoginAttempt, OrganizationMember, RateLimitEvent, Session as UserSession, User
from .security import digest, expires, hash_password, opaque_token, utcnow, verify_password

SESSION_COOKIE="aiopt_session";CSRF_COOKIE="aiopt_csrf"

def audit(db,action,outcome="success",actor=None,resource_type="security",resource_id=None,**metadata):
    safe={k:v for k,v in metadata.items() if not any(word in k.lower() for word in ("password","secret","token","credential"))}
    organization_id=safe.pop("organization_id",None)
    if not organization_id and actor:organization_id=db.scalar(select(OrganizationMember.organization_id).where(OrganizationMember.user_id==actor,OrganizationMember.status=="ACTIVE").order_by(OrganizationMember.joined_at))
    user=db.get(User,actor) if actor else None;db.add(AuditEvent(actor_user_id=actor,actor_role=user.role if user else None,action=action,outcome=outcome,resource_type=resource_type,resource_id=resource_id,metadata_json=safe,organization_id=organization_id))

def public_user(user:User):
    return {"id":user.id,"username":user.username,"email":user.email,"display_name":user.display_name,"role":user.role,"is_active":user.is_active,"must_change_password":user.must_change_password,"organization":user.organization,"job_title":user.job_title,"preferences":user.preferences,"created_at":user.created_at,"last_login_at":user.last_login_at}
def public_user_context(db:Session,user:User):
    value=public_user(user);membership=db.scalar(select(OrganizationMember).where(OrganizationMember.user_id==user.id,OrganizationMember.status=="ACTIVE").order_by(OrganizationMember.joined_at));value["organization_role"]=membership.role if membership else None;value["organization_id"]=membership.organization_id if membership else None;value["is_platform_admin"]=bool(user.is_platform_admin);return value

def current_session(request:Request,db:Session):
    raw=request.cookies.get(SESSION_COOKIE)
    if not raw:return None
    session=db.scalar(select(UserSession).where(UserSession.token_hash==digest(raw),UserSession.revoked_at.is_(None),UserSession.expires_at>utcnow()))
    if not session or not session.user.is_active:return None
    return session

def require_user(request:Request,db:Session=Depends(db_session)):
    session=current_session(request,db)
    if not session:raise HTTPException(401,"Authentication required")
    return session.user

def require_operational_user(user:User=Depends(require_user)):
    if user.must_change_password:
        raise HTTPException(428,"Password change required")
    return user

def require_analyst(user:User=Depends(require_operational_user)):
    if user.role not in {"ANALYST","ADMIN"}:raise HTTPException(403,"Analyst access required")
    return user

def require_admin(user:User=Depends(require_operational_user)):
    if user.role!="ADMIN":raise HTTPException(403,"Administrator access required")
    return user
def require_platform_admin(user:User=Depends(require_admin)):
    if not user.is_platform_admin:raise HTTPException(403,"Platform administrator access required")
    return user

def require_csrf(request:Request,db:Session=Depends(db_session)):
    if request.method in {"GET","HEAD","OPTIONS"}:return
    session=current_session(request,db)
    if not session:raise HTTPException(401,"Authentication required")
    supplied=request.headers.get("X-CSRF-Token","")
    cookie=request.cookies.get(CSRF_COOKIE,"")
    if not supplied or not cookie or not secrets.compare_digest(supplied,cookie) or not secrets.compare_digest(digest(supplied),session.csrf_hash):raise HTTPException(403,"CSRF validation failed")

def login_limited(db:Session,identity:str):
    key=sha256(identity.casefold().encode()).hexdigest();cutoff=utcnow()-timedelta(minutes=15)
    failures=db.scalar(select(func.count()).select_from(LoginAttempt).where(LoginAttempt.identity_hash==key,LoginAttempt.attempted_at>=cutoff,LoginAttempt.successful.is_(False))) or 0
    return failures>=8,key

def enforce_rate_limit(db:Session,action:str,subject:str,limit:int,minutes:int=15):
    key=digest(subject.casefold());cutoff=utcnow()-timedelta(minutes=minutes)
    count=db.scalar(select(func.count()).select_from(RateLimitEvent).where(RateLimitEvent.action==action,RateLimitEvent.subject_hash==key,RateLimitEvent.occurred_at>=cutoff)) or 0
    if count>=limit:raise HTTPException(429,"Too many attempts. Try again later")
    db.add(RateLimitEvent(action=action,subject_hash=key));db.commit()

def create_session(db:Session,user:User,client_summary=None):
    raw=opaque_token();csrf=opaque_token();db.add(UserSession(user_id=user.id,token_hash=digest(raw),csrf_hash=digest(csrf),expires_at=expires(settings().session_ttl_seconds),client_summary=(client_summary or "Browser session")[:160]));return raw,csrf

def bootstrap_admins(db:Session):
    created=[]
    for username,variable in (("Sith","ADMIN_SITH_PASSWORD"),("Beyond","ADMIN_BEYOND_PASSWORD")):
        if db.scalar(select(User).where(func.lower(User.username)==username.casefold())):continue
        password=os.getenv(variable)
        if not password:continue
        if len(password)<12:raise RuntimeError(f"{variable} must contain at least 12 characters")
        user=User(username=username,email=f"{username.casefold()}@bootstrap.invalid",display_name=username,password_hash=hash_password(password),role="ADMIN",is_active=True,must_change_password=True,is_platform_admin=True)
        db.add(user);created.append(username)
    if created:audit(db,"admin.bootstrap",resource_type="user",accounts=created)
    db.commit();return created
