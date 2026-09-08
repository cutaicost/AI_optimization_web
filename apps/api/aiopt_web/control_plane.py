"""Organization-scoped SaaS administration APIs."""
from datetime import datetime,timedelta
from fastapi import APIRouter,Depends,HTTPException,Query,Request
from pydantic import BaseModel,ConfigDict,EmailStr,Field
from sqlalchemy import delete,func,or_,select
from sqlalchemy.orm import Session
from .auth import SESSION_COOKIE,audit,current_session,require_csrf,require_operational_user,require_platform_admin
from .database import db_session
from .entitlements import PLANS,OrganizationContext,enforce_limit,organization_context,plan_summary,require_permission
from .models import AuditEvent,Budget,FeatureFlag,ForecastRun,ImportJob,Integration,NotificationPreference,Organization,OrganizationInvitation,OrganizationMember,PriceOverride,ProviderCredential,ScenarioRun,Session as UserSession,TelemetryEvent,User,WorkerInstance
from .multi_provider_catalog import CATALOG_ENTRIES
from .security import digest,utcnow

router=APIRouter(prefix="/api/v1/admin/control")
platform_router=APIRouter(prefix="/api/v1/platform",dependencies=[Depends(require_platform_admin)])
class Strict(BaseModel):model_config=ConfigDict(extra="forbid",str_strip_whitespace=True)
class OrganizationIn(Strict):name:str=Field(min_length=1,max_length=120);retention_days:int|None=Field(None,ge=7,le=3650)
class InvitationIn(Strict):email:EmailStr;role:str=Field(pattern="^(ADMIN|ANALYST|VIEWER)$");expires_days:int=Field(7,ge=1,le=30)
class RoleIn(Strict):role:str=Field(pattern="^(ADMIN|ANALYST|VIEWER)$")
class PreferencesIn(Strict):preferences:dict[str,bool]
class TemporarySessionsIn(Strict):enabled:bool=False;maximum_minutes:int=Field(30,ge=5,le=240);maximum_requests:int=Field(100,ge=1,le=10000);allowed_providers:list[str]=Field(default_factory=list,max_length=8);telemetry_retention:str=Field("SESSION_ONLY",pattern="^(SESSION_ONLY|ORGANIZATION_POLICY)$")

def member_ids(db,org_id):return list(db.scalars(select(OrganizationMember.user_id).where(OrganizationMember.organization_id==org_id,OrganizationMember.status=="ACTIVE")).all())
def invitation_status(row):
    if row.revoked_at:return "REVOKED"
    if row.accepted_at:return "ACCEPTED"
    if row.expires_at.replace(tzinfo=row.expires_at.tzinfo or utcnow().tzinfo)<=utcnow():return "EXPIRED"
    return "INVITED"
def org_public(context):return {"id":context.organization.id,"name":context.organization.name,"slug":context.organization.slug,"status":context.organization.status,"role":context.membership.role,"created_at":context.organization.created_at,"settings":context.organization.settings}

@router.get("/overview")
def overview(context:OrganizationContext=Depends(organization_context),db:Session=Depends(db_session)):
    ids=member_ids(db,context.organization.id);limits=plan_summary(context.organization);workers=db.scalars(select(WorkerInstance)).all();cutoff=utcnow()-timedelta(seconds=90);active_imports=db.scalar(select(func.count()).select_from(ImportJob).where(ImportJob.user_id.in_(ids),ImportJob.status.in_(["QUEUED","PREPARING","IMPORTING","CANCELLING"]))) or 0
    return {"organization":org_public(context),"plan":limits,"metrics":{"members":len(ids),"providers":db.scalar(select(func.count()).select_from(ProviderCredential).where(ProviderCredential.user_id.in_(ids))) or 0,"catalog_models":len(CATALOG_ENTRIES),"telemetry_events":db.scalar(select(func.count()).select_from(TelemetryEvent).where(TelemetryEvent.user_id.in_(ids))) or 0,"active_imports":active_imports},"health":{"import_worker":"HEALTHY" if any((x.last_heartbeat_at.replace(tzinfo=x.last_heartbeat_at.tzinfo or utcnow().tzinfo)>=cutoff and x.status!="OFFLINE") for x in workers) else "DEGRADED" if active_imports else "UNAVAILABLE","pricing_catalog":"HEALTHY","api":"HEALTHY","database":"HEALTHY"}}

