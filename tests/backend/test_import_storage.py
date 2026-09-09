from pathlib import Path
import pytest
from apps.api.aiopt_web.import_storage import LocalFileImportStorage

def test_local_storage_streams_materializes_cancels_and_cleans(tmp_path:Path):
    storage=LocalFileImportStorage(tmp_path);reference="abc123"
    with storage.open_writer(reference) as handle:handle.write(b"telemetry")
    assert storage.exists(reference)
    with storage.materialize(reference) as path:assert path.read_bytes()==b"telemetry"
    storage.request_cancellation(reference);assert storage.cancellation_requested(reference)
    storage.clear_cancellation(reference);assert not storage.cancellation_requested(reference)
    storage.delete(reference);assert not storage.exists(reference)

def test_local_storage_rejects_unsafe_references(tmp_path:Path):
    storage=LocalFileImportStorage(tmp_path)
    try:storage.exists("../escape")
    except ValueError:pass
    else:raise AssertionError("unsafe storage reference accepted")

def test_production_storage_requires_explicit_persistence_acknowledgement(tmp_path:Path,monkeypatch):
    monkeypatch.setenv("APP_ENV","production");monkeypatch.delenv("IMPORT_STORAGE_PERSISTENT",raising=False)
    with pytest.raises(RuntimeError,match="persistent shared volume"):LocalFileImportStorage(tmp_path)
    monkeypatch.setenv("IMPORT_STORAGE_PERSISTENT","true");assert LocalFileImportStorage(tmp_path).root==tmp_path
