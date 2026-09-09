"""Database-backed leased import worker. Run as a dedicated process."""
import os,socket,threading,time,logging
from datetime import timedelta
from sqlalchemy import delete,insert,or_,select,update
from sqlalchemy.exc import SQLAlchemyError
from .auth import audit
from .config import VERSION
from .database import SessionLocal,engine
from .models import ImportJob,TelemetryEvent,WorkerInstance
from .security import utcnow
from .import_storage import get_import_storage
from .telemetry_import import ImportFailure,map_row,rows
from .cost_engine import CostCalculator

ACTIVE=("PREPARING","IMPORTING","CANCELLING");LEASE_SECONDS=int(os.getenv("WORKER_LEASE_SECONDS","90"));HEARTBEAT_SECONDS=int(os.getenv("WORKER_HEARTBEAT_SECONDS","15"))
logger=logging.getLogger("aiopt.import.worker")
def register_worker(worker_id,status="STARTING"):
    with SessionLocal() as db:
        row=db.get(WorkerInstance,worker_id);now=utcnow()
        if row:row.started_at=now;row.last_heartbeat_at=now;row.hostname=socket.gethostname()[:120];row.status=status;row.current_job_id=None;row.version=VERSION
        else:db.add(WorkerInstance(worker_id=worker_id,started_at=now,last_heartbeat_at=now,hostname=socket.gethostname()[:120],status=status,version=VERSION))
        db.commit()
def heartbeat(worker_id,status="IDLE",job_id=None,renew_lease=True):
    try:
        with SessionLocal() as db:
            now=utcnow();row=db.get(WorkerInstance,worker_id)
            if not row:db.add(WorkerInstance(worker_id=worker_id,started_at=now,last_heartbeat_at=now,hostname=socket.gethostname()[:120],status=status,current_job_id=job_id,version=VERSION))
            else:row.last_heartbeat_at=now;row.status=status;row.current_job_id=job_id;row.version=VERSION
            if job_id and renew_lease:db.execute(update(ImportJob).where(ImportJob.id==job_id,ImportJob.executor_id==worker_id,ImportJob.status.in_(ACTIVE)).values(lease_expires_at=now+timedelta(seconds=LEASE_SECONDS)))
            db.commit()
    except SQLAlchemyError:pass
def recover_stale_jobs(max_age_minutes=None):
    with SessionLocal() as db:
        now=utcnow();fallback=timedelta(minutes=max_age_minutes) if max_age_minutes is not None else timedelta(seconds=LEASE_SECONDS);jobs=db.scalars(select(ImportJob).where(ImportJob.status.in_(ACTIVE),or_(ImportJob.lease_expires_at<now,ImportJob.lease_expires_at.is_(None)&(ImportJob.claimed_at<now-fallback)))).all();requeued=cancelled=0
        for job in jobs:
            if job.status=="CANCELLING" or get_import_storage().cancellation_requested(job.storage_id):job.status="CANCELLED";job.completed_at=now;cancelled+=1;_cleanup(job)
            else:job.status="QUEUED";job.failure_reason="Recovered after expired worker lease";requeued+=1
            job.executor_id=None;job.claimed_at=None;job.lease_expires_at=None
        db.execute(update(WorkerInstance).where(WorkerInstance.last_heartbeat_at<now-timedelta(seconds=LEASE_SECONDS)).values(status="OFFLINE",current_job_id=None));db.commit();return requeued+cancelled
def claim_next(executor_id):
    with SessionLocal() as db:
        query=select(ImportJob).where(ImportJob.status=="QUEUED",ImportJob.executor_id.is_(None)).order_by(ImportJob.updated_at).limit(1)
        if engine.dialect.name=="postgresql":query=query.with_for_update(skip_locked=True)
        job=db.scalar(query)
        if not job:return None
        now=utcnow()
        if engine.dialect.name=="postgresql":job.status="PREPARING";job.executor_id=executor_id;job.claimed_at=now;job.started_at=now;job.lease_expires_at=now+timedelta(seconds=LEASE_SECONDS);changed=1
        else:changed=db.execute(update(ImportJob).where(ImportJob.id==job.id,ImportJob.status=="QUEUED",ImportJob.executor_id.is_(None)).values(status="PREPARING",executor_id=executor_id,claimed_at=now,started_at=now,lease_expires_at=now+timedelta(seconds=LEASE_SECONDS))).rowcount
        db.commit()
        if changed==1:logger.info("import job claimed job_id=%s executor_id=%s",job.id,executor_id)
        return job.id if changed==1 else None
