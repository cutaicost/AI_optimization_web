from pathlib import Path
from secrets import token_hex
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session
from .auth import audit,require_csrf,require_operational_user
from .database import db_session
from .models import ImportJob,TelemetryEvent,User
from .schemas import ImportCommitIn,ImportStartIn
from .security import utcnow
from .telemetry_import import MAX_ACTIVE_IMPORTS,MAX_FILE_SIZE,ImportFailure,auto_mapping,delimiter,encoding,map_row,rows,storage_path,validate_filename

router=APIRouter(prefix="/api/v1")

def owned_job(db,user,import_id):
    job=db.scalar(select(ImportJob).where(ImportJob.id==import_id,ImportJob.user_id==user.id))
    if not job:raise HTTPException(404,"Import not found")
    return job

def job_json(job):
    return {"id":job.id,"filename":job.filename,"file_size":job.file_size,"format":job.file_format,"status":job.status,"total_rows":job.rows_total,"processed_rows":job.rows_processed,"valid_rows":job.rows_valid,"rejected_rows":job.rows_rejected,"inserted_rows":job.rows_imported,"mapping":job.mapping,"sample_rows":job.sample_rows,"failure_reason":job.failure_reason,"created_at":job.created_at,"updated_at":job.updated_at,"completed_at":job.completed_at}

def unlink(job):
    path=storage_path(job.storage_id)
    try:
        if path.is_file() and not path.is_symlink():path.unlink()
    except OSError:pass

@router.post("/import/start",status_code=201,dependencies=[Depends(require_csrf)])
def start_import(payload:ImportStartIn,user:User=Depends(require_operational_user),db:Session=Depends(db_session)):
    try:validate_filename(payload.filename,payload.format)
    except ImportFailure as error:raise HTTPException(400,str(error))
    active=db.scalar(select(func.count()).select_from(ImportJob).where(ImportJob.user_id==user.id,ImportJob.status.in_(["CREATED","UPLOADED","ANALYZING","READY","IMPORTING"]))) or 0
    if active>=MAX_ACTIVE_IMPORTS:raise HTTPException(429,"Too many active imports")
    job=ImportJob(user_id=user.id,filename=Path(payload.filename).name,file_size=payload.file_size,file_format=payload.format,storage_id=token_hex(24))
    db.add(job);db.flush();audit(db,"import.started",actor=user.id,resource_type="import",resource_id=job.id,filename=job.filename,file_size=job.file_size);db.commit()
    return {"import":job_json(job)}

@router.post("/import/{import_id}/upload",dependencies=[Depends(require_csrf)])
async def upload_import(import_id:str,file:UploadFile=File(...),user:User=Depends(require_operational_user),db:Session=Depends(db_session)):
    job=owned_job(db,user,import_id)
    if job.status!="CREATED":raise HTTPException(409,"This import has already been uploaded")
    path=storage_path(job.storage_id);received=0
    try:
        with path.open("xb") as handle:
            while chunk:=await file.read(1_000_000):
                received+=len(chunk)
                if received>MAX_FILE_SIZE or received>job.file_size:raise ImportFailure("Upload exceeds its declared size or the 500 MB limit")
                handle.write(chunk)
        if received!=job.file_size:raise ImportFailure("Upload is incomplete")
    except (ImportFailure,OSError) as error:
        try:path.unlink(missing_ok=True)
        except OSError:pass
        raise HTTPException(400,str(error))
    finally:await file.close()
    job.status="UPLOADED";db.commit();return {"import":job_json(job)}

