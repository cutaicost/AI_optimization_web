"""Checksummed PostgreSQL backup/restore utility for TokenScope deployments."""
import argparse,base64,hashlib,json,os,subprocess,sys,tempfile
from datetime import datetime,timezone
from pathlib import Path
from sqlalchemy import create_engine,text
from sqlalchemy.engine import make_url
from cryptography.hazmat.primitives.ciphers import Cipher,algorithms,modes

def tools():
    root=Path(os.getenv("POSTGRES_BIN",""));suffix=".exe" if os.name=="nt" else ""
    return (root/f"pg_dump{suffix}" if root else Path(f"pg_dump{suffix}"),root/f"pg_restore{suffix}" if root else Path(f"pg_restore{suffix}"))
def connection(url):
    parsed=make_url(url);env={**os.environ}
    if parsed.password:env["PGPASSWORD"]=parsed.password
    args=["--host",parsed.host or "127.0.0.1","--port",str(parsed.port or 5432),"--username",parsed.username or "postgres","--dbname",parsed.database];return args,env
def sha256(path):
    value=hashlib.sha256()
    with path.open("rb") as source:
        while block:=source.read(1024*1024):value.update(block)
    return value.hexdigest()
def schema(url):
    with create_engine(url,pool_pre_ping=True).connect() as db:return db.scalar(text("select version_num from alembic_version"))
def manifest_path(path):return path.with_suffix(path.suffix+".json")
def key():
    try:value=base64.urlsafe_b64decode(os.environ["BACKUP_ENCRYPTION_KEY"])
    except Exception as error:raise RuntimeError("BACKUP_ENCRYPTION_KEY must be deployment-injected base64") from error
    if len(value)!=32:raise RuntimeError("BACKUP_ENCRYPTION_KEY must decode to 32 bytes")
    return value
def encrypt(source,target):
    nonce=os.urandom(12);cipher=Cipher(algorithms.AES(key()),modes.GCM(nonce)).encryptor()
    with source.open("rb") as incoming,target.open("wb") as outgoing:
        outgoing.write(b"TSBK1"+nonce)
        while block:=incoming.read(1024*1024):outgoing.write(cipher.update(block))
        outgoing.write(cipher.finalize()+cipher.tag)
def decrypt(source,target):
    with source.open("rb") as incoming:
        if incoming.read(5)!=b"TSBK1":raise RuntimeError("Backup encryption header is invalid")
        nonce=incoming.read(12);incoming.seek(-16,2);tag=incoming.read(16);end=incoming.tell()-16;incoming.seek(17);cipher=Cipher(algorithms.AES(key()),modes.GCM(nonce,tag)).decryptor()
        with target.open("wb") as outgoing:
            while incoming.tell()<end:
                block=incoming.read(min(1024*1024,end-incoming.tell()));outgoing.write(cipher.update(block))
            outgoing.write(cipher.finalize())
def backup(url,path,recovery=False):
    dump,_=tools();args,env=connection(url);path.parent.mkdir(parents=True,exist_ok=True);temporary=path.with_suffix(path.suffix+".plain")
    try:subprocess.run([str(dump),*args,"--format=custom","--no-owner","--no-privileges","--file",str(temporary)],env=env,check=True);encrypt(temporary,path)
    finally:temporary.unlink(missing_ok=True)
    manifest={"format":"tokenscope-postgresql-v1","created_at":datetime.now(timezone.utc).isoformat(),"schema_version":schema(url),"sha256":sha256(path),"recovery":recovery,"encrypted":"AES-256-GCM"};manifest_path(path).write_text(json.dumps(manifest,indent=2),encoding="utf-8");return manifest
def verify(path,expected_schema=None):
    try:manifest=json.loads(manifest_path(path).read_text(encoding="utf-8"))
    except Exception as error:raise RuntimeError("Backup manifest is missing or corrupt") from error
    if manifest.get("format")!="tokenscope-postgresql-v1" or manifest.get("sha256")!=sha256(path):raise RuntimeError("Backup checksum mismatch")
    if expected_schema and manifest.get("schema_version")!=expected_schema:raise RuntimeError("Backup schema mismatch")
    return manifest
def restore(url,path,recovery_path):
    expected=schema(url);verify(path,expected);backup(url,recovery_path,True);_,restore_tool=tools();args,env=connection(url);temporary=path.with_suffix(path.suffix+".restore")
    try:decrypt(path,temporary);subprocess.run([str(restore_tool),*args,"--clean","--if-exists","--no-owner","--no-privileges","--single-transaction",str(temporary)],env=env,check=True)
    finally:temporary.unlink(missing_ok=True)
def main():
    parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest="command",required=True)
    create=sub.add_parser("backup");create.add_argument("path",type=Path)
    check=sub.add_parser("verify");check.add_argument("path",type=Path)
    load=sub.add_parser("restore");load.add_argument("path",type=Path);load.add_argument("--recovery",type=Path,required=True)
    args=parser.parse_args();url=os.environ.get("DATABASE_URL")
    if not url or not url.startswith("postgresql"):parser.error("DATABASE_URL must reference PostgreSQL")
    try:
        if args.command=="backup":print(json.dumps(backup(url,args.path)))
        elif args.command=="verify":print(json.dumps(verify(args.path)))
        else:restore(url,args.path,args.recovery);print("restore complete")
    except Exception as error:print(str(error),file=sys.stderr);return 1
    return 0
if __name__=="__main__":raise SystemExit(main())
