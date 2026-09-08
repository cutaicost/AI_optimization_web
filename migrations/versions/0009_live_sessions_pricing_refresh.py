"""Add owner live sessions and pricing refresh audit."""
from alembic import op
import sqlalchemy as sa

revision="0009";down_revision="0008";branch_labels=None;depends_on=None

def upgrade():
    inspector=sa.inspect(op.get_bind());tables=set(inspector.get_table_names())
    if "live_telemetry_sessions" not in tables:
        op.create_table("live_telemetry_sessions",sa.Column("id",sa.String(36),primary_key=True),sa.Column("user_id",sa.String(36),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("provider",sa.String(80),nullable=False),sa.Column("mode",sa.String(30),nullable=False),sa.Column("status",sa.String(20),nullable=False),sa.Column("started_at",sa.DateTime(timezone=True),nullable=False),sa.Column("stopped_at",sa.DateTime(timezone=True)),sa.Column("last_event_at",sa.DateTime(timezone=True)))
        op.create_index("ix_live_telemetry_sessions_user_id","live_telemetry_sessions",["user_id"]);op.create_index("ix_live_telemetry_sessions_status","live_telemetry_sessions",["status"]);op.create_index("ix_live_owner_status","live_telemetry_sessions",["user_id","status"])
    if "pricing_refreshes" not in tables:
        op.create_table("pricing_refreshes",sa.Column("id",sa.String(36),primary_key=True),sa.Column("admin_user_id",sa.String(36),sa.ForeignKey("users.id",ondelete="RESTRICT"),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("source",sa.String(500),nullable=False),sa.Column("providers_checked",sa.Integer(),nullable=False),sa.Column("models_checked",sa.Integer(),nullable=False),sa.Column("models_changed",sa.Integer(),nullable=False),sa.Column("models_unchanged",sa.Integer(),nullable=False),sa.Column("models_added",sa.Integer(),nullable=False),sa.Column("success",sa.Boolean(),nullable=False),sa.Column("validation_errors",sa.JSON(),nullable=False))
        op.create_index("ix_pricing_refreshes_admin_user_id","pricing_refreshes",["admin_user_id"]);op.create_index("ix_pricing_refreshes_created_at","pricing_refreshes",["created_at"])

def downgrade():
    op.drop_table("pricing_refreshes");op.drop_table("live_telemetry_sessions")