@router.get("/organization")
def organization(context:OrganizationContext=Depends(organization_context)):return {"organization":org_public(context)}
@router.patch("/organization",dependencies=[Depends(require_csrf)])
def update_organization(payload:OrganizationIn,context:OrganizationContext=Depends(require_permission("organization.manage")),db:Session=Depends(db_session)):
    context.organization.name=payload.name
    if payload.retention_days is not None:context.organization.settings={**(context.organization.settings or {}),"retention_days":payload.retention_days}
    audit(db,"organization.updated",actor=context.user.id,resource_type="organization",resource_id=context.organization.id,organization_id=context.organization.id);db.commit();return {"organization":org_public(context)}

@router.get("/members")
def members(context:OrganizationContext=Depends(organization_context),db:Session=Depends(db_session)):
    rows=db.execute(select(OrganizationMember,User).join(User,User.id==OrganizationMember.user_id).where(OrganizationMember.organization_id==context.organization.id).order_by(OrganizationMember.joined_at)).all();invites=db.scalars(select(OrganizationInvitation).where(OrganizationInvitation.organization_id==context.organization.id).order_by(OrganizationInvitation.created_at.desc())).all()
    return {"items":[{"id":m.id,"user_id":u.id,"display_name":u.display_name,"email":u.email,"role":m.role,"status":m.status,"joined_at":m.joined_at,"last_active_at":u.last_login_at} for m,u in rows],"invitations":[{"id":x.id,"email":x.email,"role":x.role,"status":invitation_status(x),"created_at":x.created_at,"expires_at":x.expires_at,"last_sent_at":x.last_sent_at} for x in invites]}
@router.post("/invitations",status_code=201,dependencies=[Depends(require_csrf)])
def invite(payload:InvitationIn,context:OrganizationContext=Depends(require_permission("members.manage")),db:Session=Depends(db_session)):
    email=str(payload.email).casefold();active=db.scalar(select(OrganizationInvitation).where(OrganizationInvitation.organization_id==context.organization.id,func.lower(OrganizationInvitation.email)==email,OrganizationInvitation.accepted_at.is_(None),OrganizationInvitation.revoked_at.is_(None),OrganizationInvitation.expires_at>utcnow()))
    if active:raise HTTPException(409,"An active invitation already exists")
    members=db.scalar(select(func.count()).select_from(OrganizationMember).where(OrganizationMember.organization_id==context.organization.id,OrganizationMember.status=="ACTIVE")) or 0;enforce_limit(context.organization,"member_limit",members)
    row=OrganizationInvitation(organization_id=context.organization.id,email=email,role=payload.role,invited_by=context.user.id,expires_at=utcnow()+timedelta(days=payload.expires_days));db.add(row);db.flush();audit(db,"member.invited",actor=context.user.id,resource_type="invitation",resource_id=row.id,organization_id=context.organization.id,email_domain=email.rsplit("@",1)[-1],role=payload.role,delivery="NOT_CONFIGURED");db.commit();return {"id":row.id,"status":"INVITED","delivery":"NOT_CONFIGURED"}
@router.post("/invitations/{invitation_id}/resend",dependencies=[Depends(require_csrf)])
def resend(invitation_id:str,context:OrganizationContext=Depends(require_permission("members.manage")),db:Session=Depends(db_session)):
    row=db.scalar(select(OrganizationInvitation).where(OrganizationInvitation.id==invitation_id,OrganizationInvitation.organization_id==context.organization.id));
    if not row or invitation_status(row)!="INVITED":raise HTTPException(409,"Invitation is not active")
    row.last_sent_at=utcnow();audit(db,"member.invitation_resent",actor=context.user.id,resource_type="invitation",resource_id=row.id,organization_id=context.organization.id,delivery="NOT_CONFIGURED");db.commit();return {"status":"INVITED","delivery":"NOT_CONFIGURED"}
@router.delete("/invitations/{invitation_id}",dependencies=[Depends(require_csrf)])
def revoke(invitation_id:str,context:OrganizationContext=Depends(require_permission("members.manage")),db:Session=Depends(db_session)):
    row=db.scalar(select(OrganizationInvitation).where(OrganizationInvitation.id==invitation_id,OrganizationInvitation.organization_id==context.organization.id));
    if not row:raise HTTPException(404,"Invitation not found")
    if invitation_status(row)!="INVITED":raise HTTPException(409,"Invitation is not active")
    row.revoked_at=utcnow();audit(db,"member.invitation_revoked",actor=context.user.id,resource_type="invitation",resource_id=row.id,organization_id=context.organization.id);db.commit();return {"status":"REVOKED"}
