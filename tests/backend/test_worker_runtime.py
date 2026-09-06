from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from sqlalchemy import func,select
from apps.api.aiopt_web.database import Base,SessionLocal,engine
from apps.api.aiopt_web.models import ImportJob,User,WorkerInstance
from apps.api.aiopt_web.security import utcnow
from apps.api.aiopt_web.telemetry_import import cancellation_path
from apps.api.aiopt_web.worker import LEASE_SECONDS,claim_next,heartbeat,recover_stale_jobs,register_worker
def setup_function():Base.metadata.drop_all(engine);Base.metadata.create_all(engine)
def teardown_function():Base.metadata.drop_all(engine)
def jobs(count):
    with SessionLocal() as db:
        user=User(username='runtime',email='runtime@example.com',display_name='Runtime',password_hash='x');db.add(user);db.flush()
        for index in range(count):db.add(ImportJob(user_id=user.id,filename=f'{index}.csv',file_size=1,file_format='csv',storage_id=f'runtime-{index}',status='QUEUED'))
        db.commit()
def test_heartbeat_registration_and_lease_renewal():
    jobs(1);register_worker('worker-a');job_id=claim_next('worker-a');heartbeat('worker-a','BUSY',job_id)
    with SessionLocal() as db:
        worker=db.get(WorkerInstance,'worker-a');job=db.get(ImportJob,job_id);assert worker.status=='BUSY' and worker.current_job_id==job_id;assert job.lease_expires_at is not None
def test_two_workers_claim_five_jobs_exactly_once():
    jobs(5)
    def claim(worker):return [claim_next(worker) for _ in range(5)]
    with ThreadPoolExecutor(max_workers=2) as pool:claimed=[x for group in pool.map(claim,['worker-a','worker-b']) for x in group if x]
    assert len(claimed)==5 and len(set(claimed))==5
    with SessionLocal() as db:assert db.scalar(select(func.count()).select_from(ImportJob).where(ImportJob.status=='PREPARING'))==5
def test_expired_importing_lease_requeues_and_cancelling_lease_cancels():
    jobs(2);first=claim_next('dead-a');second=claim_next('dead-b')
    with SessionLocal() as db:
        a=db.get(ImportJob,first);b=db.get(ImportJob,second);a.status='IMPORTING';b.status='CANCELLING';a.lease_expires_at=utcnow()-timedelta(seconds=1);b.lease_expires_at=utcnow()-timedelta(seconds=1);db.commit();cancellation_path(b.storage_id).touch()
    assert recover_stale_jobs()==2
    with SessionLocal() as db:assert db.get(ImportJob,first).status=='QUEUED';assert db.get(ImportJob,second).status=='CANCELLED'
