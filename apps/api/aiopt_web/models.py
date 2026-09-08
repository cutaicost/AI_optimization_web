from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base

def now(): return datetime.now(timezone.utc)
def identifier(): return str(uuid4())

class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    username: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(512))
    role: Mapped[str] = mapped_column(String(20), default="ANALYST", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    organization: Mapped[str | None] = mapped_column(String(120), nullable=True)
    job_title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    preferences: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user: Mapped[User] = relationship()

class OidcIdentity(Base):
    __tablename__="oidc_identities"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=identifier)
    issuer:Mapped[str]=mapped_column(String(500))
    subject:Mapped[str]=mapped_column(String(255))
    user_id:Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    last_login_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    __table_args__=(UniqueConstraint("issuer","subject",name="uq_oidc_issuer_subject"),)

class OidcLoginState(Base):
    __tablename__="oidc_login_states"
    state_hash:Mapped[str]=mapped_column(String(64),primary_key=True)
    nonce:Mapped[str]=mapped_column(String(128))
    code_verifier:Mapped[str]=mapped_column(String(128))
    expires_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),index=True)

class TelemetryEvent(Base):
    __tablename__ = "telemetry_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    organization_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    provider: Mapped[str] = mapped_column(String(80), index=True)
    model: Mapped[str] = mapped_column(String(160), index=True)
    application: Mapped[str] = mapped_column(String(120), index=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[float] = mapped_column(Float, default=0)
    estimated_cost: Mapped[float] = mapped_column(Float, default=0)
    provider_recorded_cost: Mapped[float | None] = mapped_column(Numeric(24,12), nullable=True)
    calculated_cost: Mapped[float | None] = mapped_column(Numeric(24,12), nullable=True)
    pricing_record_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    provenance: Mapped[str] = mapped_column(String(30), default="LEGACY", index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    source: Mapped[str] = mapped_column(String(50), default="api")
    import_job_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (Index("ix_telemetry_owner_time", "user_id", "timestamp"),Index("ix_telemetry_owner_model", "user_id", "model"),Index("ix_telemetry_owner_provider", "user_id", "provider"),Index("ix_telemetry_owner_application", "user_id", "application"),)

class ImportJob(Base):
    __tablename__ = "import_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    file_format: Mapped[str] = mapped_column(String(10), default="csv")
    storage_id: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(30), default="CREATED", index=True)
    rows_total: Mapped[int] = mapped_column(Integer, default=0)
    rows_processed: Mapped[int] = mapped_column(Integer, default=0)
    rows_valid: Mapped[int] = mapped_column(Integer, default=0)
    rows_imported: Mapped[int] = mapped_column(Integer, default=0)
    rows_rejected: Mapped[int] = mapped_column(Integer, default=0)
    mapping: Mapped[dict] = mapped_column(JSON, default=dict)
    sample_rows: Mapped[list] = mapped_column(JSON, default=list)
    rejected_rows_json: Mapped[list] = mapped_column(JSON, default=list)
    detected_encoding: Mapped[str | None] = mapped_column(String(20), nullable=True)
    detected_delimiter: Mapped[str | None] = mapped_column(String(5), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    executor_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    __table_args__ = (Index("ix_import_owner_status", "user_id", "status"),Index("ix_import_owner_created", "user_id", "created_at"),)

class Budget(Base):
    __tablename__ = "budgets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    monthly_amount: Mapped[float] = mapped_column(Float)
    period: Mapped[str] = mapped_column(String(20), default="monthly")
    warning_threshold: Mapped[float] = mapped_column(Float, default=80.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    actor_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    actor_role: Mapped[str | None] = mapped_column(String(20), nullable=True)
    action: Mapped[str] = mapped_column(String(100), index=True)
    outcome: Mapped[str] = mapped_column(String(20), default="success")
    resource_type: Mapped[str] = mapped_column(String(60))
    resource_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    identity_hash: Mapped[str] = mapped_column(String(64), index=True)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    successful: Mapped[bool] = mapped_column(Boolean, default=False)

class RateLimitEvent(Base):
    __tablename__ = "rate_limit_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    action: Mapped[str] = mapped_column(String(40), index=True)
    subject_hash: Mapped[str] = mapped_column(String(64), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    __table_args__ = (Index("ix_rate_limit_action_subject_time", "action", "subject_hash", "occurred_at"),)

class WorkerInstance(Base):
    __tablename__="worker_instances"
    worker_id:Mapped[str]=mapped_column(String(64),primary_key=True)
    started_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    last_heartbeat_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,index=True)
    hostname:Mapped[str]=mapped_column(String(120))
    current_job_id:Mapped[str|None]=mapped_column(String(36),nullable=True,index=True)
    status:Mapped[str]=mapped_column(String(20),default="STARTING",index=True)
    version:Mapped[str]=mapped_column(String(30))
    last_completed_job_id:Mapped[str|None]=mapped_column(String(36),nullable=True)
    recent_failure:Mapped[str|None]=mapped_column(String(200),nullable=True)

class EnterpriseSetting(Base):
    __tablename__="enterprise_settings"
    key:Mapped[str]=mapped_column(String(100),primary_key=True)
    value_json:Mapped[dict]=mapped_column(JSON,default=dict)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,onupdate=now)
    updated_by:Mapped[str|None]=mapped_column(String(36),nullable=True)

# Reserved durable entities for incremental feature migration.
class ForecastRun(Base):
    __tablename__="forecast_runs"; id:Mapped[str]=mapped_column(String(36),primary_key=True,default=identifier);user_id:Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True);organization_id:Mapped[str|None]=mapped_column(String(36),nullable=True,index=True);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now);parameters:Mapped[dict]=mapped_column(JSON,default=dict);result:Mapped[dict]=mapped_column(JSON,default=dict);source_start:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True);source_end:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
