"""Authenticated provider connection lifecycle APIs."""
from dataclasses import asdict
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,ConfigDict,SecretStr
from sqlalchemy import delete,select
from sqlalchemy.orm import Session
from .auth import audit,require_analyst,require_csrf,require_operational_user
from .database import db_session
from .models import ProviderCredential,ProviderModel,User
from .provider_credentials import CredentialConfigurationError,decrypt_credential,encrypt_credential
from .providers import ProviderError,provider_adapter
from .security import utcnow

router=APIRouter(prefix="/api/v1/providers")
class ConnectIn(BaseModel):model_config=ConfigDict(extra="forbid");credential:SecretStr
def owned(db,user,provider):return db.scalar(select(ProviderCredential).where(ProviderCredential.user_id==user.id,ProviderCredential.provider==provider))
def safe(row):
    adapter=provider_adapter(row.provider);return {"provider":row.provider,"status":row.validation_status,"masked_identifier":row.masked_identifier,"last_validated_at":row.last_validated_at,"created_at":row.created_at,"updated_at":row.updated_at,"capabilities":asdict(adapter.capabilities),"usage_sync_note":"OpenAI organization usage and cost APIs require an organization Admin API key; ordinary project keys are not synchronized." if row.provider=="openai" else None}
def adapter_error(error):return HTTPException({"INVALID":401,"INSUFFICIENT_PERMISSION":403,"RATE_LIMITED":429,"TIMEOUT":504,"UNAVAILABLE":503}.get(error.status,400),str(error))
def decrypt(row):
    try:return decrypt_credential(row.encrypted_credential,row.user_id,row.provider,row.key_version)
    except CredentialConfigurationError as error:raise HTTPException(503,"Provider credential encryption is not configured") from error
    except Exception as error:raise HTTPException(503,"Provider credential could not be decrypted") from error

@router.get("")
def connections(user:User=Depends(require_operational_user),db:Session=Depends(db_session)):return {"items":[safe(x) for x in db.scalars(select(ProviderCredential).where(ProviderCredential.user_id==user.id)).all()],"supported":[provider_adapter("openai").get_connection_status()]}
@router.get("/{provider}")
def status(provider:str,user:User=Depends(require_operational_user),db:Session=Depends(db_session)):
    row=owned(db,user,provider.casefold());return safe(row) if row else {"provider":provider.casefold(),"status":"NOT_CONNECTED","capabilities":asdict(provider_adapter(provider).capabilities)}
@router.post("/{provider}/connect",dependencies=[Depends(require_csrf)])
def connect(provider:str,payload:ConnectIn,user:User=Depends(require_analyst),db:Session=Depends(db_session)):
    provider=provider.casefold();adapter=provider_adapter(provider);credential=payload.credential.get_secret_value()
    try:result=adapter.validate_credentials(credential);encrypted=encrypt_credential(credential,user.id,provider)
    except ProviderError as error:audit(db,"provider.validation_failed",outcome="failure",actor=user.id,resource_type="provider",resource_id=provider,status=error.status);db.commit();raise adapter_error(error)
    except CredentialConfigurationError as error:raise HTTPException(503,"Provider credential encryption is not configured") from error
    row=owned(db,user,provider) or ProviderCredential(user_id=user.id,provider=provider);db.add(row);row.encrypted_credential=encrypted;row.key_version=1;row.masked_identifier=f"••••{credential[-4:]}";row.validation_status=result["status"];row.last_validated_at=utcnow();row.updated_at=utcnow();audit(db,"provider.connected",actor=user.id,resource_type="provider",resource_id=provider);db.commit();return safe(row)
@router.post("/{provider}/validate",dependencies=[Depends(require_csrf)])
def validate(provider:str,user:User=Depends(require_analyst),db:Session=Depends(db_session)):
    row=owned(db,user,provider.casefold())
    if not row:raise HTTPException(404,"Provider connection not found")
    try:provider_adapter(row.provider).validate_credentials(decrypt(row));row.validation_status="CONNECTED";row.last_validated_at=utcnow();row.updated_at=utcnow();audit(db,"provider.validated",actor=user.id,resource_type="provider",resource_id=row.provider);db.commit();return safe(row)
    except ProviderError as error:row.validation_status=error.status;row.updated_at=utcnow();audit(db,"provider.validation_failed",outcome="failure",actor=user.id,resource_type="provider",resource_id=row.provider,status=error.status);db.commit();raise adapter_error(error)
@router.get("/{provider}/models")
def models(provider:str,user:User=Depends(require_operational_user),db:Session=Depends(db_session)):
    row=owned(db,user,provider.casefold())
    if not row:raise HTTPException(404,"Provider connection not found")
    try:items=provider_adapter(row.provider).get_available_models(decrypt(row))
    except ProviderError as error:raise adapter_error(error)
    db.execute(delete(ProviderModel).where(ProviderModel.user_id==user.id,ProviderModel.provider==row.provider))
    for item in items:db.add(ProviderModel(user_id=user.id,provider=row.provider,model_id=item.id,owned_by=item.owned_by,provider_created_at=item.created_at,context_window=item.context_window,modalities=item.modalities,capabilities=item.capabilities,last_seen_at=utcnow()))
    db.commit();return {"provider":row.provider,"items":[asdict(x) for x in items],"unknown_metadata_remains_null":True}
@router.delete("/{provider}",dependencies=[Depends(require_csrf)])
def disconnect(provider:str,user:User=Depends(require_analyst),db:Session=Depends(db_session)):
    row=owned(db,user,provider.casefold())
    if not row:raise HTTPException(404,"Provider connection not found")
    db.delete(row);db.execute(delete(ProviderModel).where(ProviderModel.user_id==user.id,ProviderModel.provider==row.provider));audit(db,"provider.disconnected",actor=user.id,resource_type="provider",resource_id=row.provider);db.commit();return {"provider":row.provider,"status":"DISCONNECTED","revocation_required":True}
