"""Authenticated encryption for per-owner provider credentials."""
import base64,os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

class CredentialConfigurationError(RuntimeError):pass

def _master_key():
    encoded=os.getenv("PROVIDER_CREDENTIAL_MASTER_KEY","")
    try:key=base64.urlsafe_b64decode(encoded+"="*(-len(encoded)%4))
    except Exception as error:raise CredentialConfigurationError("Provider credential encryption is not configured") from error
    if len(key)!=32:raise CredentialConfigurationError("Provider credential encryption is not configured")
    return key

def encrypt_credential(value:str,owner_id:str,provider:str,key_version:int=1)->str:
    nonce=os.urandom(12);aad=f"{owner_id}:{provider}:{key_version}".encode();encrypted=AESGCM(_master_key()).encrypt(nonce,value.encode(),aad)
    return base64.urlsafe_b64encode(nonce+encrypted).decode()

def decrypt_credential(value:str,owner_id:str,provider:str,key_version:int=1)->str:
    raw=base64.urlsafe_b64decode(value);aad=f"{owner_id}:{provider}:{key_version}".encode()
    return AESGCM(_master_key()).decrypt(raw[:12],raw[12:],aad).decode()
