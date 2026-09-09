"""Admin-credential-controlled global pricing and signed-in catalog views."""
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from decimal import Decimal,InvalidOperation
import threading
from fastapi import APIRouter,Depends,HTTPException,Query
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy import select,text
from sqlalchemy.orm import Session
from .auth import audit,require_csrf,require_operational_user,require_platform_admin
from .config import settings
from .database import SessionLocal,db_session,engine
from .models import ModelCapabilityEvidence,ModelSkill,PriceOverride,PricingCatalogModel,PricingRecord,PricingRefresh,ProviderCredential,User
from .provider_credentials import CredentialConfigurationError,decrypt_credential
from .providers import ProviderError,provider_adapter
from .pricing_catalog import ALIASES,CATALOG,CURRENT,REVIEWED_AT,canonical,category,lifecycle,source
from .multi_provider_catalog import BY_KEY,CATALOG_ENTRIES,VERIFIED_AT,Workload,calculate_entry,comparable_models
from .capability_scoring import capability_profiles,profile_for
from .security import utcnow

router=APIRouter(prefix="/api/v1/admin/pricing");public_router=APIRouter(prefix="/api/v1/pricing")
SOURCE="https://developers.openai.com/api/docs/models/compare";MODEL_SOURCE="https://api.openai.com/v1/models"
SOURCE_LABEL="OpenAI Official Pricing Documentation";STALE_AFTER_DAYS=180
_refresh_lock=threading.Lock();_LOCK_ID=17420361
def _acquire_refresh(db):
    # Transaction-scoped locks are released by PostgreSQL on commit/rollback.
    # A session-scoped lock can survive an endpoint commit when SQLAlchemy
    # returns that connection to the pool before dependency cleanup runs.
    if engine.dialect.name=="postgresql":return bool(db.scalar(text("SELECT pg_try_advisory_xact_lock(:id)"),{"id":_LOCK_ID}))
    return _refresh_lock.acquire(blocking=False)
def _release_refresh(db):
    if engine.dialect.name!="postgresql" and _refresh_lock.locked():_refresh_lock.release()
def refresh_guard(db:Session=Depends(db_session)):
    if not _acquire_refresh(db):raise HTTPException(409,"Refresh already in progress.")
    try:yield
    finally:_release_refresh(db)
def capability_admin_data(db):
    profiles=capability_profiles(db);skills={x.id:x.name for x in db.scalars(select(ModelSkill)).all()}
    evidence=db.scalars(select(ModelCapabilityEvidence).order_by(ModelCapabilityEvidence.provider,ModelCapabilityEvidence.model_id,ModelCapabilityEvidence.evaluation_name)).all()
    keys={(x.provider,x.model) for x in CATALOG_ENTRIES}|{(x[0],x[1]) for x in CATALOG}|{(x.provider,x.model_id) for x in db.scalars(select(PricingCatalogModel)).all()}
    models=[]
    for provider,model in sorted(keys):
        profile=profile_for(db,provider,model,profiles);models.append({"provider":provider,"model":model,"rating_type":profile["rating_type"],"needs_review":profile["needs_review"],"inherited_from":profile["inherited_from"],"skills":profile["skills"],"pricing_verified":next((x.pricing_available for x in CATALOG_ENTRIES if x.provider==provider and x.model==model),False)})
    rows=[{"provider":x.provider,"model":x.model_id,"skill":skills.get(x.skill_id,"Unknown"),"benchmark":x.evaluation_name,"raw_score":x.raw_score,"evaluation_max":x.evaluation_max,"source_url":x.source_url,"evaluation_date":x.evaluation_date,"confidence":x.confidence,"provider_reported":x.provider_reported,"independent":x.independent} for x in evidence]
    return {"models":models,"evidence":rows,"counts":{"VERIFIED":sum(x["rating_type"]=="VERIFIED" for x in models),"BENCHMARK-INFORMED":sum(x["rating_type"]=="BENCHMARK-INFORMED" for x in models),"ESTIMATED":sum(x["rating_type"]=="ESTIMATED" for x in models),"needs_review":sum(x["needs_review"] for x in models),"evidence_records":len(rows)}}
