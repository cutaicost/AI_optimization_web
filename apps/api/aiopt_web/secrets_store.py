"""Secret storage boundary: deployment environment on servers, DPAPI on Windows."""
from abc import ABC,abstractmethod
import ctypes,hashlib,os
from pathlib import Path
class SecretStore(ABC):
    @abstractmethod
    def exists(self,reference:str)->bool:...
    @abstractmethod
    def get(self,reference:str)->str|None:...
    def save(self,reference:str,value:str):raise RuntimeError("This secret store is read-only")
    def rotate(self,reference:str,value:str):self.save(reference,value)
    def delete(self,reference:str):raise RuntimeError("This secret store is read-only")
    def mask(self,reference:str):return f"{reference[:2]}***" if self.exists(reference) else None
class EnvironmentSecretStore(SecretStore):
    def exists(self,reference):return bool(reference and os.getenv(reference))
    def get(self,reference):return os.getenv(reference) if reference else None
class _Blob(ctypes.Structure):_fields_=[("length",ctypes.c_ulong),("data",ctypes.POINTER(ctypes.c_ubyte))]
def _blob(value:bytes):
    buffer=ctypes.create_string_buffer(value);return _Blob(len(value),ctypes.cast(buffer,ctypes.POINTER(ctypes.c_ubyte))),buffer
class WindowsDpapiSecretStore(SecretStore):
    """Per-user encrypted files; plaintext never reaches normal application tables."""
    def __init__(self,root=None):
        if os.name!="nt":raise RuntimeError("DPAPI is only available on Windows")
        self.root=Path(root or Path(os.getenv("LOCALAPPDATA",Path.home()))/"TokenScope"/"secrets");self.root.mkdir(parents=True,exist_ok=True)
    def _path(self,reference):
        if not reference:raise ValueError("Secret reference is required")
        return self.root/f"{hashlib.sha256(reference.encode()).hexdigest()}.dpapi"
    def _protect(self,value):
        source,keep=_blob(value);output=_Blob()
        if not ctypes.windll.crypt32.CryptProtectData(ctypes.byref(source),"TokenScope",None,None,None,1,ctypes.byref(output)):raise ctypes.WinError()
        try:return ctypes.string_at(output.data,output.length)
        finally:ctypes.windll.kernel32.LocalFree(output.data)
    def _unprotect(self,value):
        source,keep=_blob(value);output=_Blob()
        if not ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(source),None,None,None,None,1,ctypes.byref(output)):raise ctypes.WinError()
        try:return ctypes.string_at(output.data,output.length)
        finally:ctypes.windll.kernel32.LocalFree(output.data)
    def exists(self,reference):return bool(reference and self._path(reference).is_file())
    def get(self,reference):
        path=self._path(reference);return self._unprotect(path.read_bytes()).decode() if path.is_file() else None
    def save(self,reference,value):
        if not value:raise ValueError("Secret value is required")
        path=self._path(reference);temporary=path.with_suffix(".tmp");temporary.write_bytes(self._protect(value.encode()));os.replace(temporary,path)
    def delete(self,reference):self._path(reference).unlink(missing_ok=True)
def configured_secret_store():return WindowsDpapiSecretStore() if os.getenv("RUNTIME_MODE","").lower()=="desktop" and os.name=="nt" else EnvironmentSecretStore()
secret_store=configured_secret_store()