@router.post("/import/{import_id}/analyze",dependencies=[Depends(require_csrf)])
def analyze_import(import_id:str,user:User=Depends(require_operational_user),db:Session=Depends(db_session)):
    job=owned_job(db,user,import_id)
    if job.status not in {"UPLOADED","READY"}:raise HTTPException(409,"Import is not ready for analysis")
    path=storage_path(job.storage_id)
    if not path.is_file() or path.is_symlink():raise HTTPException(409,"Uploaded file is unavailable")
    job.status="ANALYZING";db.commit()
    try:
        enc=encoding(path);sep=delimiter(path,enc) if job.file_format=="csv" else None
        iterator=rows(path,job.file_format,enc,sep or ",");sample=[];headers=[];total=0
        for row in iterator:
            total+=1
            if not headers:headers=list(row.keys())
            if len(sample)<20:sample.append({str(k)[:120]:str(v)[:500] for k,v in row.items()})
        if total==0:raise ImportFailure("Import contains no data rows")
        job.detected_encoding=enc;job.detected_delimiter=sep;job.rows_total=total;job.sample_rows=sample;job.mapping=auto_mapping(headers);job.status="READY";db.commit()
        return {"import":job_json(job),"columns":headers,"suggested_mapping":job.mapping}
    except Exception as error:
        db.rollback();job=owned_job(db,user,import_id);job.status="FAILED";job.failure_reason=str(error)[:500];job.completed_at=utcnow();audit(db,"import.failed",outcome="failure",actor=user.id,resource_type="import",resource_id=job.id,reason=job.failure_reason);db.commit();unlink(job)
        raise HTTPException(400,"The file could not be analyzed")

@router.get("/import/{import_id}/status")
def import_status(import_id:str,user:User=Depends(require_operational_user),db:Session=Depends(db_session)):return {"import":job_json(owned_job(db,user,import_id))}

@router.post("/import/{import_id}/commit",dependencies=[Depends(require_csrf)])
def commit_import(import_id:str,payload:ImportCommitIn,user:User=Depends(require_operational_user),db:Session=Depends(db_session)):
    job=owned_job(db,user,import_id)
    if job.status!="READY":raise HTTPException(409,"Import is not ready to commit")
    if not {"application","provider","model"}.issubset(set(payload.mapping.values())):raise HTTPException(422,"Mapping must include application, provider, and model")
    path=storage_path(job.storage_id);job.status="IMPORTING";job.mapping=payload.mapping;db.flush();inserted=0;rejected=0;examples=[]
    try:
        for number,row in enumerate(rows(path,job.file_format,job.detected_encoding or "utf-8",job.detected_delimiter or ","),1):
            try:
                data=map_row(row,payload.mapping);db.add(TelemetryEvent(user_id=user.id,organization_id=None,import_job_id=job.id,source="import",metadata_json={},**data));inserted+=1
                if inserted%1000==0:db.flush()
            except Exception as error:
                rejected+=1
                if len(examples)<100:examples.append({"row_number":number,"error":str(error)[:300]})
        db.flush()
        if inserted<1:raise ImportFailure("No valid telemetry rows were available to import")
        job.rows_processed=inserted+rejected;job.rows_valid=inserted;job.rows_imported=inserted;job.rows_rejected=rejected;job.rejected_rows_json=examples;job.status="COMPLETED";job.completed_at=utcnow();audit(db,"import.completed",actor=user.id,resource_type="import",resource_id=job.id,inserted=inserted,rejected=rejected);db.commit();unlink(job)
        return {"import":job_json(job)}
    except Exception:
        db.rollback();job=owned_job(db,user,import_id);job.status="FAILED";job.failure_reason="Telemetry persistence failed; no rows were committed";job.rows_imported=0;job.rows_rejected=rejected;job.rejected_rows_json=examples;job.completed_at=utcnow();audit(db,"import.failed",outcome="failure",actor=user.id,resource_type="import",resource_id=job.id,rejected=rejected);db.commit();unlink(job)
        raise HTTPException(400,job.failure_reason)

@router.post("/import/{import_id}/cancel",dependencies=[Depends(require_csrf)])
def cancel_import(import_id:str,user:User=Depends(require_operational_user),db:Session=Depends(db_session)):
    job=owned_job(db,user,import_id)
    if job.status in {"COMPLETED","FAILED","CANCELLED"}:raise HTTPException(409,"Import can no longer be cancelled")
    job.status="CANCELLED";job.completed_at=utcnow();audit(db,"import.cancelled",actor=user.id,resource_type="import",resource_id=job.id);db.commit();unlink(job);return {"import":job_json(job)}

@router.get("/import/{import_id}/rejected")
def rejected_rows(import_id:str,user:User=Depends(require_operational_user),db:Session=Depends(db_session)):
    job=owned_job(db,user,import_id);return {"items":job.rejected_rows_json,"count":job.rows_rejected}

