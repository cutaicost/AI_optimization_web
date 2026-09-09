"""Opt-in preservation test from the pre-RC 0005 schema to current head."""
import os,subprocess,sys
import pytest
from sqlalchemy import create_engine,text
if os.getenv("RUN_POSTGRES_UPGRADE")!="1":pytest.skip("opt-in PostgreSQL upgrade test",allow_module_level=True)
URL=os.environ["DATABASE_URL"].replace("postgresql://","postgresql+psycopg://",1)
def alembic(*args):subprocess.run([sys.executable,"-m","alembic",*args],env=os.environ,check=True,capture_output=True,text=True)
def test_0005_upgrade_preserves_enterprise_data_and_failed_ddl_rolls_back():
    engine=create_engine(URL)
    with engine.begin() as db:
        db.execute(text("drop schema public cascade"));db.execute(text("create schema public"))
    alembic("upgrade","head");alembic("downgrade","0005")
    with engine.begin() as db:
        db.execute(text("insert into users(id,username,email,display_name,password_hash,role,is_active,must_change_password,preferences,created_at,updated_at) values ('u','preuser','pre@example.com','Pre','hash','USER',true,false,'{}',now(),now())"))
        db.execute(text("insert into telemetry_events(id,user_id,timestamp,provider,model,application,input_tokens,output_tokens,total_tokens,duration_ms,estimated_cost,metadata_json,source,created_at) values ('t','u',now(),'p','m','a',1,2,3,4,5,'{}','api',now())"))
        db.execute(text("insert into budgets(id,user_id,name,monthly_amount,period,warning_threshold,is_active,created_at) values ('b','u','budget',10,'monthly',80,true,now())"));db.execute(text("insert into integrations(id,user_id,name,kind,configuration,secret_reference,created_at) values ('i','u','integration','generic','{}','ENV_REF',now())"));db.execute(text("insert into cloud_provider_configs(id,user_id,provider,credential_reference) values ('c','u','provider','ENV_REF')"));db.execute(text("insert into price_overrides(id,user_id,provider,model,input_price,output_price) values ('p','u','provider','model',1,2)"));db.execute(text("insert into model_evaluations(id,user_id,model,metric,score,created_at) values ('e','u','model','quality',.9,now())"));db.execute(text("insert into import_jobs(id,user_id,filename,file_size,file_format,storage_id,status,rows_total,rows_processed,rows_valid,rows_imported,rows_rejected,mapping,sample_rows,rejected_rows_json,created_at,updated_at) values ('j','u','x.csv',1,'csv','ref','COMPLETED',1,1,1,1,0,'{}','[]','[]',now(),now())"));db.execute(text("insert into audit_events(id,timestamp,actor_user_id,action,outcome,resource_type,metadata_json) values ('a',now(),'u','pre.upgrade','success','upgrade','{}')"))
    with engine.connect() as db:before={table:db.scalar(text(f"select count(*) from {table}")) for table in ("telemetry_events","budgets","integrations","cloud_provider_configs","price_overrides","model_evaluations","import_jobs","audit_events")}
    alembic("upgrade","head")
    with engine.connect() as db:
        assert db.scalar(text("select version_num from alembic_version"))=="0013";assert db.scalar(text("select role from users where id='u'"))=="ANALYST"
        for table,count in before.items():assert db.scalar(text(f"select count(*) from {table}"))==count
    try:
        with engine.begin() as db:db.execute(text("alter table users add column migration_probe integer"));db.execute(text("select * from table_that_does_not_exist"))
    except Exception:pass
    with engine.connect() as db:assert not db.scalar(text("select exists(select 1 from information_schema.columns where table_name='users' and column_name='migration_probe')"));assert db.scalar(text("select count(*) from telemetry_events"))==1