@router.post("/invitations/{invitation_id}/accept",dependencies=[Depends(require_csrf)])
def accept(invitation_id:str,user:User=Depends(require_operational_user),db:Session=Depends(db_session)):
    row=db.get(OrganizationInvitation,invitation_id)
    if not row:raise HTTPException(404,"Invitation not found")
    if invitation_status(row)!="INVITED":raise HTTPException(409,"Invitation is invalid or expired")
    if row.email.casefold()!=user.email.casefold():raise HTTPException(403,"Invitation identity does not match")
    existing=db.scalar(select(OrganizationMember).where(OrganizationMember.organization_id==row.organization_id,OrganizationMember.user_id==user.id))
    if existing:existing.status="ACTIVE";existing.role=row.role;existing.joined_at=utcnow()
    else:db.add(OrganizationMember(organization_id=row.organization_id,user_id=user.id,role=row.role))
    row.accepted_at=utcnow();audit(db,"member.joined",actor=user.id,resource_type="organization",resource_id=row.organization_id,organization_id=row.organization_id,role=row.role);db.commit();return {"status":"ACCEPTED"}
@router.patch("/members/{membership_id}",dependencies=[Depends(require_csrf)])
def change_role(membership_id:str,payload:RoleIn,context:OrganizationContext=Depends(require_permission("members.manage")),db:Session=Depends(db_session)):
    row=db.scalar(select(OrganizationMember).where(OrganizationMember.id==membership_id,OrganizationMember.organization_id==context.organization.id))
    if not row:raise HTTPException(404,"Member not found")
    if row.role=="OWNER":raise HTTPException(409,"The organization owner cannot be demoted")
    row.role=payload.role;audit(db,"member.role_changed",actor=context.user.id,resource_type="membership",resource_id=row.id,organization_id=context.organization.id,role=row.role);db.commit();return {"role":row.role}
@router.delete("/members/{membership_id}",dependencies=[Depends(require_csrf)])
def remove_member(membership_id:str,context:OrganizationContext=Depends(require_permission("members.manage")),db:Session=Depends(db_session)):
    row=db.scalar(select(OrganizationMember).where(OrganizationMember.id==membership_id,OrganizationMember.organization_id==context.organization.id))
    if not row:raise HTTPException(404,"Member not found")
    if row.role=="OWNER":raise HTTPException(409,"The organization owner cannot be removed")
    row.status="SUSPENDED";db.execute(delete(UserSession).where(UserSession.user_id==row.user_id));audit(db,"member.removed",actor=context.user.id,resource_type="membership",resource_id=row.id,organization_id=context.organization.id);db.commit();return {"status":"SUSPENDED"}

@router.get("/membership")
def membership(context:OrganizationContext=Depends(organization_context),db:Session=Depends(db_session)):
    ids=member_ids(db,context.organization.id);plan=plan_summary(context.organization);start=utcnow().replace(day=1,hour=0,minute=0,second=0,microsecond=0);usage={"members":len(ids),"providers":db.scalar(select(func.count()).select_from(ProviderCredential).where(ProviderCredential.user_id.in_(ids))) or 0,"telemetry_events":db.scalar(select(func.count()).select_from(TelemetryEvent).where(TelemetryEvent.user_id.in_(ids))) or 0,"monthly_imports":db.scalar(select(func.count()).select_from(ImportJob).where(ImportJob.user_id.in_(ids),ImportJob.created_at>=start)) or 0};return {"plan":plan,"usage":usage}
