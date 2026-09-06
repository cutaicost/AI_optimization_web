"""Persist sanitized provider connection telemetry."""
from alembic import op
import sqlalchemy as sa

revision="0008";down_revision="0007";branch_labels=None;depends_on=None

def upgrade():
    columns={column["name"] for column in sa.inspect(op.get_bind()).get_columns("provider_credentials")}
    with op.batch_alter_table("provider_credentials") as batch:
        if "last_connection_attempt_at" not in columns:batch.add_column(sa.Column("last_connection_attempt_at",sa.DateTime(timezone=True)))
        if "last_successful_connection_at" not in columns:batch.add_column(sa.Column("last_successful_connection_at",sa.DateTime(timezone=True)))
        if "last_telemetry_refresh_at" not in columns:batch.add_column(sa.Column("last_telemetry_refresh_at",sa.DateTime(timezone=True)))
        if "last_latency_ms" not in columns:batch.add_column(sa.Column("last_latency_ms",sa.Float()))

def downgrade():
    with op.batch_alter_table("provider_credentials") as batch:
        batch.drop_column("last_latency_ms");batch.drop_column("last_telemetry_refresh_at");batch.drop_column("last_successful_connection_at");batch.drop_column("last_connection_attempt_at")
