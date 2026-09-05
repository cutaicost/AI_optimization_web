from datetime import datetime, timedelta, timezone
from hashlib import sha256
import secrets
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

hasher=PasswordHasher(time_cost=3,memory_cost=65536,parallelism=4,hash_len=32,salt_len=16)
def hash_password(password:str)->str:return hasher.hash(password)
def verify_password(encoded:str,password:str)->bool:
    try:return hasher.verify(encoded,password)
    except (VerifyMismatchError,InvalidHashError):return False
def opaque_token()->str:return secrets.token_urlsafe(48)
def digest(value:str)->str:return sha256(value.encode()).hexdigest()
def utcnow():return datetime.now(timezone.utc)
def expires(ttl:int):return utcnow()+timedelta(seconds=ttl)