@router.get("/usage")
def usage(context:OrganizationContext=Depends(organization_context),db:Session=Depends(db_session)):
    ids=member_ids(db,context.organization.id);start=utcnow().replace(day=1,hour=0,minute=0,second=0,microsecond=0);return {"telemetry_events":db.scalar(select(func.count()).select_from(TelemetryEvent).where(TelemetryEvent.user_id.in_(ids))) or 0,"imports_this_month":db.scalar(select(func.count()).select_from(ImportJob).where(ImportJob.user_id.in_(ids),ImportJob.created_at>=start)) or 0,"total_imported_rows":db.scalar(select(func.coalesce(func.sum(ImportJob.rows_imported),0)).where(ImportJob.user_id.in_(ids))) or 0,"provider_connections":db.scalar(select(func.count()).select_from(ProviderCredential).where(ProviderCredential.user_id.in_(ids))) or 0,"members":len(ids),"forecast_runs":db.scalar(select(func.count()).select_from(ForecastRun).where(ForecastRun.user_id.in_(ids))) or 0,"simulation_runs":db.scalar(select(func.count()).select_from(ScenarioRun).where(ScenarioRun.user_id.in_(ids))) or 0,"limits":plan_summary(context.organization)["limits"]}
@router.get("/system")
def system(context:OrganizationContext=Depends(require_permission("configuration.manage")),db:Session=Depends(db_session)):
    ids=member_ids(db,context.organization.id);active_states=["QUEUED","PREPARING","IMPORTING","CANCELLING"];queued=db.scalar(select(func.count()).select_from(ImportJob).where(ImportJob.user_id.in_(ids),ImportJob.status=="QUEUED")) or 0;running=db.scalar(select(func.count()).select_from(ImportJob).where(ImportJob.user_id.in_(ids),ImportJob.status.in_(active_states[1:]))) or 0;oldest=db.scalar(select(func.min(ImportJob.updated_at)).where(ImportJob.user_id.in_(ids),ImportJob.status.in_(active_states)));cutoff=utcnow()-timedelta(hours=24);failed=db.scalar(select(func.count()).select_from(ImportJob).where(ImportJob.user_id.in_(ids),ImportJob.status=="FAILED",ImportJob.updated_at>=cutoff)) or 0;worker_cutoff=utcnow()-timedelta(seconds=90);workers=db.scalars(select(WorkerInstance).order_by(WorkerInstance.last_heartbeat_at.desc())).all();instances=[{"worker_id":x.worker_id,"status":"OFFLINE" if x.last_heartbeat_at.replace(tzinfo=x.last_heartbeat_at.tzinfo or utcnow().tzinfo)<worker_cutoff else x.status,"current_job_id":x.current_job_id,"last_heartbeat_at":x.last_heartbeat_at} for x in workers];worker_health="HEALTHY" if any(x["status"]!="OFFLINE" for x in instances) else "DEGRADED" if queued else "UNAVAILABLE";return {"health":{"api":"HEALTHY","database":"HEALTHY","import_worker":worker_health,"telemetry_pipeline":"DEGRADED" if queued and worker_health!="HEALTHY" else "HEALTHY","pricing_catalog":"HEALTHY","storage":"HEALTHY","gateway":"UNAVAILABLE"},"worker":{"queued":queued,"running":running,"oldest_job_at":oldest,"instances":instances},"imports":{"failed_24h":failed},"pricing":{"providers":len({x.provider for x in CATALOG_ENTRIES}),"models":len(CATALOG_ENTRIES)}}

@router.get("/sessions")
def sessions(request:Request,context:OrganizationContext=Depends(organization_context),db:Session=Depends(db_session)):
    current=current_session(request,db);rows=db.scalars(select(UserSession).where(UserSession.user_id==context.user.id,UserSession.revoked_at.is_(None),UserSession.expires_at>utcnow()).order_by(UserSession.created_at.desc())).all();return {"items":[{"id":x.id,"created_at":x.created_at,"last_active_at":x.last_active_at,"expires_at":x.expires_at,"client_summary":x.client_summary or "Browser session","current":bool(current and current.id==x.id)} for x in rows]}
@router.delete("/sessions/others",dependencies=[Depends(require_csrf)])
def sign_out_others(request:Request,context:OrganizationContext=Depends(organization_context),db:Session=Depends(db_session)):
    current=current_session(request,db);rows=db.scalars(select(UserSession).where(UserSession.user_id==context.user.id,UserSession.revoked_at.is_(None),UserSession.id!=current.id)).all() if current else []
    for row in rows:row.revoked_at=utcnow()
    audit(db,"security.other_sessions_revoked",actor=context.user.id,resource_type="session",organization_id=context.organization.id,count=len(rows));db.commit();return {"revoked":len(rows)}

