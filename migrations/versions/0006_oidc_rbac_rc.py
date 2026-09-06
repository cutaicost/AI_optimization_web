"""Add generic OIDC identities and normalize enterprise roles."""
from alembic import op
import sqlalchemy as sa
revision="0006";down_revision="0005";branch_labels=None;depends_on=None
def upgrade():
    inspector=sa.inspect(op.get_bind());tables=set(inspector.get_table_names())
    op.execute("UPDATE users SET role='ANALYST' WHERE role='USER'")
    with op.batch_alter_table("users") as batch:batch.alter_column("role",server_default="ANALYST")
    if "oidc_identities" not in tables:op.create_table("oidc_identities",sa.Column("id",sa.String(36),primary_key=True),sa.Column("issuer",sa.String(500),nullable=False),sa.Column("subject",sa.String(255),nullable=False),sa.Column("user_id",sa.String(36),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("last_login_at",sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint("issuer","subject",name="uq_oidc_issuer_subject"));op.create_index("ix_oidc_identities_user_id","oidc_identities",["user_id"])
    if "oidc_login_states" not in tables:op.create_table("oidc_login_states",sa.Column("state_hash",sa.String(64),primary_key=True),sa.Column("nonce",sa.String(128),nullable=False),sa.Column("code_verifier",sa.String(128),nullable=False),sa.Column("expires_at",sa.DateTime(timezone=True),nullable=False));op.create_index("ix_oidc_login_states_expires_at","oidc_login_states",["expires_at"])
    worker_columns={x["name"] for x in inspector.get_columns("worker_instances")}
    with op.batch_alter_table("worker_instances") as batch:
        if "last_completed_job_id" not in worker_columns:batch.add_column(sa.Column("last_completed_job_id",sa.String(36)))
        if "recent_failure" not in worker_columns:batch.add_column(sa.Column("recent_failure",sa.String(200)))
    if "actor_role" not in {x["name"] for x in inspector.get_columns("audit_events")}:
        with op.batch_alter_table("audit_events") as batch:batch.add_column(sa.Column("actor_role",sa.String(20)))
    if "enterprise_settings" not in tables:op.create_table("enterprise_settings",sa.Column("key",sa.String(100),primary_key=True),sa.Column("value_json",sa.JSON(),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False),sa.Column("updated_by",sa.String(36)))
def downgrade():
    op.drop_table("enterprise_settings")
    with op.batch_alter_table("audit_events") as batch:batch.drop_column("actor_role")
    with op.batch_alter_table("worker_instances") as batch:batch.drop_column("recent_failure");batch.drop_column("last_completed_job_id")
    op.drop_table("oidc_login_states");op.drop_table("oidc_identities");op.execute("UPDATE users SET role='USER' WHERE role='ANALYST'")
    with op.batch_alter_table("users") as batch:batch.alter_column("role",server_default=None)
