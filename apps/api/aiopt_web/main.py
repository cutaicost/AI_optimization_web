from contextlib import asynccontextmanager
from datetime import datetime, timezone
from time import monotonic
import secrets
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import case, delete, func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .auth import CSRF_COOKIE,SESSION_COOKIE,audit,bootstrap_admins,create_session,current_session,enforce_rate_limit,login_limited,public_user,require_admin,require_csrf,require_operational_user,require_user
from .config import VERSION,settings
from .database import Base,SessionLocal,db_session,engine
from .models import AuditEvent,ImportJob,LoginAttempt,Session as UserSession,TelemetryEvent,User
from .schemas import AdminUserUpdateIn,EventIn,LoginIn,PasswordChangeIn,ProfileIn,RegisterIn
from .security import hash_password,utcnow,verify_password

STARTED=monotonic();cfg=settings()

@asynccontextmanager
async def lifespan(_):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:bootstrap_admins(db)
    yield

app=FastAPI(title="AI Optimization Tool Web API",version=VERSION,lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=list(cfg.allowed_origins),allow_credentials=True,allow_methods=["GET","POST","PUT","PATCH","DELETE"],allow_headers=["Content-Type","X-CSRF-Token"])

@app.middleware("http")
async def security_headers(request:Request,call_next):
    response=await call_next(request)
    headers={"X-Content-Type-Options":"nosniff","X-Frame-Options":"DENY","Referrer-Policy":"strict-origin-when-cross-origin","Permissions-Policy":"camera=(), microphone=(), geolocation=()","Content-Security-Policy":"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'"}
    for key,value in headers.items():response.headers[key]=value
    return response

def set_session_cookies(response:Response,raw:str,csrf:str):
    response.set_cookie(SESSION_COOKIE,raw,max_age=cfg.session_ttl_seconds,httponly=True,secure=cfg.cookie_secure,samesite="lax",path="/")
    response.set_cookie(CSRF_COOKIE,csrf,max_age=cfg.session_ttl_seconds,httponly=False,secure=cfg.cookie_secure,samesite="lax",path="/")

@app.get("/api/v1/health")
def health(db:Session=Depends(db_session)):
    try:db.execute(text("SELECT 1"));database="connected";status="healthy"
    except Exception:database="unavailable";status="degraded"
    return {"status":status,"version":VERSION,"uptime_seconds":round(monotonic()-STARTED,2),"database":database}

@app.post("/api/v1/auth/register",status_code=201)
def register(payload:RegisterIn,request:Request,db:Session=Depends(db_session)):
    enforce_rate_limit(db,"registration",request.client.host if request.client else "unknown",10,60)
    username=payload.username.casefold();email=str(payload.email).casefold()
    if username in {"sith","beyond"}:
        raise HTTPException(409,"This username is reserved")
    if db.scalar(select(User.id).where(or_(func.lower(User.username)==username,func.lower(User.email)==email))):raise HTTPException(409,"An account with those details already exists")
    user=User(username=payload.username,email=email,display_name=payload.display_name,password_hash=hash_password(payload.password),role="USER",organization=payload.organization,job_title=payload.job_title)
    db.add(user)
    try:db.flush();audit(db,"account.registered",actor=user.id,resource_type="user",resource_id=user.id);db.commit()
    except IntegrityError:db.rollback();raise HTTPException(409,"An account with those details already exists")
    return {"user":public_user(user)}

@app.post("/api/v1/auth/login")
def login(payload:LoginIn,response:Response,db:Session=Depends(db_session)):
    limited,key=login_limited(db,payload.identity)
    if limited:raise HTTPException(429,"Sign-in temporarily unavailable. Try again later")
    user=db.scalar(select(User).where(or_(func.lower(User.username)==payload.identity.casefold(),func.lower(User.email)==payload.identity.casefold())))
    valid=bool(user and verify_password(user.password_hash,payload.password))
    db.add(LoginAttempt(identity_hash=key,successful=valid))
    if not valid:
        audit(db,"authentication.login",outcome="failure");db.commit();raise HTTPException(401,"Invalid username or password")
    if not user.is_active:
        audit(db,"authentication.login",outcome="disabled",actor=user.id);db.commit();raise HTTPException(403,"This account is disabled")
    db.execute(delete(UserSession).where(UserSession.user_id==user.id,UserSession.revoked_at.is_(None)))
    raw,csrf=create_session(db,user);user.last_login_at=utcnow();audit(db,"authentication.login",actor=user.id);db.commit();set_session_cookies(response,raw,csrf)
    return {"user":public_user(user)}