@router.get("/import/history")
def import_history(limit:int=Query(50,ge=1,le=200),offset:int=Query(0,ge=0),user:User=Depends(require_operational_user),db:Session=Depends(db_session)):
    jobs=db.scalars(select(ImportJob).where(ImportJob.user_id==user.id).order_by(ImportJob.created_at.desc()).offset(offset).limit(limit+1)).all();return {"items":[job_json(x) for x in jobs[:limit]],"has_more":len(jobs)>limit}

def breakdown(db,user,column,value_column):
    return [{"name":name or "Unknown","value":float(value or 0)} for name,value in db.execute(select(column,func.coalesce(func.sum(value_column),0)).where(TelemetryEvent.user_id==user.id).group_by(column).order_by(func.sum(value_column).desc())).all()]

@router.get("/usage")
def usage(user:User=Depends(require_operational_user),db:Session=Depends(db_session)):
    row=db.execute(select(func.count(),func.coalesce(func.sum(TelemetryEvent.input_tokens),0),func.coalesce(func.sum(TelemetryEvent.output_tokens),0),func.coalesce(func.sum(TelemetryEvent.total_tokens),0)).where(TelemetryEvent.user_id==user.id)).one()
    trend=[{"date":str(day),"requests":requests,"tokens":tokens} for day,requests,tokens in db.execute(select(func.date(TelemetryEvent.timestamp),func.count(),func.sum(TelemetryEvent.total_tokens)).where(TelemetryEvent.user_id==user.id).group_by(func.date(TelemetryEvent.timestamp)).order_by(func.date(TelemetryEvent.timestamp))).all()]
    return {"requests":row[0],"input_tokens":row[1],"output_tokens":row[2],"total_tokens":row[3],"trend":trend,"applications":breakdown(db,user,TelemetryEvent.application,TelemetryEvent.total_tokens),"providers":breakdown(db,user,TelemetryEvent.provider,TelemetryEvent.total_tokens),"models":breakdown(db,user,TelemetryEvent.model,TelemetryEvent.total_tokens)}

@router.get("/costs")
def costs(user:User=Depends(require_operational_user),db:Session=Depends(db_session)):
    total=float(db.scalar(select(func.coalesce(func.sum(TelemetryEvent.estimated_cost),0)).where(TelemetryEvent.user_id==user.id)) or 0);requests=db.scalar(select(func.count()).select_from(TelemetryEvent).where(TelemetryEvent.user_id==user.id)) or 0
    trend=[{"date":str(day),"cost":float(cost or 0)} for day,cost in db.execute(select(func.date(TelemetryEvent.timestamp),func.sum(TelemetryEvent.estimated_cost)).where(TelemetryEvent.user_id==user.id).group_by(func.date(TelemetryEvent.timestamp)).order_by(func.date(TelemetryEvent.timestamp))).all()]
    return {"total_spend":total,"average_per_request":total/requests if requests else 0,"trend":trend,"applications":breakdown(db,user,TelemetryEvent.application,TelemetryEvent.estimated_cost),"providers":breakdown(db,user,TelemetryEvent.provider,TelemetryEvent.estimated_cost),"models":breakdown(db,user,TelemetryEvent.model,TelemetryEvent.estimated_cost)}

@router.get("/models")
def models(user:User=Depends(require_operational_user),db:Session=Depends(db_session)):
    total=db.scalar(select(func.count()).select_from(TelemetryEvent).where(TelemetryEvent.user_id==user.id)) or 0
    rows_=db.execute(select(TelemetryEvent.model,TelemetryEvent.provider,func.count(),func.sum(TelemetryEvent.total_tokens),func.sum(TelemetryEvent.estimated_cost),func.avg(TelemetryEvent.duration_ms)).where(TelemetryEvent.user_id==user.id).group_by(TelemetryEvent.model,TelemetryEvent.provider).order_by(func.count().desc())).all()
    return {"items":[{"model":m,"provider":p,"requests":r,"tokens":t or 0,"cost":float(c or 0),"latency_ms":float(l or 0),"share":r/total if total else 0} for m,p,r,t,c,l in rows_]}
