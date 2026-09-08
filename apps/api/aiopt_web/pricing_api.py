"""Admin-credential-controlled global pricing and signed-in catalog views."""
from datetime import datetime,timedelta,timezone
from decimal import Decimal,InvalidOperation
from fastapi import APIRouter,Depends,HTTPException,Query
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from .auth import audit,require_admin,require_csrf,require_operational_user
from .database import db_session
from .models import PriceOverride,PricingCatalogModel,PricingRecord,PricingRefresh,ProviderCredential,User
from .provider_credentials import CredentialConfigurationError,decrypt_credential
from .providers import ProviderError,provider_adapter
from .pricing_catalog import ALIASES,CATALOG,CURRENT,REVIEWED_AT,canonical,category,lifecycle,source
from .security import utcnow

router=APIRouter(prefix="/api/v1/admin/pricing");public_router=APIRouter(prefix="/api/v1/pricing")
SOURCE="https://developers.openai.com/api/docs/models/compare";MODEL_SOURCE="https://api.openai.com/v1/models"
SOURCE_LABEL="OpenAI Official Pricing Documentation";STALE_AFTER_DAYS=180
class RefreshIn(BaseModel):
    model_config=ConfigDict(extra="forbid");provider:str=Field("openai",pattern=r"^[a-z0-9_.-]+$");apply:bool=False;confirm_anomalies:bool=False
def validate_prices(provider):
    result=[]
    for source_provider,model,inp,out,cached in CATALOG:
        if source_provider!=provider:continue
        try:values=(Decimal(inp),Decimal(out),Decimal(cached) if cached is not None else None)
        except InvalidOperation as error:raise ValueError(f"Invalid decimal price for {provider}/{model}") from error
        if not model or any(x<0 or x>Decimal("1000000") for x in values if x is not None):raise ValueError(f"Invalid price record for {provider}/{model}")
        result.append((provider,model,*values))
    return result
def admin_connection(db,user,provider):return db.scalar(select(ProviderCredential).where(ProviderCredential.user_id==user.id,ProviderCredential.provider==provider))
def discover(row):
    try:key=decrypt_credential(row.encrypted_credential,row.user_id,row.provider,row.key_version);return provider_adapter(row.provider).get_available_models(key)
    except CredentialConfigurationError as error:raise HTTPException(503,"Provider credential encryption is not configured") from error
    except ProviderError as error:raise HTTPException({"INVALID":401,"INSUFFICIENT_PERMISSION":403,"RATE_LIMITED":429,"TIMEOUT":504,"UNAVAILABLE":503}.get(error.status,400),str(error)) from error
    except Exception as error:raise HTTPException(503,"Stored provider credential could not be decrypted") from error
def compare(db,items):
    changes=[];unchanged=added=changed=0
    for provider,model,inp,out,cached in items:
        current=db.scalar(select(PricingRecord).where(PricingRecord.provider==provider,PricingRecord.model==model,PricingRecord.effective_to.is_(None)).order_by(PricingRecord.effective_from.desc()));current_values=(Decimal(current.input_price),Decimal(current.output_price),Decimal(current.cached_input_price) if current and current.cached_input_price is not None else None) if current else None;different=not current or current_values!=(inp,out,cached);state="added" if not current else "changed" if different else "unchanged";added+=state=="added";changed+=state=="changed";unchanged+=state=="unchanged";changes.append({"provider":provider,"model":model,"status":state,"before":{"input":float(current.input_price),"output":float(current.output_price),"cached_input":float(current.cached_input_price) if current.cached_input_price is not None else None} if current else None,"after":{"input":float(inp),"output":float(out),"cached_input":float(cached) if cached is not None else None}})
    return changes,added,changed,unchanged
def direction(before,after):
    if before is None:return "UNCHANGED" if after is None else "NEWLY_AVAILABLE"
    if after is None:return "DISAPPEARED" if before is not None else "UNCHANGED"
    if after>before:return "INCREASED"
    if after<before:return "DECREASED"
    return "UNCHANGED"