class Integration(Base):
    __tablename__="integrations";id:Mapped[str]=mapped_column(String(36),primary_key=True,default=identifier);user_id:Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True);name:Mapped[str]=mapped_column(String(120));kind:Mapped[str]=mapped_column(String(60));configuration:Mapped[dict]=mapped_column(JSON,default=dict);secret_reference:Mapped[str|None]=mapped_column(String(200),nullable=True);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class ScenarioRun(Base):
    __tablename__="scenario_runs";id:Mapped[str]=mapped_column(String(36),primary_key=True,default=identifier);user_id:Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True);organization_id:Mapped[str|None]=mapped_column(String(36),nullable=True,index=True);parameters:Mapped[dict]=mapped_column(JSON,default=dict);result:Mapped[dict]=mapped_column(JSON,default=dict);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class CloudProviderConfig(Base):
    __tablename__="cloud_provider_configs";id:Mapped[str]=mapped_column(String(36),primary_key=True,default=identifier);user_id:Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True);provider:Mapped[str]=mapped_column(String(80));credential_reference:Mapped[str|None]=mapped_column(String(120),nullable=True);__table_args__=(UniqueConstraint("user_id","provider",name="uq_provider_owner"),)
class PriceOverride(Base):
    __tablename__="price_overrides";id:Mapped[str]=mapped_column(String(36),primary_key=True,default=identifier);user_id:Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True);provider:Mapped[str]=mapped_column(String(80));model:Mapped[str]=mapped_column(String(160));input_price:Mapped[float]=mapped_column(Float);output_price:Mapped[float]=mapped_column(Float);__table_args__=(UniqueConstraint("user_id","provider","model",name="uq_price_owner_model"),)
class ModelEvaluation(Base):
    __tablename__="model_evaluations";id:Mapped[str]=mapped_column(String(36),primary_key=True,default=identifier);user_id:Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True);model:Mapped[str]=mapped_column(String(160));metric:Mapped[str]=mapped_column(String(100));score:Mapped[float]=mapped_column(Float);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class ProviderCredential(Base):
    __tablename__="provider_credentials";id:Mapped[str]=mapped_column(String(36),primary_key=True,default=identifier);user_id:Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True);provider:Mapped[str]=mapped_column(String(80));encrypted_credential:Mapped[str]=mapped_column(Text);key_version:Mapped[int]=mapped_column(Integer,default=1);masked_identifier:Mapped[str|None]=mapped_column(String(32),nullable=True);validation_status:Mapped[str]=mapped_column(String(40),default="UNKNOWN");last_validated_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True);last_connection_attempt_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True);last_successful_connection_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True);last_telemetry_refresh_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True);last_latency_ms:Mapped[float|None]=mapped_column(Float,nullable=True);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now);updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,onupdate=now);__table_args__=(UniqueConstraint("user_id","provider",name="uq_provider_credential_owner"),)