@public_router.get("/demo")
def demo_catalog():
    selected={("anthropic","claude-sonnet-5"),("google","gemini-3.8-flash"),("xai","grok-4.6"),("mistral","mistral-medium-3-5"),("deepseek","deepseek-v4-pro"),("cohere","command-a-03-2025"),("perplexity","sonar-pro")}
    items=[entry.public() for entry in CATALOG_ENTRIES if (entry.provider,entry.model) in selected]
    # Keep one existing OpenAI row while exposing a genuinely cross-provider demo.
    openai=next(({"provider":provider,"model":model,"display_name":model,"family":"GPT","input":float(inp),"output":float(out),"cached_input":float(cached) if cached is not None else None,"capabilities":["FRONTIER","ADVANCED_REASONING","CODING","TOOL_CALLING","STRUCTURED_OUTPUT"],"quality_tier":1,"context_window":None,"max_output_tokens":None,"source":source(model),"model_creator":"OpenAI","hosting_provider":None,"deprecated":False,"preview":False,"rules":{},"verified_at":REVIEWED_AT,"pricing_unit":"USD_PER_MILLION_TOKENS","pricing_available":True} for provider,model,inp,out,cached in CATALOG if model=="gpt-6-astra"),None)
    return {"items":([openai] if openai else [])+items,"unit":"USD_PER_MILLION_TOKENS","workload":"SIMULATED","notice":"Verified catalog pricing; workload and comparisons are simulated. Quality equivalence is not implied."}
class RefreshIn(BaseModel):
    model_config=ConfigDict(extra="forbid");provider:str=Field("openai",pattern=r"^[a-z0-9_.-]+$");apply:bool=False;confirm_anomalies:bool=False
class RepriceIn(BaseModel):
    model_config=ConfigDict(extra="forbid")
    provider:str=Field(pattern=r"^[a-z0-9_.-]+$");model:str=Field(min_length=1,max_length=160)
    input_tokens:int=Field(ge=0);output_tokens:int=Field(ge=0);cached_input_tokens:int=Field(0,ge=0);cache_write_tokens:int=Field(0,ge=0)
    requests:int=Field(0,ge=0);searches:int=Field(0,ge=0);citation_tokens:int=Field(0,ge=0);reasoning_tokens:int=Field(0,ge=0)
    context_length:int|None=Field(None,ge=1);batch:bool=False;search_context:str=Field("low",pattern="^(low|medium|high)$");region:str|None=None

@public_router.post("/compare")
def reprice(payload:RepriceIn,user:User=Depends(require_operational_user),db:Session=Depends(db_session)):
    entry=BY_KEY.get((payload.provider.casefold(),payload.model))
    if not entry:raise HTTPException(404,"Unknown provider/model catalog entry")
    override=db.scalar(select(PriceOverride).where(PriceOverride.user_id==user.id,PriceOverride.provider==entry.provider,PriceOverride.model==entry.model))
    if override:entry=replace(entry,input_price=str(override.input_price),output_price=str(override.output_price),cached_input_price=None,rules={})
    workload=Workload(**payload.model_dump(exclude={"provider","model"}))
    result=calculate_entry(entry,workload)
    if result is None:raise HTTPException(422,"Pricing is unavailable or the workload requires an unsupported pricing rule")
    alternatives=[]
    for candidate in comparable_models(entry.provider,entry.model,capabilities=set(entry.capabilities)&{"MULTIMODAL","CODING","TOOL_CALLING","STRUCTURED_OUTPUT"},context_length=payload.context_length)[:8]:
        candidate_override=db.scalar(select(PriceOverride).where(PriceOverride.user_id==user.id,PriceOverride.provider==candidate.provider,PriceOverride.model==candidate.model))
        if candidate_override:candidate=replace(candidate,input_price=str(candidate_override.input_price),output_price=str(candidate_override.output_price),cached_input_price=None,rules={})
        priced=calculate_entry(candidate,workload)
        if priced:alternatives.append({"provider":candidate.provider,"model":candidate.model,"display_name":candidate.display_name,"quality_tier":candidate.quality_tier,"estimated_cost":float(priced["total"]),"projected_difference":float(result["total"]-priced["total"]),"notice":"Pricing comparison only; quality equivalence is not assumed."})
    return {"current":{"provider":entry.provider,"model":entry.model,"estimated_cost":float(result["total"]),"breakdown":{key:float(value) for key,value in result["components"].items()},"pricing_mode":result["pricing_mode"]},"alternatives":alternatives,"workload_preserved":True}
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
def history(user:User=Depends(require_platform_admin),db:Session=Depends(db_session)):
    rows=db.scalars(select(PricingRefresh).order_by(PricingRefresh.created_at.desc()).limit(10)).all();connections={x.provider:x for x in db.scalars(select(ProviderCredential).where(ProviderCredential.user_id==user.id)).all()}
    last_discovery=db.scalar(select(PricingCatalogModel.retrieved_at).where(PricingCatalogModel.provider=="openai").order_by(PricingCatalogModel.retrieved_at.desc()).limit(1))
    providers=[{"provider":"openai","credential_status":connections["openai"].validation_status if "openai" in connections else "NOT_CONFIGURED","masked_identifier":connections["openai"].masked_identifier if "openai" in connections else None,"model_catalog_source":"AUTHENTICATED_PROVIDER_API","pricing_source_type":"MANUAL_MAINTAINED_CATALOG","pricing_source":SOURCE,"pricing_source_label":SOURCE_LABEL,"last_pricing_review":REVIEWED_AT,"last_model_discovery":last_discovery,"stale_after_days":STALE_AFTER_DAYS}]
    for provider_id in sorted({x.provider for x in CATALOG_ENTRIES}-{ "openai" }):
        entries=[x for x in CATALOG_ENTRIES if x.provider==provider_id];providers.append({"provider":provider_id,"credential_status":"CATALOG_ONLY","masked_identifier":None,"model_catalog_source":"MANUAL_VERIFIED_OFFICIAL_DOCUMENTATION","pricing_source_type":"MANUAL_MAINTAINED_CATALOG","pricing_source":entries[0].source,"pricing_source_label":f"{provider_id.title()} official pricing documentation","last_pricing_review":VERIFIED_AT,"last_model_discovery":None,"stale_after_days":STALE_AFTER_DAYS,"models":len(entries),"priced_models":sum(x.pricing_available for x in entries)})
    cfg=settings();now=utcnow();next_run=(now+timedelta(days=1)).replace(hour=cfg.model_refresh_hour,minute=0,second=0,microsecond=0) if now.hour>=cfg.model_refresh_hour else now.replace(hour=cfg.model_refresh_hour,minute=0,second=0,microsecond=0)
    return {"last_successful_refresh":next((x.created_at for x in rows if x.success),None),"schedule":{"enabled":cfg.model_refresh_enabled,"hour":cfg.model_refresh_hour,"next_run":next_run if cfg.model_refresh_enabled else None},"providers":providers,"items":[{"timestamp":x.created_at,"provider":x.provider,"provider_credential_id":x.provider_credential_id,"models_retrieved":x.models_retrieved,"prices_retrieved":x.prices_retrieved,"models_changed":x.models_changed,"models_added":x.models_added,"success":x.success,"source_type":x.source_type,"validation_errors":x.validation_errors} for x in rows],"capabilities":capability_admin_data(db)}

