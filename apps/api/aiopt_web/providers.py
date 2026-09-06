"""Provider-neutral connection adapters and the OpenAI implementation."""
from abc import ABC,abstractmethod
from dataclasses import asdict,dataclass
from datetime import datetime,timezone
from time import monotonic
import httpx

@dataclass(frozen=True)
class ProviderCapabilities:
    credential_validation:bool=False;model_discovery:bool=False;usage_sync:bool=False;billing_sync:bool=False;live_inference:bool=False;gateway:bool=False
@dataclass(frozen=True)
class ProviderModelInfo:
    id:str;owned_by:str|None=None;created_at:datetime|None=None;context_window:int|None=None;modalities:list[str]|None=None;capabilities:dict|None=None
class ProviderError(RuntimeError):
    def __init__(self,message,status="ERROR"):super().__init__(message);self.status=status
class ProviderAdapter(ABC):
    identifier:str;capabilities=ProviderCapabilities()
    @abstractmethod
    def validate_credentials(self,credential:str)->dict:...
    @abstractmethod
    def get_available_models(self,credential:str)->list[ProviderModelInfo]:...
    def get_connection_status(self):return {"provider":self.identifier,"capabilities":asdict(self.capabilities)}
    def collect_usage(self,*_):raise ProviderError("Usage synchronization is not supported by this credential type","NOT_AVAILABLE")
    def normalize_usage(self,value):return value
    def normalize_model(self,value):return value

class OpenAIAdapter(ProviderAdapter):
    identifier="openai";base_url="https://api.openai.com/v1"
    capabilities=ProviderCapabilities(credential_validation=True,model_discovery=True)
    def _models(self,credential):
        started=monotonic()
        try:
            response=httpx.get(f"{self.base_url}/models",headers={"Authorization":f"Bearer {credential}"},timeout=10)
        except httpx.TimeoutException as error:raise ProviderError("OpenAI validation timed out. Try again.","TIMEOUT") from error
        except httpx.HTTPError as error:raise ProviderError("OpenAI is currently unavailable. Try again.","UNAVAILABLE") from error
        if response.status_code==401:raise ProviderError("OpenAI rejected this credential.","INVALID")
        if response.status_code==403:raise ProviderError("This OpenAI credential lacks model-list permission.","INSUFFICIENT_PERMISSION")
        if response.status_code==429:raise ProviderError("OpenAI rate limited credential validation. Try again later.","RATE_LIMITED")
        if response.status_code>=500:raise ProviderError("OpenAI is currently unavailable. Try again.","UNAVAILABLE")
        if response.status_code!=200:raise ProviderError("OpenAI credential validation failed.","ERROR")
        try:return response.json().get("data",[]),round((monotonic()-started)*1000,2)
        except (ValueError,AttributeError) as error:raise ProviderError("OpenAI returned an invalid validation response.","ERROR") from error
    def validate_credentials(self,credential):
        models,latency=self._models(credential);return {"status":"CONNECTED","models_visible":len(models),"latency_ms":latency}
    def get_available_models(self,credential):
        result=[]
        models,_latency=self._models(credential)
        for item in models:
            created=item.get("created");result.append(ProviderModelInfo(id=str(item.get("id",""))[:160],owned_by=str(item.get("owned_by"))[:120] if item.get("owned_by") else None,created_at=datetime.fromtimestamp(created,tz=timezone.utc) if isinstance(created,(int,float)) else None))
        return [item for item in result if item.id]

ADAPTERS={"openai":OpenAIAdapter()}
def provider_adapter(provider:str):
    adapter=ADAPTERS.get(provider.casefold())
    if not adapter:raise ProviderError("Provider is not supported.","NOT_SUPPORTED")
    return adapter
