"""Opt-in PostgreSQL pg_dump/pg_restore validation against a disposable database."""
import base64,os,subprocess,sys
from pathlib import Path
import pytest
from sqlalchemy import create_engine,func,select,text
from sqlalchemy.orm import Session
if os.getenv("RUN_POSTGRES_BACKUP")!="1":pytest.skip("opt-in PostgreSQL backup test",allow_module_level=True)
from apps.api.aiopt_web.models import AuditEvent,Budget,CloudProviderConfig,EnterpriseSetting,ImportJob,Integration,ModelEvaluation,PriceOverride,TelemetryEvent,User
from apps.api.aiopt_web.security import utcnow
URL=os.environ["DATABASE_URL"];SCRIPT=Path(__file__).resolve().parents[2]/"scripts"/"postgres-backup.py"
os.environ.setdefault("BACKUP_ENCRYPTION_KEY",base64.urlsafe_b64encode(os.urandom(32)).decode())
def run(*args,check=True):return subprocess.run([sys.executable,str(SCRIPT),*map(str,args)],env=os.environ,capture_output=True,text=True,check=check)
def counts(engine):
    with Session(engine) as db:return {model.__tablename__:db.scalar(select(func.count()).select_from(model)) for model in (TelemetryEvent,Budget,Integration,CloudProviderConfig,PriceOverride,ModelEvaluation,EnterpriseSetting,AuditEvent,ImportJob)}
def test_backup_restore_populated_corruption_schema_and_recovery(tmp_path):
    engine=create_engine(URL);backup=tmp_path/"valid.dump";recovery=tmp_path/"recovery.dump"
    with Session(engine) as db:
        user=User(username="backup",email="backup@example.com",display_name="Backup",password_hash="not-a-secret",role="ADMIN");db.add(user);db.flush();db.add_all([TelemetryEvent(user_id=user.id,provider="p",model="m",application="a"),Budget(user_id=user.id,name="b",monthly_amount=1),Integration(user_id=user.id,name="i",kind="k",configuration={},secret_reference="ENV_ONLY"),CloudProviderConfig(user_id=user.id,provider="p",credential_reference="ENV_ONLY"),PriceOverride(user_id=user.id,provider="p",model="m",input_price=1,output_price=2),ModelEvaluation(user_id=user.id,model="m",metric="q",score=.9),EnterpriseSetting(key="retention",value_json={"days":90}),AuditEvent(actor_user_id=user.id,actor_role="ADMIN",action="seed",resource_type="test"),ImportJob(user_id=user.id,filename="x.csv",file_size=1,file_format="csv",storage_id="backup-ref",status="COMPLETED")]);db.commit()
    expected=counts(engine);run("backup",backup);run("verify",backup)
    with engine.begin() as db:db.execute(text("delete from telemetry_events"));db.execute(text("insert into enterprise_settings(key,value_json,updated_at) values ('extra','{}',now())"))
    run("restore",backup,"--recovery",recovery);assert counts(engine)==expected;assert recovery.exists() and recovery.with_suffix(".dump.json").exists()
    corrupt=tmp_path/"corrupt.dump";corrupt.write_bytes(backup.read_bytes()+b"corrupt");corrupt.with_suffix(".dump.json").write_bytes(backup.with_suffix(".dump.json").read_bytes());assert run("verify",corrupt,check=False).returncode!=0
    manifest=backup.with_suffix(".dump.json");original=manifest.read_text();manifest.write_text(original.replace('"schema_version": "0006"','"schema_version": "wrong"'));assert run("restore",backup,"--recovery",tmp_path/"unused.dump",check=False).returncode!=0;manifest.write_text(original)
