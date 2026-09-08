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
class AdminUserUpdateIn(StrictModel): role:str|None=Field(None,pattern=r"^(ADMIN|ANALYST|VIEWER)$");is_active:bool|None=None
class EventIn(StrictModel): provider:str=Field(max_length=80);model:str=Field(max_length=160);application:str=Field(max_length=120);input_tokens:int=Field(0,ge=0);output_tokens:int=Field(0,ge=0);cached_input_tokens:int|None=Field(None,ge=0);duration_ms:float=Field(0,ge=0);time_to_first_token_ms:float|None=Field(None,ge=0);status:str|None=Field(None,max_length=40);estimated_cost:float=Field(0,ge=0);metadata:dict=Field(default_factory=dict)

class ImportStartIn(StrictModel):
    filename:str=Field(min_length=1,max_length=255)
    file_size:int=Field(gt=0,le=500_000_000)
    format:str=Field(pattern=r"^(csv|json|jsonl)$")

class ImportCommitIn(StrictModel):
    mapping:dict[str,str]=Field(min_length=1,max_length=100)

class BudgetIn(StrictModel):
    name:str=Field(min_length=1,max_length=120);monthly_amount:float=Field(gt=0,le=1_000_000_000);period:str=Field("monthly",pattern=r"^(monthly|quarterly|annual)$");warning_threshold:float=Field(80,ge=1,le=100);is_active:bool=True
class ScenarioIn(StrictModel):
    name:str=Field(min_length=1,max_length=120);monthly_requests:int=Field(ge=0,le=1_000_000_000);input_tokens_per_request:int=Field(ge=0,le=10_000_000);output_tokens_per_request:int=Field(ge=0,le=10_000_000);input_price_per_million:float=Field(ge=0,le=1_000_000);output_price_per_million:float=Field(ge=0,le=1_000_000)
class IntegrationIn(StrictModel):
    name:str=Field(min_length=1,max_length=120);kind:str=Field(min_length=1,max_length=60,pattern=r"^[a-z0-9_.-]+$");endpoint:str|None=Field(None,max_length=500);secret_env_name:str|None=Field(None,max_length=200,pattern=r"^[A-Z][A-Z0-9_]*$")
