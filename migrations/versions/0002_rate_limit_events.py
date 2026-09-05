"""Add durable abuse-protection events."""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

def upgrade():
    # 0001 used the then-current metadata snapshot; tolerate fresh installs where
    # the new model is therefore already present while still upgrading deployed DBs.
    if "rate_limit_events" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "rate_limit_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("subject_hash", sa.String(64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_rate_limit_events_action", "rate_limit_events", ["action"])
    op.create_index("ix_rate_limit_events_subject_hash", "rate_limit_events", ["subject_hash"])
    op.create_index("ix_rate_limit_events_occurred_at", "rate_limit_events", ["occurred_at"])
    op.create_index("ix_rate_limit_action_subject_time", "rate_limit_events", ["action", "subject_hash", "occurred_at"])

def downgrade():
    op.drop_table("rate_limit_events")