@router.post("/refresh",dependencies=[Depends(require_csrf),Depends(refresh_guard)])
def refresh(payload:RefreshIn,user:User=Depends(require_platform_admin),db:Session=Depends(db_session)):
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

def run_scheduled_refresh_if_due(now=None):
    cfg=settings();now=now or utcnow()
    if not cfg.model_refresh_enabled or now.hour<cfg.model_refresh_hour:return False
    with SessionLocal() as db:
        start=now.replace(hour=0,minute=0,second=0,microsecond=0)
        if db.scalar(select(PricingRefresh.id).where(PricingRefresh.source_type=="SCHEDULED",PricingRefresh.created_at>=start).limit(1)):return False
        if not _acquire_refresh(db):return False
        try:
            credential=db.scalar(select(ProviderCredential).where(ProviderCredential.provider=="openai",ProviderCredential.validation_status=="CONNECTED").order_by(ProviderCredential.updated_at.desc()))
            admin=db.get(User,credential.user_id) if credential else None
            if not admin or admin.role!="ADMIN" or not admin.is_platform_admin:return False
            result=refresh(RefreshIn(provider="openai",apply=True,confirm_anomalies=False),admin,db)
            row=db.scalar(select(PricingRefresh).order_by(PricingRefresh.created_at.desc()).limit(1))
            if row:row.source_type="SCHEDULED";db.commit()
            return result
        except HTTPException:
            row=db.scalar(select(PricingRefresh).where(PricingRefresh.admin_user_id==admin.id).order_by(PricingRefresh.created_at.desc()).limit(1)) if 'admin' in locals() and admin else None
            if row:row.source_type="SCHEDULED";db.commit()
            return False
        finally:_release_refresh(db)

