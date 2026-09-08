"""Public demo and account-access request intake.

Requests are recorded without creating an account, session, organization, or
provider connection. This deliberately avoids a schema migration while the
organization-ownership migration is being completed separately.
"""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from sqlalchemy.orm import Session

from .auth import enforce_rate_limit
from .database import db_session
from .models import AuditEvent

router = APIRouter(prefix="/api/v1/public")


class PublicRequestIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    request_type: str = Field(pattern=r"^(DEMO|ACCESS)$")
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    company: str | None = Field(None, max_length=120)
    role: str | None = Field(None, max_length=120)
    ai_spend_range: str | None = Field(None, max_length=80)
    preferred_contact: str | None = Field(None, max_length=80)
    providers: str | None = Field(None, max_length=300)
    goals: str = Field(min_length=1, max_length=1500)
    website: str | None = Field(None, max_length=200)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value):
        return str(value).casefold()


@router.post("/requests", status_code=202)
def create_public_request(payload: PublicRequestIn, request: Request, db: Session = Depends(db_session)):
    # Honeypot submissions get the same response without storing submitted PII.
    if payload.website:
        return {"accepted": True}
    host = request.client.host if request.client else "unknown"
    enforce_rate_limit(db, "public_access_request", host, 8, 60)
    db.add(AuditEvent(
        action="public.demo_requested" if payload.request_type == "DEMO" else "public.access_requested",
        outcome="success",
        resource_type="public_request",
        metadata_json={
            "request_type": payload.request_type,
            "name": payload.name,
            "email": payload.email,
            "company": payload.company,
            "role": payload.role,
            "ai_spend_range": payload.ai_spend_range,
            "preferred_contact": payload.preferred_contact or "Email",
            "providers": payload.providers,
            "goals": payload.goals,
        },
    ))
    db.commit()
    return {"accepted": True}