class ProviderModel(Base):
    __tablename__="provider_models";id:Mapped[str]=mapped_column(String(36),primary_key=True,default=identifier);user_id:Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True);provider:Mapped[str]=mapped_column(String(80));model_id:Mapped[str]=mapped_column(String(160));owned_by:Mapped[str|None]=mapped_column(String(120),nullable=True);provider_created_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True);context_window:Mapped[int|None]=mapped_column(Integer,nullable=True);modalities:Mapped[list|None]=mapped_column(JSON,nullable=True);capabilities:Mapped[dict|None]=mapped_column(JSON,nullable=True);last_seen_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now);__table_args__=(UniqueConstraint("user_id","provider","model_id",name="uq_provider_model_owner"),)
class PricingRecord(Base):
    __tablename__="pricing_records";id:Mapped[str]=mapped_column(String(36),primary_key=True,default=identifier);provider:Mapped[str]=mapped_column(String(80),index=True);model:Mapped[str]=mapped_column(String(160),index=True);effective_from:Mapped[datetime]=mapped_column(DateTime(timezone=True),index=True);effective_to:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True,index=True);pricing_unit:Mapped[str]=mapped_column(String(40),default="PER_MILLION_TOKENS");input_price:Mapped[float]=mapped_column(Numeric(24,12));output_price:Mapped[float]=mapped_column(Numeric(24,12));cached_input_price:Mapped[float|None]=mapped_column(Numeric(24,12),nullable=True);currency:Mapped[str]=mapped_column(String(3),default="USD");region:Mapped[str|None]=mapped_column(String(80),nullable=True);provenance:Mapped[str]=mapped_column(String(500));last_verified_at:Mapped[datetime]=mapped_column(DateTime(timezone=True));__table_args__=(UniqueConstraint("provider","model","effective_from","region",name="uq_pricing_version"),)

class LiveTelemetrySession(Base):
    __tablename__="live_telemetry_sessions"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=identifier)
    user_id:Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True)
    provider:Mapped[str]=mapped_column(String(80),default="openai")
    mode:Mapped[str]=mapped_column(String(30),default="GATEWAY")
    status:Mapped[str]=mapped_column(String(20),default="ACTIVE",index=True)
    started_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    stopped_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    last_event_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    __table_args__=(Index("ix_live_owner_status","user_id","status"),)

class PricingRefresh(Base):
    __tablename__="pricing_refreshes"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=identifier)
    admin_user_id:Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="RESTRICT"),index=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,index=True)
    source:Mapped[str]=mapped_column(String(500))
    providers_checked:Mapped[int]=mapped_column(Integer,default=0)
    models_checked:Mapped[int]=mapped_column(Integer,default=0)
    models_changed:Mapped[int]=mapped_column(Integer,default=0)
    models_unchanged:Mapped[int]=mapped_column(Integer,default=0)
    models_added:Mapped[int]=mapped_column(Integer,default=0)
    success:Mapped[bool]=mapped_column(Boolean,default=False)
    validation_errors:Mapped[list]=mapped_column(JSON,default=list)
    provider:Mapped[str]=mapped_column(String(80),default="openai")
    provider_credential_id:Mapped[str|None]=mapped_column(String(36),nullable=True)
    models_retrieved:Mapped[int]=mapped_column(Integer,default=0)
    prices_retrieved:Mapped[int]=mapped_column(Integer,default=0)
    source_type:Mapped[str]=mapped_column(String(60),default="MANUAL_MAINTAINED_CATALOG")

class PricingCatalogModel(Base):
    __tablename__="pricing_catalog_models"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=identifier)
    provider:Mapped[str]=mapped_column(String(80),index=True)
    model_id:Mapped[str]=mapped_column(String(160),index=True)
    display_name:Mapped[str]=mapped_column(String(200))
    availability_status:Mapped[str]=mapped_column(String(30),default="AVAILABLE")
    catalog_source_type:Mapped[str]=mapped_column(String(60),default="AUTHENTICATED_PROVIDER_API")
    catalog_source_reference:Mapped[str]=mapped_column(String(500))
    discovered_by_credential_id:Mapped[str|None]=mapped_column(String(36),nullable=True)
    retrieved_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    extra_pricing_dimensions:Mapped[dict]=mapped_column(JSON,default=dict)
    __table_args__=(UniqueConstraint("provider","model_id",name="uq_pricing_catalog_provider_model"),)