@router.get("/notifications")
def notifications(context:OrganizationContext=Depends(organization_context),db:Session=Depends(db_session)):
    row=db.scalar(select(NotificationPreference).where(NotificationPreference.organization_id==context.organization.id,NotificationPreference.user_id==context.user.id));return {"channel":"IN_APP","preferences":row.preferences if row else {}}
@router.put("/notifications",dependencies=[Depends(require_csrf)])
def set_notifications(payload:PreferencesIn,context:OrganizationContext=Depends(organization_context),db:Session=Depends(db_session)):
    allowed={"budget_threshold","projected_budget","provider_invalid","import_failed","worker_unhealthy","pricing_stale","anomaly_detected","member_activity","critical_configuration"}
    if set(payload.preferences)-allowed:raise HTTPException(422,"Unknown notification preference")
    row=db.scalar(select(NotificationPreference).where(NotificationPreference.organization_id==context.organization.id,NotificationPreference.user_id==context.user.id)) or NotificationPreference(organization_id=context.organization.id,user_id=context.user.id);db.add(row);row.preferences=payload.preferences;audit(db,"notification.preferences_changed",actor=context.user.id,resource_type="notification",organization_id=context.organization.id);db.commit();return {"channel":"IN_APP","preferences":row.preferences}
@router.put("/temporary-sessions",dependencies=[Depends(require_csrf)])
def temporary_sessions(payload:TemporarySessionsIn,context:OrganizationContext=Depends(require_permission("security.manage")),db:Session=Depends(db_session)):
    valid={x.provider for x in CATALOG_ENTRIES}
    if set(payload.allowed_providers)-valid:raise HTTPException(422,"Unknown provider")
    context.organization.settings={**(context.organization.settings or {}),"temporary_provider_sessions":payload.model_dump(),"credential_retention":"NEVER"};audit(db,"security.temporary_sessions_changed",actor=context.user.id,resource_type="organization",resource_id=context.organization.id,organization_id=context.organization.id,enabled=payload.enabled);db.commit();return {"temporary_provider_sessions":context.organization.settings["temporary_provider_sessions"],"credential_retention":"NEVER","backend_status":"FOUNDATION_ONLY"}

@router.get("/audit")
def org_audit(q:str="",action:str="",outcome:str="",actor:str="",date_from:datetime|None=None,date_to:datetime|None=None,limit:int=Query(100,ge=1,le=500),context:OrganizationContext=Depends(require_permission("configuration.manage")),db:Session=Depends(db_session)):
    query=select(AuditEvent).where(AuditEvent.organization_id==context.organization.id)
    if q:query=query.where(or_(AuditEvent.action.ilike(f"%{q}%"),AuditEvent.resource_type.ilike(f"%{q}%"),AuditEvent.resource_id.ilike(f"%{q}%")))
    if action:query=query.where(AuditEvent.action==action)
    if outcome:query=query.where(AuditEvent.outcome==outcome)
    if actor:query=query.where(AuditEvent.actor_user_id==actor)
    if date_from:query=query.where(AuditEvent.timestamp>=date_from)
    if date_to:query=query.where(AuditEvent.timestamp<=date_to)
    rows=db.scalars(query.order_by(AuditEvent.timestamp.desc()).limit(limit)).all();return {"items":[{"id":x.id,"timestamp":x.timestamp,"actor_user_id":x.actor_user_id,"action":x.action,"outcome":x.outcome,"resource_type":x.resource_type,"resource_id":x.resource_id,"metadata":x.metadata_json} for x in rows]}

@platform_router.get("/organizations")
def platform_organizations(db:Session=Depends(db_session)):
    rows=db.scalars(select(Organization).order_by(Organization.created_at.desc()).limit(200)).all();return {"items":[{"id":x.id,"name":x.name,"status":x.status,"plan_id":x.plan_id,"created_at":x.created_at} for x in rows]}
@platform_router.get("/feature-flags")
def platform_flags(db:Session=Depends(db_session)):
    configured={x.key:x for x in db.scalars(select(FeatureFlag)).all()};definitions={"new_scope_ui":"New Scope UI","live_provider_feed":"Live Provider Feed","policy_routing":"Policy Routing","new_forecast_engine":"New Forecast Engine","gemini_live_telemetry":"Gemini Live Telemetry","public_provider_sessions":"Public Provider Sessions"};return {"items":[{"key":key,"description":description,"state":configured[key].state if key in configured else "OFF"} for key,description in definitions.items()]}
