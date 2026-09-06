"""Database-backed import worker. Run with: python -m apps.api.aiopt_web.worker."""
import os,time
from datetime import timedelta
from sqlalchemy import delete,select,update
from .auth import audit
from .database import SessionLocal
from .models import ImportJob,TelemetryEvent
from .security import utcnow
from .telemetry_import import ImportFailure,cancellation_path,map_row,rows,storage_path

ACTIVE=("PREPARING","IMPORTING")
def recover_stale_jobs(max_age_minutes=15):
    with SessionLocal() as db:
        cutoff=utcnow()-timedelta(minutes=max_age_minutes)
        jobs=db.scalars(select(ImportJob).where(ImportJob.status.in_(ACTIVE),ImportJob.claimed_at<cutoff)).all()
        for job in jobs:job.status="QUEUED";job.executor_id=None;job.claimed_at=None;job.failure_reason="Recovered after interrupted worker"
        db.commit();return len(jobs)

def claim_next(executor_id):
    with SessionLocal() as db:
        candidate=db.scalar(select(ImportJob.id).where(ImportJob.status=="QUEUED").order_by(ImportJob.updated_at).limit(1))
        if not candidate:return None
        changed=db.execute(update(ImportJob).where(ImportJob.id==candidate,ImportJob.status=="QUEUED",ImportJob.executor_id.is_(None)).values(status="PREPARING",executor_id=executor_id,claimed_at=utcnow(),started_at=utcnow())).rowcount
        db.commit();return candidate if changed==1 else None

def cancellation_requested(job):return cancellation_path(job.storage_id).is_file()

def execute(job_id,executor_id):
    inserted=rejected=0;examples=[]
    with SessionLocal() as db:
        job=db.get(ImportJob,job_id)
        if not job or job.executor_id!=executor_id or job.status!="PREPARING":return False
        path=storage_path(job.storage_id);job.status="IMPORTING";db.commit()
        try:
            db.execute(delete(TelemetryEvent).where(TelemetryEvent.import_job_id==job.id))
            for number,row in enumerate(rows(path,job.file_format,job.detected_encoding or "utf-8",job.detected_delimiter or ","),1):
                if number%250==0 and cancellation_requested(job):raise InterruptedError
                try:
                    data=map_row(row,job.mapping);db.add(TelemetryEvent(user_id=job.user_id,organization_id=None,import_job_id=job.id,source="import",metadata_json={},**data));inserted+=1
                    if inserted%1000==0:db.flush()
                except Exception as error:
                    rejected+=1
                    if len(examples)<100:examples.append({"row_number":number,"error":str(error)[:300]})
            db.flush()
            if inserted<1:raise ImportFailure("No valid telemetry rows were available to import")
            job.rows_processed=inserted+rejected;job.rows_valid=inserted;job.rows_imported=inserted;job.rows_rejected=rejected;job.rejected_rows_json=examples;job.status="COMPLETED";job.completed_at=utcnow();audit(db,"import.completed",actor=job.user_id,resource_type="import",resource_id=job.id,inserted=inserted,rejected=rejected);db.commit();_cleanup(job);return True
        except InterruptedError:
            db.rollback();job=db.get(ImportJob,job_id);job.status="CANCELLED";job.completed_at=utcnow();job.executor_id=None;audit(db,"import.cancelled",actor=job.user_id,resource_type="import",resource_id=job.id);db.commit();_cleanup(job);return False
        except Exception as error:
            db.rollback();job=db.get(ImportJob,job_id);job.status="FAILED";job.failure_reason=str(error)[:500];job.rows_imported=0;job.rows_rejected=rejected;job.rejected_rows_json=examples;job.completed_at=utcnow();audit(db,"worker.import_failed",outcome="failure",actor=job.user_id,resource_type="import",resource_id=job.id);db.commit();_cleanup(job);return False

def _cleanup(job):
    try:
        path=storage_path(job.storage_id)
        if path.is_file() and not path.is_symlink():path.unlink()
    except OSError:pass
    try:cancellation_path(job.storage_id).unlink(missing_ok=True)
    except OSError:pass

def process_next(executor_id=None):
    executor_id=executor_id or f"worker-{os.getpid()}";job_id=claim_next(executor_id);return execute(job_id,executor_id) if job_id else None

def run_forever(poll_seconds=1):
    recover_stale_jobs();executor=f"worker-{os.getpid()}"
    while True:
        if process_next(executor) is None:time.sleep(poll_seconds)
if __name__=="__main__":run_forever()
