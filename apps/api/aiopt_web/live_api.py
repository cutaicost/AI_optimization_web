"""Owner-scoped gateway telemetry sessions and a one-way SSE feed."""
import asyncio,json
from fastapi import APIRouter,Depends,HTTPException,Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func,select
from sqlalchemy.orm import Session
from .auth import audit,require_operational_user,require_csrf
from .database import SessionLocal,db_session
from .models import LiveTelemetrySession,PricingRecord,ProviderCredential,TelemetryEvent,User
from .security import utcnow

router=APIRouter(prefix="/api/v1/live")
def active(db,user_id):return db.scalar(select(LiveTelemetrySession).where(LiveTelemetrySession.user_id==user_id,LiveTelemetrySession.status=="ACTIVE").order_by(LiveTelemetrySession.started_at.desc()))
def session_payload(row):return {"id":row.id,"provider":row.provider,"mode":row.mode,"status":row.status,"started_at":row.started_at,"stopped_at":row.stopped_at,"last_event_at":row.last_event_at,"scope_note":"Per-request data includes only calls reported through the CutAIcost gateway endpoint; the provider key alone does not reveal requests made elsewhere."}

@router.post("/start",dependencies=[Depends(require_csrf)])
def start(user:User=Depends(require_operational_user),db:Session=Depends(db_session)):
    row=active(db,user.id)
    if row:return session_payload(row)
    connection=db.scalar(select(ProviderCredential).where(ProviderCredential.user_id==user.id,ProviderCredential.validation_status=="CONNECTED"))
    if not connection:raise HTTPException(409,"Connect and validate a provider before starting live telemetry")
    row=LiveTelemetrySession(user_id=user.id,provider=connection.provider,mode="GATEWAY",status="ACTIVE");db.add(row);audit(db,"live.started",actor=user.id,resource_type="live_session",resource_id=row.id,mode="GATEWAY");db.commit();db.refresh(row);return session_payload(row)

@router.post("/stop",dependencies=[Depends(require_csrf)])
def stop(user:User=Depends(require_operational_user),db:Session=Depends(db_session)):
    row=active(db,user.id)
    if not row:raise HTTPException(404,"No active live telemetry session")
    row.status="STOPPED";row.stopped_at=utcnow();audit(db,"live.stopped",actor=user.id,resource_type="live_session",resource_id=row.id);db.commit();return session_payload(row)

@router.get("/status")
def status(user:User=Depends(require_operational_user),db:Session=Depends(db_session)):
    row=active(db,user.id) or db.scalar(select(LiveTelemetrySession).where(LiveTelemetrySession.user_id==user.id).order_by(LiveTelemetrySession.started_at.desc()))
    connection=db.scalar(select(ProviderCredential).where(ProviderCredential.user_id==user.id).order_by(ProviderCredential.updated_at.desc()))
    return {"session":session_payload(row) if row else None,"connection":{"provider":connection.provider,"status":connection.validation_status,"masked_identifier":connection.masked_identifier,"last_latency_ms":connection.last_latency_ms} if connection else None}

def event_payload(db,row):
    price=db.get(PricingRecord,row.pricing_record_id) if row.pricing_record_id else None
    meta=row.metadata_json or {};total=row.total_tokens or 0;seconds=(row.duration_ms or 0)/1000
    return {"id":row.id,"provider":row.provider,"model":row.model,"timestamp":row.timestamp,"status":meta.get("status","observed"),"input_tokens":row.input_tokens,"output_tokens":row.output_tokens,"cached_tokens":meta.get("cached_tokens"),"total_tokens":total,"estimated_cost":float(row.calculated_cost) if row.calculated_cost is not None else None,"latency_ms":row.duration_ms,"time_to_first_token_ms":meta.get("time_to_first_token_ms"),"tokens_per_second":round(total/seconds,2) if seconds>0 else None,"metric_sources":{"tokens":"observed","latency":"locally_measured","cost":"estimated" if row.calculated_cost is not None else "unknown"},"pricing":{"source":price.provenance,"effective_at":price.effective_from,"input_per_million":float(price.input_price),"output_per_million":float(price.output_price)} if price else None}

@router.get("/snapshot")
def snapshot(user:User=Depends(require_operational_user),db:Session=Depends(db_session)):
    row=active(db,user.id) or db.scalar(select(LiveTelemetrySession).where(LiveTelemetrySession.user_id==user.id).order_by(LiveTelemetrySession.started_at.desc()))
    if not row:return {"session":None,"metrics":{},"items":[]}
    events=db.scalars(select(TelemetryEvent).where(TelemetryEvent.user_id==user.id,TelemetryEvent.timestamp>=row.started_at,TelemetryEvent.provenance=="GATEWAY").order_by(TelemetryEvent.timestamp.desc()).limit(100)).all()
    spend=sum(float(x.calculated_cost or 0) for x in events if x.calculated_cost is not None);tokens=sum(x.total_tokens for x in events);errors=sum(1 for x in events if (x.metadata_json or {}).get("status") not in (None,"ok","success","observed"))
    return {"session":session_payload(row),"metrics":{"requests":len(events),"tokens":tokens,"session_spend":spend,"error_rate":errors/len(events) if events else 0,"average_latency_ms":sum(x.duration_ms for x in events)/len(events) if events else None},"items":[event_payload(db,x) for x in events]}

@router.get("/stream")
async def stream(request:Request,user:User=Depends(require_operational_user)):
    user_id=user.id;last=request.headers.get("last-event-id")
    async def generate():
        cursor=last
        while not await request.is_disconnected():
            with SessionLocal() as db:
                row=active(db,user_id)
                if not row:
                    yield "event: session\ndata: {\"status\":\"STOPPED\"}\n\n";return
                query=select(TelemetryEvent).where(TelemetryEvent.user_id==user_id,TelemetryEvent.timestamp>=row.started_at,TelemetryEvent.provenance=="GATEWAY").order_by(TelemetryEvent.created_at,TelemetryEvent.id)
                events=db.scalars(query).all();found=cursor is None
                for item in events:
                    if not found:
                        found=item.id==cursor;continue
                    cursor=item.id;yield f"id: {item.id}\nevent: telemetry\ndata: {json.dumps(event_payload(db,item),default=str)}\n\n"
            yield ": heartbeat\n\n";await asyncio.sleep(5)
    return StreamingResponse(generate(),media_type="text/event-stream",headers={"Cache-Control":"no-cache, no-transform","X-Accel-Buffering":"no","Connection":"keep-alive"})