def change_details(change):
    before=change["before"];after=change["after"];dimensions=[]
    for field in ("input","cached_input","output"):
        old=before[field] if before else None;new=after[field];kind=direction(old,new);percent=None if old in (None,0) or new is None else round((new-old)/old*100,2);ratio=None if old in (None,0) or new is None else new/old;dimensions.append({"dimension":field,"previous":old,"new":new,"direction":kind,"percentage_change":percent,"requires_review":ratio is not None and (ratio>10 or ratio<.1)})
    return change|{"dimensions":dimensions,"requires_review":any(x["requires_review"] for x in dimensions)}
def failed_refresh(db,user,provider,row,message,status):
    db.add(PricingRefresh(admin_user_id=user.id,source=SOURCE,provider=provider,provider_credential_id=row.id if row else None,providers_checked=1,success=False,validation_errors=[message],source_type="MANUAL_MAINTAINED_CATALOG"));audit(db,"pricing.refresh_failed",outcome="failure",actor=user.id,resource_type="pricing",provider=provider,status=status);db.commit()

@router.get("")
def history(user:User=Depends(require_admin),db:Session=Depends(db_session)):
    rows=db.scalars(select(PricingRefresh).order_by(PricingRefresh.created_at.desc()).limit(10)).all();connections={x.provider:x for x in db.scalars(select(ProviderCredential).where(ProviderCredential.user_id==user.id)).all()}
    last_discovery=db.scalar(select(PricingCatalogModel.retrieved_at).where(PricingCatalogModel.provider=="openai").order_by(PricingCatalogModel.retrieved_at.desc()).limit(1))
    return {"last_successful_refresh":next((x.created_at for x in rows if x.success),None),"providers":[{"provider":"openai","credential_status":connections["openai"].validation_status if "openai" in connections else "NOT_CONFIGURED","masked_identifier":connections["openai"].masked_identifier if "openai" in connections else None,"model_catalog_source":"AUTHENTICATED_PROVIDER_API","pricing_source_type":"MANUAL_MAINTAINED_CATALOG","pricing_source":SOURCE,"pricing_source_label":SOURCE_LABEL,"last_pricing_review":REVIEWED_AT,"last_model_discovery":last_discovery,"stale_after_days":STALE_AFTER_DAYS}],"items":[{"timestamp":x.created_at,"provider":x.provider,"provider_credential_id":x.provider_credential_id,"models_retrieved":x.models_retrieved,"prices_retrieved":x.prices_retrieved,"models_changed":x.models_changed,"models_added":x.models_added,"success":x.success,"source_type":x.source_type,"validation_errors":x.validation_errors} for x in rows]}

