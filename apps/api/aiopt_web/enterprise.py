"""Enterprise retention and safe audit export operations."""
import csv,io,json
from datetime import timedelta
from fastapi import APIRouter,Depends,HTTPException,Query,Response
from pydantic import BaseModel
from sqlalchemy import delete,func,select
from sqlalchemy.orm import Session
from .auth import audit,require_csrf,require_platform_admin
from .database import db_session
from .models import AuditEvent,EnterpriseSetting,TelemetryEvent,User
from .security import utcnow

router=APIRouter(prefix="/api/v1/admin");POLICIES={30,90,180,365}
class RetentionIn(BaseModel):days:int|None
def cutoff(days):
    if days is not None and days not in POLICIES:raise HTTPException(422,"Retention must be 30, 90, 180, 365 days, or unlimited")
    return utcnow()-timedelta(days=days) if days else None
@router.get("/retention/preview")
def retention_preview(days:int|None=Query(None),_:User=Depends(require_platform_admin),db:Session=Depends(db_session)):
    before=cutoff(days);count=db.scalar(select(func.count()).select_from(TelemetryEvent).where(TelemetryEvent.timestamp<before)) if before else 0;return {"days":days,"unlimited":days is None,"rows_to_delete":count or 0,"cutoff":before}
@router.post("/retention",dependencies=[Depends(require_csrf)])
def retention_apply(payload:RetentionIn,admin:User=Depends(require_platform_admin),db:Session=Depends(db_session)):
    before=cutoff(payload.days);deleted=db.execute(delete(TelemetryEvent).where(TelemetryEvent.timestamp<before)).rowcount if before else 0;setting=db.get(EnterpriseSetting,"telemetry_retention")
    if not setting:setting=EnterpriseSetting(key="telemetry_retention",value_json={});db.add(setting)
    setting.value_json={"days":payload.days};setting.updated_by=admin.id;audit(db,"retention.executed",actor=admin.id,resource_type="telemetry",days=payload.days,deleted=deleted);db.commit();return {"days":payload.days,"deleted":deleted}
def audit_rows(db,limit=10_000):return db.scalars(select(AuditEvent).order_by(AuditEvent.timestamp.desc()).limit(limit)).all()
def safe(row):return {"timestamp":row.timestamp,"actor":row.actor_user_id,"role":row.actor_role,"action":row.action,"resource_type":row.resource_type,"resource_id":row.resource_id,"outcome":row.outcome,"metadata":row.metadata_json}
@router.get("/audit/export.json")
def audit_json(_:User=Depends(require_platform_admin),db:Session=Depends(db_session)):
    body=json.dumps([safe(row) for row in audit_rows(db)],default=str);return Response(body,media_type="application/json",headers={"Content-Disposition":"attachment; filename=audit.json"})
def csv_safe(value):
    text=str(value or "");return "'"+text if text.startswith(("=","+","-","@","\t","\r")) else text
@router.get("/audit/export.csv")
def audit_csv(_:User=Depends(require_platform_admin),db:Session=Depends(db_session)):
    output=io.StringIO();writer=csv.writer(output);writer.writerow(["timestamp","actor","role","action","resource_type","resource_id","outcome","metadata"])
    for row in audit_rows(db):writer.writerow([csv_safe(x) for x in (row.timestamp,row.actor_user_id,row.actor_role,row.action,row.resource_type,row.resource_id,row.outcome,json.dumps(row.metadata_json))])
    return Response(output.getvalue(),media_type="text/csv",headers={"Content-Disposition":"attachment; filename=audit.csv"})
