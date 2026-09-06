"""Durable import object storage boundary.

Import code consumes stable object references through this interface. Backends that
cannot expose a local path can download into a bounded-lifetime staging file from
``materialize`` without changing parser or worker business logic.
"""
from abc import ABC,abstractmethod
from contextlib import contextmanager
import os,re,tempfile,time
from pathlib import Path

class ImportStorage(ABC):
    @abstractmethod
    def open_writer(self,reference:str):...
    @abstractmethod
    def materialize(self,reference:str):...
    @abstractmethod
    def exists(self,reference:str)->bool:...
    @abstractmethod
    def delete(self,reference:str)->None:...
    @abstractmethod
    def request_cancellation(self,reference:str)->None:...
    @abstractmethod
    def cancellation_requested(self,reference:str)->bool:...
    @abstractmethod
    def clear_cancellation(self,reference:str)->None:...
    @abstractmethod
    def cleanup_stale(self,max_age_seconds:int=86_400)->int:...

class LocalFileImportStorage(ImportStorage):
    """Filesystem implementation suitable for one host or a shared volume."""
    def __init__(self,root:Path|str|None=None):
        configured=root or os.getenv("IMPORT_STORAGE_ROOT") or os.getenv("IMPORT_TEMP_DIR")
        self.root=Path(configured) if configured else Path(tempfile.gettempdir())/"aiopt-web-imports"
        self.root.mkdir(mode=0o700,parents=True,exist_ok=True)
        if self.root.is_symlink():raise RuntimeError("Import storage is unavailable")
    def _path(self,reference,suffix=".upload"):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}",reference or ""):raise ValueError("Invalid import storage reference")
        return self.root/f"{reference}{suffix}"
    def open_writer(self,reference):return self._path(reference).open("xb")
    @contextmanager
    def materialize(self,reference):
        path=self._path(reference)
        if not path.is_file() or path.is_symlink():raise FileNotFoundError(reference)
        yield path
    def exists(self,reference):
        path=self._path(reference);return path.is_file() and not path.is_symlink()
    def delete(self,reference):self._path(reference).unlink(missing_ok=True)
    def request_cancellation(self,reference):self._path(reference,".cancel").touch(exist_ok=True)
    def cancellation_requested(self,reference):return self._path(reference,".cancel").is_file()
    def clear_cancellation(self,reference):self._path(reference,".cancel").unlink(missing_ok=True)
    def cleanup_stale(self,max_age_seconds=86_400):
        cutoff=time.time()-max_age_seconds;removed=0
        for path in self.root.glob("*.upload"):
            try:
                if path.is_file() and not path.is_symlink() and path.stat().st_mtime<cutoff:path.unlink();removed+=1
            except OSError:pass
        return removed

_storage=None
def get_import_storage():
    global _storage
    if _storage is None:_storage=LocalFileImportStorage()
    return _storage
