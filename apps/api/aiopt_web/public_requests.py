"""Public demo/account-access intake plus platform-admin ticket browsing.

Requests never create an account, session, organization, or provider connection.
They are stored as durable request records in AuditEvent metadata so this feature
does not collide with the in-progress tenant ownership migration.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import audit, enforce_rate_limit, require_csrf, require_platform_admin
from .database import db_session
from .models import AuditEvent, User

router = APIRouter(prefix="/api/v1/public")
admin_router = APIRouter(prefix="/api/v1/platform/request-tickets")

TICKET_STATUSES = {"NEW", "CONTACTED", "QUALIFIED", "SCHEDULED", "APPROVED", "DENIED", "CLOSED"}


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


class TicketUpdateIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    status: str = Field(pattern=r"^(NEW|CONTACTED|QUALIFIED|SCHEDULED|APPROVED|DENIED|CLOSED)$")
    admin_notes: str | None = Field(None, max_length=3000)


def _ticket_number(row: AuditEvent) -> str:
    return f"REQ-{row.id.replace('-', '')[:8].upper()}"


def _ticket(row: AuditEvent) -> dict:
    data = dict(row.metadata_json or {})
    return {
        "id": row.id,
        "ticket_number": data.get("ticket_number") or _ticket_number(row),
        "request_type": data.get("request_type", "DEMO" if row.action == "public.demo_requested" else "ACCESS"),
        "status": data.get("status", "NEW"),
        "name": data.get("name"),
        "email": data.get("email"),
        "company": data.get("company"),
        "role": data.get("role"),
        "ai_spend_range": data.get("ai_spend_range"),
        "preferred_contact": data.get("preferred_contact", "Email"),
        "providers": data.get("providers"),
        "goals": data.get("goals"),
        "admin_notes": data.get("admin_notes"),
        "created_at": row.timestamp,
        "updated_at": data.get("updated_at") or row.timestamp,
        "updated_by": data.get("updated_by"),
    }


def _request_rows(db: Session):
    return db.scalars(
        select(AuditEvent)
        .where(
            AuditEvent.resource_type == "public_request",
            AuditEvent.action.in_(["public.demo_requested", "public.access_requested"]),
        )
        .order_by(AuditEvent.timestamp.desc())
        .limit(500)
    ).all()


@router.post("/requests", status_code=202)
def create_public_request(payload: PublicRequestIn, request: Request, db: Session = Depends(db_session)):
    if payload.website:
        return {"accepted": True}
    host = request.client.host if request.client else "unknown"
    enforce_rate_limit(db, "public_access_request", host, 8, 60)
    row = AuditEvent(
        action="public.demo_requested" if payload.request_type == "DEMO" else "public.access_requested",
        outcome="success",
        resource_type="public_request",
        metadata_json={
            "request_type": payload.request_type,
            "status": "NEW",
            "name": payload.name,
            "email": payload.email,
            "company": payload.company,
            "role": payload.role,
            "ai_spend_range": payload.ai_spend_range,
            "preferred_contact": payload.preferred_contact or "Email",
            "providers": payload.providers,
            "goals": payload.goals,
        },
    )
    db.add(row)
    db.flush()
    row.metadata_json = {**row.metadata_json, "ticket_number": _ticket_number(row)}
    db.commit()
    return {"accepted": True, "ticket_number": _ticket_number(row)}


@admin_router.get("")
def list_request_tickets(
    status: str | None = None,
    request_type: str | None = None,
    _: User = Depends(require_platform_admin),
    db: Session = Depends(db_session),
):
    if status and status not in TICKET_STATUSES:
        raise HTTPException(400, "Invalid ticket status")
    if request_type and request_type not in {"DEMO", "ACCESS"}:
        raise HTTPException(400, "Invalid request type")
    items = [_ticket(row) for row in _request_rows(db)]
    new_count = sum(item["status"] == "NEW" for item in items)
    if status:
        items = [item for item in items if item["status"] == status]
    if request_type:
        items = [item for item in items if item["request_type"] == request_type]
    return {"items": items, "new_count": new_count, "total": len(_request_rows(db))}


@admin_router.get("/{ticket_id}")
def get_request_ticket(ticket_id: str, _: User = Depends(require_platform_admin), db: Session = Depends(db_session)):
    row = db.get(AuditEvent, ticket_id)
    if not row or row.resource_type != "public_request" or row.action not in {"public.demo_requested", "public.access_requested"}:
        raise HTTPException(404, "Request ticket not found")
    return {"ticket": _ticket(row)}


@admin_router.patch("/{ticket_id}", dependencies=[Depends(require_csrf)])
def update_request_ticket(
    ticket_id: str,
    payload: TicketUpdateIn,
    admin: User = Depends(require_platform_admin),
    db: Session = Depends(db_session),
):
    row = db.get(AuditEvent, ticket_id)
    if not row or row.resource_type != "public_request" or row.action not in {"public.demo_requested", "public.access_requested"}:
        raise HTTPException(404, "Request ticket not found")
    metadata = dict(row.metadata_json or {})
    previous_status = metadata.get("status", "NEW")
    metadata.update({
        "status": payload.status,
        "admin_notes": payload.admin_notes or None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": admin.username,
        "ticket_number": metadata.get("ticket_number") or _ticket_number(row),
    })
    row.metadata_json = metadata
    audit(
        db,
        "public_request.ticket_updated",
        actor=admin.id,
        resource_type="request_ticket_action",
        resource_id=row.id,
        previous_status=previous_status,
        status=payload.status,
    )
    db.commit()
    return {"ticket": _ticket(row)}
