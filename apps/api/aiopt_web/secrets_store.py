from abc import ABC,abstractmethod
import os
class SecretStore(ABC):
    @abstractmethod
    def exists(self,reference:str)->bool:...
class EnvironmentSecretStore(SecretStore):
    def exists(self,reference:str)->bool:return bool(os.getenv(reference))
secret_store=EnvironmentSecretStore()