@app.post("/api/v1/auth/logout",dependencies=[Depends(require_csrf)])
def logout(request:Request,response:Response,db:Session=Depends(db_session)):
    session=current_session(request,db)
    if session:session.revoked_at=utcnow();audit(db,"authentication.logout",actor=session.user_id);db.commit()
    response.delete_cookie(SESSION_COOKIE,path="/");response.delete_cookie(CSRF_COOKIE,path="/");return {"logged_out":True}

@app.get("/api/v1/auth/me")
def me(user:User=Depends(require_user)):return {"user":public_user(user)}

@app.post("/api/v1/auth/change-password",dependencies=[Depends(require_csrf)])
def change_password(payload:PasswordChangeIn,user:User=Depends(require_user),db:Session=Depends(db_session)):
    enforce_rate_limit(db,"password_change",user.id,8,15)
    if not verify_password(user.password_hash,payload.current_password):raise HTTPException(400,"Current password is incorrect")
    user.password_hash=hash_password(payload.new_password);user.must_change_password=False
    db.execute(delete(UserSession).where(UserSession.user_id==user.id));audit(db,"account.password_changed",actor=user.id,resource_type="user",resource_id=user.id);db.commit();return {"changed":True,"reauthentication_required":True}

@app.get("/api/v1/profile")
def get_profile(user:User=Depends(require_user)):return {"user":public_user(user)}

@app.patch("/api/v1/profile",dependencies=[Depends(require_csrf)])
@app.put("/api/v1/profile",dependencies=[Depends(require_csrf)],include_in_schema=False)
def update_profile(payload:ProfileIn,user:User=Depends(require_user),db:Session=Depends(db_session)):
    email=str(payload.email).casefold();existing=db.scalar(select(User.id).where(func.lower(User.email)==email,User.id!=user.id))
    if existing:raise HTTPException(409,"Email is already in use")
    user.display_name=payload.display_name;user.email=email;user.organization=payload.organization;user.job_title=payload.job_title;user.preferences=payload.preferences
    audit(db,"profile.updated",actor=user.id,resource_type="user",resource_id=user.id);db.commit();return {"user":public_user(user)}

@app.get("/api/v1/overview")
def overview(user:User=Depends(require_operational_user),db:Session=Depends(db_session)):
    owner=TelemetryEvent.user_id==user.id
    row=db.execute(select(func.count(),func.coalesce(func.sum(TelemetryEvent.total_tokens),0),func.coalesce(func.sum(TelemetryEvent.estimated_cost),0),func.coalesce(func.avg(TelemetryEvent.duration_ms),0)).where(owner)).one()
    models=db.execute(select(TelemetryEvent.model,func.count()).where(owner).group_by(TelemetryEvent.model).order_by(func.count().desc()).limit(5)).all()
    return {"requests":row[0],"tokens":row[1],"spend":float(row[2]),"latency_ms":float(row[3]),"models":[{"name":name,"requests":count} for name,count in models]}

@app.post("/api/v1/telemetry",status_code=201,dependencies=[Depends(require_csrf)])
def ingest(payload:EventIn,user:User=Depends(require_operational_user),db:Session=Depends(db_session)):
    row=TelemetryEvent(user_id=user.id,provider=payload.provider,model=payload.model,application=payload.application,input_tokens=payload.input_tokens,output_tokens=payload.output_tokens,total_tokens=payload.input_tokens+payload.output_tokens,duration_ms=payload.duration_ms,estimated_cost=payload.estimated_cost,metadata_json=payload.metadata);db.add(row);db.commit();return {"id":row.id}

@app.delete("/api/v1/telemetry",dependencies=[Depends(require_csrf)])
def clear_telemetry(user:User=Depends(require_operational_user),db:Session=Depends(db_session)):
    count=db.execute(delete(TelemetryEvent).where(TelemetryEvent.user_id==user.id)).rowcount;audit(db,"telemetry.cleared",actor=user.id,resource_type="telemetry",records=count);db.commit();return {"deleted":count}

