"""Public demo and account-access request intake.

This intentionally stores requests separately from users. A request never
creates an account, session, organization, or provider connection.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .auth import enforce_rate_limit
from .database import db_session
from .models import PublicAccessRequest

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
    # Honeypot submissions receive the same generic response so the endpoint
    # does not provide bot feedback.
    if payload.website:
        return {"accepted": True}

    host = request.client.host if request.client else "unknown"
    enforce_rate_limit(db, "public_access_request", host, 8, 60)

    # Prevent accidental rapid duplicates without revealing whether an email
    # address has previously contacted us.
    duplicate = db.scalar(
        select(PublicAccessRequest.id).where(
            func.lower(PublicAccessRequest.email) == payload.email,
            PublicAccessRequest.request_type == payload.request_type,
            PublicAccessRequest.status.in_(["NEW", "CONTACTED", "QUALIFIED", "SCHEDULED"]),
        ).limit(1)
    )
    if duplicate:
        return {"accepted": True}

    row = PublicAccessRequest(
        request_type=payload.request_type,
        name=payload.name,
        email=payload.email,
        company=payload.company or None,
        role=payload.role or None,
        ai_spend_range=payload.ai_spend_range or None,
        preferred_contact=payload.preferred_contact or "Email",
        providers=payload.providers or None,
        goals=payload.goals,
        status="NEW",
    )
    db.add(row)
    db.commit()
    return {"accepted": True}