def execute(job_id,executor_id):
    inserted=rejected=0;examples=[];batch=[];stop=threading.Event();progress={"at":time.monotonic()};pulse=threading.Thread(target=lambda:_pulse(stop,executor_id,job_id,progress),daemon=True);pulse.start()
    try:
        with SessionLocal() as db:
            job=db.get(ImportJob,job_id)
            if not job or job.executor_id!=executor_id or job.status!="PREPARING":return False
            storage=get_import_storage();job.status="IMPORTING";db.commit();logger.info("import processor started job_id=%s status=IMPORTING",job.id)
            try:
                with storage.materialize(job.storage_id) as path:
                    logger.info("import source opened job_id=%s",job.id)
                    db.execute(delete(TelemetryEvent).where(TelemetryEvent.import_job_id==job.id))
                    calculator=CostCalculator(db)
                    for number,row in enumerate(rows(path,job.file_format,job.detected_encoding or "utf-8",job.detected_delimiter or ","),1):
                        if number==1:logger.info("import first chunk read job_id=%s validation_started=true",job.id)
                        if number%250==0 and storage.cancellation_requested(job.storage_id):raise InterruptedError
                        try:
                            data=map_row(row,job.mapping);has_recorded=any(target=="estimated_cost" and str(row.get(source) or "").strip() for source,target in job.mapping.items());recorded=data["estimated_cost"] if has_recorded else None;calculated=calculator.calculate(data["provider"],data["model"],data["timestamp"],data["input_tokens"],data["output_tokens"])
                            if calculated:data["estimated_cost"]=float(calculated.total_cost)
                            batch.append({"user_id":job.user_id,"organization_id":None,"import_job_id":job.id,"source":"import","provenance":"IMPORTED","provider_recorded_cost":recorded,"calculated_cost":calculated.total_cost if calculated else None,"pricing_record_id":calculated.pricing_record_id if calculated else None,"metadata_json":{},**data});inserted+=1
                            if len(batch)>=1000:db.execute(insert(TelemetryEvent),batch);batch.clear();progress["at"]=time.monotonic();_update_progress(job.id,executor_id,inserted+rejected);logger.info("import progress job_id=%s processed=%s rejected=%s",job.id,inserted+rejected,rejected)
                        except Exception as error:
                            rejected+=1
                            if len(examples)<100:examples.append({"row_number":number,"error":str(error)[:300]})
                if batch:db.execute(insert(TelemetryEvent),batch);batch.clear()
                db.flush()
                if inserted<1:raise ImportFailure("No valid telemetry rows were available to import")
                job.rows_processed=inserted+rejected;job.rows_valid=inserted;job.rows_imported=inserted;job.rows_rejected=rejected;job.rejected_rows_json=examples;job.status="COMPLETED";job.completed_at=utcnow();job.lease_expires_at=None;worker=db.get(WorkerInstance,executor_id)
                if worker:worker.last_completed_job_id=job.id
                audit(db,"import.completed",actor=job.user_id,resource_type="import",resource_id=job.id,inserted=inserted,rejected=rejected);db.commit();logger.info("import completed job_id=%s inserted=%s rejected=%s",job.id,inserted,rejected);_cleanup(job);return True
            except InterruptedError:
                db.rollback();job=db.get(ImportJob,job_id);job.status="CANCELLED";job.completed_at=utcnow();job.executor_id=None;job.lease_expires_at=None;audit(db,"import.cancelled",actor=job.user_id,resource_type="import",resource_id=job.id);db.commit();_cleanup(job);return False
            except SQLAlchemyError:
                db.rollback();raise
            except Exception as error:
                logger.exception("import failed job_id=%s",job_id)
                db.rollback();job=db.get(ImportJob,job_id);job.status="FAILED";job.failure_reason=(str(error)[:500] if isinstance(error,ImportFailure) else "Import processing failed");job.rows_imported=0;job.rows_rejected=rejected;job.rejected_rows_json=examples;job.completed_at=utcnow();job.lease_expires_at=None;worker=db.get(WorkerInstance,executor_id)
                if worker:worker.recent_failure="Import failed"
                audit(db,"worker.import_failed",outcome="failure",actor=job.user_id,resource_type="import",resource_id=job.id);db.commit();_cleanup(job);return False
    finally:stop.set();pulse.join(timeout=2);heartbeat(executor_id,"IDLE")
def _pulse(stop,worker_id,job_id,progress):
    heartbeat(worker_id,"BUSY",job_id)
    while not stop.wait(HEARTBEAT_SECONDS):
        recent=time.monotonic()-progress["at"]<max(HEARTBEAT_SECONDS*3,5);heartbeat(worker_id,"BUSY",job_id,recent)
        if not recent and not worker_id.startswith("embedded"):os._exit(75)
def _update_progress(job_id,worker_id,processed):
    if engine.dialect.name!="postgresql":return
    with SessionLocal() as progress_db:progress_db.execute(update(ImportJob).where(ImportJob.id==job_id,ImportJob.executor_id==worker_id,ImportJob.status=="IMPORTING").values(rows_processed=processed));progress_db.commit()
def _cleanup(job):
    storage=get_import_storage()
    try:storage.delete(job.storage_id);storage.clear_cancellation(job.storage_id);logger.info("import cleanup completed job_id=%s",job.id)
    except OSError:logger.exception("import cleanup failed job_id=%s",job.id)
def process_next(executor_id=None):
    executor_id=executor_id or f"worker-{os.getpid()}";job_id=claim_next(executor_id);return execute(job_id,executor_id) if job_id else None
def run_forever(poll_seconds=1):
    worker=f"worker-{os.getpid()}";last_recovery=last_model_refresh_check=0
    try:
        while True:
            try:
                if not last_recovery:register_worker(worker)
                if time.monotonic()-last_recovery>=HEARTBEAT_SECONDS:recover_stale_jobs();last_recovery=time.monotonic()
                if time.monotonic()-last_model_refresh_check>=60:
                    from .pricing_api import run_scheduled_refresh_if_due
                    run_scheduled_refresh_if_due();last_model_refresh_check=time.monotonic()
                result=process_next(worker)
                if result is None:heartbeat(worker,"IDLE");time.sleep(poll_seconds)
            except SQLAlchemyError:
                last_recovery=0;time.sleep(poll_seconds)
    finally:heartbeat(worker,"STOPPING")
if __name__=="__main__":run_forever()
