"""Admin-controlled provider credentials, sanitized public telemetry, and public access intake."""
from dataclasses import asdict
from fastapi import APIRouter,Depends,HTTPException,Request
from pydantic import BaseModel,ConfigDict,EmailStr,Field,SecretStr,field_validator
from sqlalchemy import delete,select
from sqlalchemy.orm import Session
from .auth import audit,enforce_rate_limit,require_operational_user,require_csrf
from .database import db_session
from .models import LiveTelemetrySession,PricingRecord,ProviderCredential,ProviderModel,User
from .provider_credentials import CredentialConfigurationError,decrypt_credential,encrypt_credential
from .providers import ProviderError,provider_adapter
from .security import utcnow
from .entitlements import require_permission

router=APIRouter(prefix="/api/v1/providers",dependencies=[Depends(require_permission("providers.manage"))]);public_router=APIRouter()
class ConnectIn(BaseModel):model_config=ConfigDict(extra="forbid");credential:SecretStr
class PublicRequestIn(BaseModel):
    model_config=ConfigDict(extra="forbid",str_strip_whitespace=True)
    request_type:str=Field(pattern=r"^(DEMO|ACCESS)$")
    name:str=Field(min_length=1,max_length=100)
    email:EmailStr
    company:str|None=Field(None,max_length=120)
    role:str|None=Field(None,max_length=120)
    ai_spend_range:str|None=Field(None,max_length=80)
    preferred_contact:str|None=Field(None,max_length=80)
    providers:str|None=Field(None,max_length=300)
    goals:str=Field(min_length=1,max_length=1500)
    website:str|None=Field(None,max_length=200)
    @field_validator("email")
    @classmethod
    def normalize_email(cls,value):return str(value).casefold()
def owned(db,user,provider):return db.scalar(select(ProviderCredential).where(ProviderCredential.user_id==user.id,ProviderCredential.provider==provider))
def safe(row):
    adapter=provider_adapter(row.provider)
    return {"provider":row.provider,"status":row.validation_status,"masked_identifier":row.masked_identifier,"last_connection_attempt_at":row.last_connection_attempt_at,"last_successful_connection_at":row.last_successful_connection_at,"last_telemetry_refresh_at":row.last_telemetry_refresh_at,"last_latency_ms":row.last_latency_ms,"created_at":row.created_at,"updated_at":row.updated_at,"capabilities":asdict(adapter.capabilities),"usage_sync_note":"OpenAI organization usage and cost APIs require an organization Admin API key; ordinary project keys are not synchronized." if row.provider=="openai" else None}
def adapter_error(error):return HTTPException({"INVALID":401,"INSUFFICIENT_PERMISSION":403,"RATE_LIMITED":429,"TIMEOUT":504,"UNAVAILABLE":503}.get(error.status,400),str(error))
def decrypt(row):
    try:return decrypt_credential(row.encrypted_credential,row.user_id,row.provider,row.key_version)
    except CredentialConfigurationError as error:raise HTTPException(503,"Provider credential encryption is not configured") from error
    except Exception as error:raise HTTPException(503,"Provider credential could not be decrypted") from error
def limited(db,user,provider):enforce_rate_limit(db,"provider_connection",f"{user.id}:{provider}",10,15)

@router.get("")
def connections(user:User=Depends(require_operational_user),db:Session=Depends(db_session)):return {"items":[safe(x) for x in db.scalars(select(ProviderCredential).where(ProviderCredential.user_id==user.id)).all()],"supported":[provider_adapter("openai").get_connection_status()]}
@router.get("/{provider}")
def status(provider:str,user:User=Depends(require_operational_user),db:Session=Depends(db_session)):
    row=owned(db,user,provider.casefold());return safe(row) if row else {"provider":provider.casefold(),"status":"NOT_CONNECTED","capabilities":asdict(provider_adapter(provider).capabilities)}
@router.post("/{provider}/connect",dependencies=[Depends(require_csrf)])
def connect(provider:str,payload:ConnectIn,user:User=Depends(require_operational_user),db:Session=Depends(db_session)):
    provider=provider.casefold();limited(db,user,provider);adapter=provider_adapter(provider);credential=payload.credential.get_secret_value();row=owned(db,user,provider);attempted=utcnow()
    try:result=adapter.validate_credentials(credential);encrypted=encrypt_credential(credential,user.id,provider)
    except ProviderError as error:
        if row:row.validation_status=error.status;row.last_connection_attempt_at=attempted;row.updated_at=attempted
        audit(db,"provider.validation_failed",outcome="failure",actor=user.id,resource_type="provider",resource_id=provider,status=error.status);db.commit();raise adapter_error(error)
    except CredentialConfigurationError as error:raise HTTPException(503,"Provider credential encryption is not configured") from error
    row=row or ProviderCredential(user_id=user.id,provider=provider);db.add(row);row.encrypted_credential=encrypted;row.key_version=1;row.masked_identifier=f"••••{credential[-4:]}";row.validation_status=result["status"];row.last_connection_attempt_at=attempted;row.last_successful_connection_at=attempted;row.last_telemetry_refresh_at=attempted;row.last_latency_ms=result.get("latency_ms");row.last_validated_at=attempted;row.updated_at=attempted;audit(db,"provider.connected",actor=user.id,resource_type="provider",resource_id=provider);db.commit();return safe(row)