@router.post("/refresh",dependencies=[Depends(require_csrf)])
def refresh(payload:RefreshIn,user:User=Depends(require_admin),db:Session=Depends(db_session)):
    provider=payload.provider.casefold();row=admin_connection(db,user,provider)
    if not row:failed_refresh(db,user,provider,None,"Admin provider credential is not configured","NOT_CONFIGURED");raise HTTPException(409,f"Admin credential for {provider} is not configured")
    try:models=discover(row);all_prices=validate_prices(provider)
    except HTTPException as error:failed_refresh(db,user,provider,row,str(error.detail),"PROVIDER_ERROR");raise
    except ValueError as error:failed_refresh(db,user,provider,row,str(error),"VALIDATION_ERROR");raise HTTPException(422,str(error))
    discovered={x.id for x in models};resolved={canonical(x) for x in discovered};prices=[x for x in all_prices if x[1] in resolved];changes,added,changed,unchanged=compare(db,prices);changes=[change_details(x) for x in changes];known_models={x.model_id for x in db.scalars(select(PricingCatalogModel).where(PricingCatalogModel.provider==provider)).all()};active_models={x.model for x in db.scalars(select(PricingRecord).where(PricingRecord.provider==provider,PricingRecord.effective_to.is_(None))).all()};priced_models={x[1] for x in prices};missing=sorted(x for x in discovered if canonical(x) not in priced_models);removed=sorted(known_models-discovered);disappeared=sorted((active_models&resolved)-priced_models);override_models={(x.provider,x.model) for x in db.scalars(select(PriceOverride).where(PriceOverride.provider==provider)).all()};protected=sorted(model for model in discovered if (provider,model) in override_models or (provider,canonical(model)) in override_models);anomalies=[x for x in changes if x["requires_review"]];result={"provider":provider,"credential_status":row.validation_status,"applied":payload.apply,"models_discovered":len(discovered),"current_models":sum(lifecycle(x)=="CURRENT" for x in discovered),"legacy_models":sum(lifecycle(x)=="LEGACY" for x in discovered),"prices_retrieved":len(prices),"priced_models":sum(canonical(x) in priced_models for x in discovered),"alias_resolved_models":sum(x in ALIASES and canonical(x) in priced_models for x in discovered),"non_token_models":sum(category(x) in {"REALTIME","AUDIO","IMAGE","VIDEO"} for x in discovered),"models_changed":changed,"models_unchanged":unchanged,"models_added":added,"new_models_discovered":sorted(discovered-known_models),"models_removed_or_unavailable":removed,"models_missing_pricing":missing,"pricing_disappeared":disappeared,"manual_overrides_protecting_effective_price":protected,"stale_pricing":[x.model for x in db.scalars(select(PricingRecord).where(PricingRecord.provider==provider,PricingRecord.effective_to.is_(None),PricingRecord.last_verified_at<utcnow()-timedelta(days=STALE_AFTER_DAYS))).all()],"anomalies_requiring_review":anomalies,"errors":[],"model_catalog_source":"AUTHENTICATED_PROVIDER_API","pricing_source_type":"MANUAL_MAINTAINED_CATALOG","pricing_source":SOURCE,"pricing_source_label":SOURCE_LABEL,"last_pricing_review":REVIEWED_AT,"changes":changes}
    if payload.apply and anomalies and not payload.confirm_anomalies:raise HTTPException(409,"Unusually large pricing changes require explicit admin confirmation")
    if not payload.apply:return result
    now=utcnow()
    for catalog in db.scalars(select(PricingCatalogModel).where(PricingCatalogModel.provider==provider)).all():catalog.availability_status="UNAVAILABLE"
    for item in models:
        catalog=db.scalar(select(PricingCatalogModel).where(PricingCatalogModel.provider==provider,PricingCatalogModel.model_id==item.id)) or PricingCatalogModel(provider=provider,model_id=item.id,display_name=item.id,catalog_source_reference=MODEL_SOURCE);db.add(catalog);catalog.availability_status="AVAILABLE";catalog.catalog_source_type="AUTHENTICATED_PROVIDER_API";catalog.discovered_by_credential_id=row.id;catalog.retrieved_at=now;catalog.pricing_category=category(item.id);catalog.lifecycle_status=lifecycle(item.id);catalog.canonical_pricing_model=canonical(item.id) if canonical(item.id)!=item.id else None
    for change,(item_provider,model,inp,out,cached) in zip(changes,prices):
        if change["status"]=="unchanged":
            current=db.scalar(select(PricingRecord).where(PricingRecord.provider==item_provider,PricingRecord.model==model,PricingRecord.effective_to.is_(None)));current.last_verified_at=REVIEWED_AT;current.provenance=source(model);continue
        current=db.scalar(select(PricingRecord).where(PricingRecord.provider==item_provider,PricingRecord.model==model,PricingRecord.effective_to.is_(None)).order_by(PricingRecord.effective_from.desc()))
        if current:current.effective_to=now
        db.add(PricingRecord(provider=item_provider,model=model,effective_from=now,input_price=inp,output_price=out,cached_input_price=cached,currency="USD",region=None,provenance=source(model),last_verified_at=REVIEWED_AT))
    for vanished in disappeared:
        current=db.scalar(select(PricingRecord).where(PricingRecord.provider==provider,PricingRecord.model==vanished,PricingRecord.effective_to.is_(None)));current.effective_to=now
    db.add(PricingRefresh(admin_user_id=user.id,created_at=now,source=SOURCE,provider=provider,provider_credential_id=row.id,providers_checked=1,models_checked=len(models),models_retrieved=len(models),prices_retrieved=len(prices),models_changed=changed,models_unchanged=unchanged,models_added=added,success=True,validation_errors=[],source_type="MANUAL_MAINTAINED_CATALOG"));audit(db,"pricing.refreshed",actor=user.id,resource_type="pricing",provider=provider,credential_reference=row.id,models_retrieved=len(models),prices_retrieved=len(prices));db.commit();return result|{"refreshed_at":now}