@app.get("/api/v1/admin/summary")
def admin_summary(_:User=Depends(require_admin),db:Session=Depends(db_session)):
    total=db.scalar(select(func.count()).select_from(User)) or 0;active=db.scalar(select(func.count()).select_from(User).where(User.is_active.is_(True))) or 0
    admins=db.scalar(select(func.count()).select_from(User).where(User.role=="ADMIN")) or 0
    recent=db.scalars(select(AuditEvent).order_by(AuditEvent.timestamp.desc()).limit(5)).all()
    return {"users":{"total":total,"active":active,"disabled":total-active,"admins":admins},"telemetry":db.scalar(select(func.count()).select_from(TelemetryEvent)) or 0,"recent_imports":db.scalar(select(func.count()).select_from(ImportJob)) or 0,"audit_events":db.scalar(select(func.count()).select_from(AuditEvent)) or 0,"recent_audit":[{"timestamp":r.timestamp,"action":r.action,"outcome":r.outcome} for r in recent],"health":"healthy","version":VERSION}

@app.get("/api/v1/admin/users")
def admin_users(q:str="",limit:int=Query(50,ge=1,le=200),offset:int=Query(0,ge=0),_:User=Depends(require_admin),db:Session=Depends(db_session)):
    query=select(User)
    if q:query=query.where(or_(User.username.ilike(f"%{q}%"),User.email.ilike(f"%{q}%"),User.display_name.ilike(f"%{q}%")))
    rows=db.scalars(query.order_by(User.created_at.desc()).offset(offset).limit(limit+1)).all();return {"items":[public_user(row) for row in rows[:limit]],"limit":limit,"offset":offset,"has_more":len(rows)>limit}

@app.get("/api/v1/admin/users/{user_id}")
def admin_user(user_id:str,_:User=Depends(require_admin),db:Session=Depends(db_session)):
    target=db.get(User,user_id)
    if not target:raise HTTPException(404,"User not found")
    return {"user":public_user(target)}

@app.patch("/api/v1/admin/users/{user_id}",dependencies=[Depends(require_csrf)])
def admin_update_user(user_id:str,payload:AdminUserUpdateIn,admin:User=Depends(require_admin),db:Session=Depends(db_session)):
    target=db.get(User,user_id)
    if not target:raise HTTPException(404,"User not found")
    removing_admin=target.role=="ADMIN" and ((payload.role and payload.role!="ADMIN") or payload.is_active is False)
    if removing_admin:
        remaining=db.scalar(select(func.count()).select_from(User).where(User.role=="ADMIN",User.is_active.is_(True),User.id!=target.id)) or 0
        if remaining<1:raise HTTPException(409,"Cannot disable or demote the final active administrator")
    if payload.role is not None:target.role=payload.role
    if payload.is_active is not None:target.is_active=payload.is_active
    if not target.is_active:db.execute(delete(UserSession).where(UserSession.user_id==target.id))
    audit(db,"admin.user_updated",actor=admin.id,resource_type="user",resource_id=target.id,role=target.role,is_active=target.is_active);db.commit();return {"user":public_user(target)}

@app.get("/api/v1/admin/audit")
def admin_audit(q:str="",action:str="",outcome:str="",limit:int=Query(100,ge=1,le=500),offset:int=Query(0,ge=0),_:User=Depends(require_admin),db:Session=Depends(db_session)):
    query=select(AuditEvent)
    if q:query=query.where(or_(AuditEvent.action.ilike(f"%{q}%"),AuditEvent.resource_type.ilike(f"%{q}%"),AuditEvent.resource_id.ilike(f"%{q}%")))
    if action:query=query.where(AuditEvent.action==action)
    if outcome:query=query.where(AuditEvent.outcome==outcome)
    rows=db.scalars(query.order_by(AuditEvent.timestamp.desc()).offset(offset).limit(limit+1)).all();return {"items":[{"id":r.id,"timestamp":r.timestamp,"actor_user_id":r.actor_user_id,"action":r.action,"outcome":r.outcome,"resource_type":r.resource_type,"resource_id":r.resource_id,"metadata":r.metadata_json} for r in rows[:limit]],"limit":limit,"offset":offset,"has_more":len(rows)>limit}

@app.get("/api/v1/admin/system")
def admin_system(_:User=Depends(require_admin),db:Session=Depends(db_session)):
    db.execute(text("SELECT 1"))
    try:migration=db.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none() or "unversioned"
    except Exception:migration="unversioned"
    return {"application_version":VERSION,"api_version":"v1","database":"connected","uptime_seconds":round(monotonic()-STARTED,2),"user_count":db.scalar(select(func.count()).select_from(User)) or 0,"migration":migration,"environment":cfg.environment}