@router.post("/{provider}/validate",dependencies=[Depends(require_csrf)])
@router.post("/{provider}/test",dependencies=[Depends(require_csrf)])
def validate(provider:str,user:User=Depends(require_operational_user),db:Session=Depends(db_session)):
    provider=provider.casefold();limited(db,user,provider);row=owned(db,user,provider)
    if not row:raise HTTPException(404,"Provider connection not found")
    attempted=utcnow();row.last_connection_attempt_at=attempted
    try:
        result=provider_adapter(row.provider).validate_credentials(decrypt(row));row.validation_status="CONNECTED";row.last_validated_at=attempted;row.last_successful_connection_at=attempted;row.last_telemetry_refresh_at=attempted;row.last_latency_ms=result.get("latency_ms");row.updated_at=attempted;audit(db,"provider.validated",actor=user.id,resource_type="provider",resource_id=row.provider);db.commit();return safe(row)
    except ProviderError as error:row.validation_status=error.status;row.updated_at=attempted;audit(db,"provider.validation_failed",outcome="failure",actor=user.id,resource_type="provider",resource_id=row.provider,status=error.status);db.commit();raise adapter_error(error)
@router.get("/{provider}/models")
def models(provider:str,user:User=Depends(require_operational_user),db:Session=Depends(db_session)):
    provider=provider.casefold();limited(db,user,provider);row=owned(db,user,provider)
    if not row:raise HTTPException(404,"Provider connection not found")
    try:items=provider_adapter(row.provider).get_available_models(decrypt(row))
    except ProviderError as error:raise adapter_error(error)
    refreshed=utcnow();db.execute(delete(ProviderModel).where(ProviderModel.user_id==user.id,ProviderModel.provider==row.provider))
    for item in items:db.add(ProviderModel(user_id=user.id,provider=row.provider,model_id=item.id,owned_by=item.owned_by,provider_created_at=item.created_at,context_window=item.context_window,modalities=item.modalities,capabilities=item.capabilities,last_seen_at=refreshed))
    row.last_telemetry_refresh_at=refreshed;row.updated_at=refreshed;db.commit();return {"provider":row.provider,"items":[asdict(x) for x in items],"unknown_metadata_remains_null":True}
@router.delete("/{provider}",dependencies=[Depends(require_csrf)])
def disconnect(provider:str,user:User=Depends(require_operational_user),db:Session=Depends(db_session)):
    row=owned(db,user,provider.casefold())
    if not row:raise HTTPException(404,"Provider connection not found")
    stopped=utcnow()
    for session in db.scalars(select(LiveTelemetrySession).where(LiveTelemetrySession.user_id==user.id,LiveTelemetrySession.provider==row.provider,LiveTelemetrySession.status=="ACTIVE")):session.status="STOPPED";session.stopped_at=stopped
    db.delete(row);db.execute(delete(ProviderModel).where(ProviderModel.user_id==user.id,ProviderModel.provider==row.provider));audit(db,"provider.disconnected",actor=user.id,resource_type="provider",resource_id=row.provider);db.commit();return {"provider":row.provider,"status":"DISCONNECTED","revocation_required":True}

@public_router.get("/api/telemetry")
def public_telemetry(db:Session=Depends(db_session)):
    connection=db.scalar(select(ProviderCredential).where(ProviderCredential.provider=="openai",ProviderCredential.validation_status=="CONNECTED").order_by(ProviderCredential.last_successful_connection_at.desc()).limit(1));available=set(db.scalars(select(ProviderModel.model_id).where(ProviderModel.provider=="openai")).all());prices=db.scalars(select(PricingRecord).where(PricingRecord.provider=="openai",PricingRecord.effective_to.is_(None)).order_by(PricingRecord.model)).all()
    return {"provider":"openai","status":"AVAILABLE" if connection else "NOT_CONNECTED","source":"LIVE_CONNECTION" if connection else "CATALOG","last_refreshed_at":connection.last_telemetry_refresh_at if connection else None,"latency_ms":connection.last_latency_ms if connection else None,"usage_available":False,"models":[{"id":x.model,"availability":"AVAILABLE" if x.model in available else "UNKNOWN","pricing":{"unit":x.pricing_unit,"input":float(x.input_price),"output":float(x.output_price),"cached_input":float(x.cached_input_price) if x.cached_input_price is not None else None,"currency":x.currency,"source":x.provenance,"last_verified_at":x.last_verified_at}} for x in prices]}

@public_router.post("/api/v1/public/requests",status_code=202)
def public_request(payload:PublicRequestIn,request:Request,db:Session=Depends(db_session)):
    # Honeypot submissions intentionally receive the same generic response.
    if payload.website:return {"accepted":True}
    host=request.client.host if request.client else "unknown"
    enforce_rate_limit(db,"public_access_request",host,8,60)
    audit(db,"public.request_received",resource_type="public_request",resource_id=payload.request_type.lower(),request_type=payload.request_type,name=payload.name,email=str(payload.email),company=payload.company,role=payload.role,ai_spend_range=payload.ai_spend_range,preferred_contact=payload.preferred_contact,providers=payload.providers,goals=payload.goals,status="NEW")
    db.commit();return {"accepted":True}
