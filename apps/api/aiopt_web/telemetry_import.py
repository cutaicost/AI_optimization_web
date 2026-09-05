"""Bounded, streaming telemetry import helpers for server-side uploads."""
import csv
import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

MAX_FILE_SIZE=500_000_000
MAX_RECORD_CHARS=2_000_000
READ_SIZE=1_000_000
MAX_ACTIVE_IMPORTS=3
csv.field_size_limit(MAX_RECORD_CHARS)

ALIASES={
 "timestamp":["created_at","time","datetime","event_time"],"application":["app","service","application_name"],
 "provider":["vendor","provider_name"],"model":["model_name","model_id"],
 "input_tokens":["prompt_tokens","input_token_count","tokens_in"],"output_tokens":["completion_tokens","output_token_count","tokens_out"],
 "total_tokens":["tokens_total"],"estimated_cost":["estimated_total_cost","total_cost","cost"],
 "duration_ms":["latency_ms","latency","response_time"],
}
REVERSE={alias:canonical for canonical,aliases in ALIASES.items() for alias in [canonical,*aliases]}
TARGETS=set(ALIASES)

class ImportFailure(ValueError):pass

def validate_filename(filename,fmt):
    if Path(filename).name!=filename or any(x in filename for x in ("/","\\","..")):raise ImportFailure("Invalid filename")
    suffix=Path(filename).suffix.lower()
    if (fmt=="csv" and suffix!=".csv") or (fmt in {"json","jsonl"} and suffix not in {".json",".jsonl"}):raise ImportFailure("Filename does not match the selected format")

def storage_root():
    root=Path(os.getenv("IMPORT_TEMP_DIR") or tempfile.gettempdir())/"aiopt-web-imports";root.mkdir(mode=0o700,parents=True,exist_ok=True)
    if root.is_symlink():raise ImportFailure("Import storage is unavailable")
    return root

def storage_path(storage_id):return storage_root()/f"{storage_id}.upload"

def cleanup_stale_files(max_age_seconds=86_400):
    cutoff=time.time()-max_age_seconds;removed=0
    for path in storage_root().glob("*.upload"):
        try:
            if path.is_file() and not path.is_symlink() and path.stat().st_mtime<cutoff:path.unlink();removed+=1
        except OSError:pass
    return removed

def normalize_header(value):return str(value).strip().casefold().replace(" ","_")
def auto_mapping(headers):return {h:REVERSE[n] for h in headers if (n:=normalize_header(h)) in REVERSE}

def encoding(path):
    with path.open("rb") as handle:sample=handle.read(64_000)
    for value in ("utf-8-sig","utf-16","latin-1"):
        try:sample.decode(value);return value
        except UnicodeDecodeError:pass
    raise ImportFailure("Unsupported text encoding")

def delimiter(path,enc):
    with path.open("r",encoding=enc,errors="strict") as handle:sample=handle.read(10_000)
    try:return csv.Sniffer().sniff(sample,delimiters=",;\t|").delimiter
    except csv.Error:return ","

def rows(path,fmt,enc,sep=","):
    with path.open("r",encoding=enc,errors="strict",newline="") as handle:
        if fmt=="csv":
            reader=csv.DictReader(handle,delimiter=sep)
            if not reader.fieldnames:raise ImportFailure("CSV has no header row")
            for row in reader:
                if None in row:raise ImportFailure("CSV row has more fields than its header")
                if any(str(v or "").strip() for v in row.values()):yield row
            return
        first=""
        while not first:
            first=handle.read(1)
            if not first:raise ImportFailure("JSON file is empty")
            first=first.strip()
        handle.seek(0)
        if first=="[":
            decoder=json.JSONDecoder();buffer="";started=False;eof=False
            while True:
                if not eof and len(buffer)<64_000:block=handle.read(64_000);eof=not block;buffer+=block
                buffer=buffer.lstrip()
                if not started:buffer=buffer[1:];started=True
                buffer=buffer.lstrip()
                if buffer.startswith(","):buffer=buffer[1:].lstrip()
                if buffer.startswith("]"):return
                try:item,end=decoder.raw_decode(buffer)
                except json.JSONDecodeError as error:
                    if eof or len(buffer)>MAX_RECORD_CHARS:raise ImportFailure("Invalid or oversized JSON record") from error
                    continue
                if not isinstance(item,dict):raise ImportFailure("Each JSON record must be an object")
                yield item;buffer=buffer[end:]
        else:
            for line in handle:
                if len(line)>MAX_RECORD_CHARS:raise ImportFailure("A source record exceeds 2 MB")
                if not line.strip():continue
                try:item=json.loads(line)
                except json.JSONDecodeError as error:raise ImportFailure("Invalid JSON line") from error
                if not isinstance(item,dict):raise ImportFailure("Each JSON line must be an object")
                yield item

def map_row(row,mapping):
    data={}
    for source,target in mapping.items():
        if target not in TARGETS:continue
        value=row.get(source)
        if value is None or str(value).strip()=="":continue
        if target in {"input_tokens","output_tokens","total_tokens"}:value=int(value)
        elif target in {"estimated_cost","duration_ms"}:value=float(value)
        elif target=="timestamp":
            value=datetime.fromisoformat(str(value).replace("Z","+00:00"))
            if value.tzinfo is None:value=value.replace(tzinfo=timezone.utc)
        else:value=str(value).strip()
        data[target]=value
    for field in ("application","provider","model"):
        if not data.get(field):raise ImportFailure(f"Missing required field: {field}")
    for field in ("input_tokens","output_tokens"):
        if data.get(field,0)<0:raise ImportFailure(f"{field} cannot be negative")
    data.setdefault("timestamp",datetime.now(timezone.utc));data.setdefault("input_tokens",0);data.setdefault("output_tokens",0)
    data["total_tokens"]=data.get("total_tokens",data["input_tokens"]+data["output_tokens"])
    data.setdefault("estimated_cost",0.0);data.setdefault("duration_ms",0.0)
    return data