@public_router.get("")
def catalog(q:str="",provider:str|None=None,sort:str=Query("name",pattern="^(name|input|output)$"),missing:bool=False,user:User=Depends(require_operational_user),db:Session=Depends(db_session)):
    discovered={(x.provider,x.model_id):x for x in db.scalars(select(PricingCatalogModel)).all()};prices={(x.provider,x.model):x for x in db.scalars(select(PricingRecord).where(PricingRecord.effective_to.is_(None))).all()};overrides={(x.provider,x.model):x for x in db.scalars(select(PriceOverride).where(PriceOverride.user_id==user.id)).all()};keys=set(discovered)|set(prices)|set(overrides);items=[]
    for key in keys:
        provider_id,model=key
        if (provider and provider_id!=provider.casefold()) or (q and q.casefold() not in model.casefold()):continue
        canonical_model=canonical(model) if provider_id=="openai" else model;base=prices.get(key) or prices.get((provider_id,canonical_model));override=overrides.get(key) or overrides.get((provider_id,canonical_model));unknown=not base and not override
        if missing and not unknown:continue
        reviewed=base.last_verified_at.replace(tzinfo=timezone.utc) if base and base.last_verified_at.tzinfo is None else base.last_verified_at if base else None;stale=bool(reviewed and reviewed<utcnow()-timedelta(days=STALE_AFTER_DAYS));base_status="FALLBACK" if base and base.provenance=="BUILT_IN_FALLBACK" else "STALE" if stale else "CURRENT" if base else "UNKNOWN";status="MANUAL_OVERRIDE" if override else base_status;catalog_row=discovered.get(key);items.append({"provider":provider_id,"model":model,"display_name":catalog_row.display_name if catalog_row else model,"availability":catalog_row.availability_status if catalog_row else "UNKNOWN","lifecycle":catalog_row.lifecycle_status if catalog_row else lifecycle(model),"pricing_category":catalog_row.pricing_category if catalog_row else category(model),"canonical_pricing_model":canonical_model if canonical_model!=model else None,"input_price_per_1m":override.input_price if override else float(base.input_price) if base else None,"cached_input_price_per_1m":float(base.cached_input_price) if base and base.cached_input_price is not None and not override else None,"output_price_per_1m":override.output_price if override else float(base.output_price) if base else None,"currency":base.currency if base else "USD","status":status,"base_status":base_status,"manual_override_active":bool(override),"catalog_input_price_per_1m":float(base.input_price) if base else None,"catalog_output_price_per_1m":float(base.output_price) if base else None,"pricing_source":"MANUAL_OVERRIDE" if override else base.provenance if base else None,"effective_at":base.effective_from if base else None,"last_pricing_review":base.last_verified_at if base else None,"stale_after_days":STALE_AFTER_DAYS,"retrieved_at":catalog_row.retrieved_at if catalog_row else base.last_verified_at if base else None,"catalog_source":catalog_row.catalog_source_type if catalog_row else None,"additional_dimensions":catalog_row.extra_pricing_dimensions if catalog_row else {}})
    items.sort(key=(lambda x:(x["input_price_per_1m"] is None,x["input_price_per_1m"] or 0)) if sort=="input" else (lambda x:(x["output_price_per_1m"] is None,x["output_price_per_1m"] or 0)) if sort=="output" else lambda x:(x["provider"],x["model"]));return {"unit":"USD_PER_MILLION_TOKENS","items":items,"providers":sorted({x["provider"] for x in items})}
