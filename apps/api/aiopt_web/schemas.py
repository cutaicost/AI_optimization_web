from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

class StrictModel(BaseModel): model_config=ConfigDict(extra="forbid",str_strip_whitespace=True)

class RegisterIn(StrictModel):
    display_name:str=Field(min_length=1,max_length=100)
    username:str=Field(min_length=3,max_length=40,pattern=r"^[A-Za-z0-9_.-]+$")
    email:EmailStr
    password:str=Field(min_length=12,max_length=128)
    confirm_password:str=Field(min_length=12,max_length=128)
    organization:str|None=Field(None,max_length=120)
    job_title:str|None=Field(None,max_length=120)
    @field_validator("email")
    @classmethod
    def normalize_email(cls,value): return str(value).casefold()
    @model_validator(mode="after")
    def passwords_match(self):
        if self.password!=self.confirm_password: raise ValueError("Passwords do not match")
        if not any(c.islower() for c in self.password) or not any(c.isupper() for c in self.password) or not any(c.isdigit() for c in self.password): raise ValueError("Password must contain upper-case, lower-case, and numeric characters")
        return self

class LoginIn(StrictModel): identity:str=Field(min_length=1,max_length=320);password:str=Field(min_length=1,max_length=128)
class PasswordChangeIn(StrictModel):
    current_password:str=Field(min_length=1,max_length=128)
    new_password:str=Field(min_length=12,max_length=128)
    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls,value):
        if not any(c.islower() for c in value) or not any(c.isupper() for c in value) or not any(c.isdigit() for c in value):
            raise ValueError("Password must contain upper-case, lower-case, and numeric characters")
        return value
class ProfileIn(StrictModel): display_name:str=Field(min_length=1,max_length=100);email:EmailStr;organization:str|None=Field(None,max_length=120);job_title:str|None=Field(None,max_length=120);preferences:dict=Field(default_factory=dict)
class AdminUserUpdateIn(StrictModel): role:str|None=Field(None,pattern=r"^(ADMIN|USER)$");is_active:bool|None=None
class EventIn(StrictModel): provider:str=Field(max_length=80);model:str=Field(max_length=160);application:str=Field(max_length=120);input_tokens:int=Field(0,ge=0);output_tokens:int=Field(0,ge=0);duration_ms:float=Field(0,ge=0);estimated_cost:float=Field(0,ge=0);metadata:dict=Field(default_factory=dict)