@public_router.get("")
def catalog(q:str="",provider:str|None=None,sort:str=Query("name",pattern="^(name|input|output)$"),missing:bool=False,user:User=Depends(require_operational_user),db:Session=Depends(db_session)):
    discovered={(x.provider,x.model_id):x for x in db.scalars(select(PricingCatalogModel)).all()};prices={(x.provider,x.model):x for x in db.scalars(select(PricingRecord).where(PricingRecord.effective_to.is_(None))).all()};overrides={(x.provider,x.model):x for x in db.scalars(select(PriceOverride).where(PriceOverride.user_id==user.id)).all()};keys=set(discovered)|set(prices)|set(overrides);items=[]
    for key in keys:
        provider_id,model=key
        if (provider and provider_id!=provider.casefold()) or (q and q.casefold() not in model.casefold()):continue
        canonical_model=canonical(model) if provider_id=="openai" else model;base=prices.get(key) or prices.get((provider_id,canonical_model));override=overrides.get(key) or overrides.get((provider_id,canonical_model));unknown=not base and not override
        if missing and not unknown:continue
        reviewed=base.last_verified_at.replace(tzinfo=timezone.utc) if base and base.last_verified_at.tzinfo is None else base.last_verified_at if base else None;stale=bool(reviewed and reviewed<utcnow()-timedelta(days=STALE_AFTER_DAYS));base_status="FALLBACK" if base and base.provenance=="BUILT_IN_FALLBACK" else "STALE" if stale else "CURRENT" if base else "UNKNOWN";status="MANUAL_OVERRIDE" if override else base_status;catalog_row=discovered.get(key);items.append({"provider":provider_id,"model":model,"display_name":catalog_row.display_name if catalog_row else model,"availability":catalog_row.availability_status if catalog_row else "UNKNOWN","lifecycle":catalog_row.lifecycle_status or lifecycle(model) if catalog_row else lifecycle(model),"pricing_category":catalog_row.pricing_category or "UNKNOWN" if catalog_row else category(model),"canonical_pricing_model":canonical_model if canonical_model!=model else None,"input_price_per_1m":override.input_price if override else float(base.input_price) if base else None,"cached_input_price_per_1m":float(base.cached_input_price) if base and base.cached_input_price is not None and not override else None,"output_price_per_1m":override.output_price if override else float(base.output_price) if base else None,"currency":base.currency if base else "USD","status":status,"base_status":base_status,"manual_override_active":bool(override),"catalog_input_price_per_1m":float(base.input_price) if base else None,"catalog_output_price_per_1m":float(base.output_price) if base else None,"pricing_source":"MANUAL_OVERRIDE" if override else base.provenance if base else None,"effective_at":base.effective_from if base else None,"last_pricing_review":base.last_verified_at if base else None,"stale_after_days":STALE_AFTER_DAYS,"retrieved_at":catalog_row.retrieved_at if catalog_row else base.last_verified_at if base else None,"catalog_source":catalog_row.catalog_source_type if catalog_row else None,"additional_dimensions":catalog_row.extra_pricing_dimensions or {} if catalog_row else {}})
    existing={(x["provider"],x["model"]) for x in items}
    for entry in CATALOG_ENTRIES:
        if (entry.provider,entry.model) in existing or (provider and entry.provider!=provider.casefold()) or (q and q.casefold() not in f"{entry.model} {entry.display_name}".casefold()):continue
        override=overrides.get((entry.provider,entry.model));unknown=not entry.pricing_available and not override
        if missing!=unknown and missing:continue
        public=entry.public();items.append({"provider":entry.provider,"model":entry.model,"display_name":entry.display_name,"availability":"AVAILABLE","lifecycle":"CURRENT","pricing_category":"TEXT_REASONING","canonical_pricing_model":None,"input_price_per_1m":override.input_price if override else public["input"],"cached_input_price_per_1m":None if override else public["cached_input"],"output_price_per_1m":override.output_price if override else public["output"],"currency":"USD","status":"MANUAL_OVERRIDE" if override else "CURRENT" if entry.pricing_available else "UNKNOWN","base_status":"CURRENT" if entry.pricing_available else "UNKNOWN","manual_override_active":bool(override),"catalog_input_price_per_1m":public["input"],"catalog_output_price_per_1m":public["output"],"pricing_source":"MANUAL_OVERRIDE" if override else entry.source,"effective_at":VERIFIED_AT,"last_pricing_review":VERIFIED_AT,"stale_after_days":STALE_AFTER_DAYS,"retrieved_at":VERIFIED_AT,"catalog_source":"MANUAL_MAINTAINED_CATALOG","additional_dimensions":entry.rules,"model_family":entry.family,"capabilities":list(entry.capabilities),"quality_tier":entry.quality_tier,"context_window":entry.context_window,"max_output_tokens":entry.max_output_tokens,"model_creator":entry.model_creator,"hosting_provider":entry.hosting_provider,"deprecated":entry.deprecated,"preview":entry.preview,"pricing_available":entry.pricing_available})
    profiles=capability_profiles(db)
    for item in items:item["capability_profile"]=profile_for(db,item["provider"],item["model"],profiles)
    items.sort(key=(lambda x:(x["input_price_per_1m"] is None,x["input_price_per_1m"] or 0)) if sort=="input" else (lambda x:(x["output_price_per_1m"] is None,x["output_price_per_1m"] or 0)) if sort=="output" else lambda x:(x["provider"],x["model"]));return {"unit":"USD_PER_MILLION_TOKENS","items":items,"providers":sorted({x["provider"] for x in items}),"categories":sorted({x["pricing_category"] for x in items if x["pricing_category"] and x["pricing_category"]!="UNKNOWN"})}
