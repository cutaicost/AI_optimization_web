"""Add durable worker registration and import claim leases."""
from alembic import op
import sqlalchemy as sa
revision="0005";down_revision="0004";branch_labels=None;depends_on=None
def upgrade():
    columns={x["name"] for x in sa.inspect(op.get_bind()).get_columns("import_jobs")}
    if "lease_expires_at" not in columns:
        with op.batch_alter_table("import_jobs") as batch:batch.add_column(sa.Column("lease_expires_at",sa.DateTime(timezone=True)))
    indexes={x["name"] for x in sa.inspect(op.get_bind()).get_indexes("import_jobs")}
    if "ix_import_jobs_lease_expires_at" not in indexes:op.create_index("ix_import_jobs_lease_expires_at","import_jobs",["lease_expires_at"])
    if "worker_instances" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table("worker_instances",sa.Column("worker_id",sa.String(64),primary_key=True),sa.Column("started_at",sa.DateTime(timezone=True),nullable=False),sa.Column("last_heartbeat_at",sa.DateTime(timezone=True),nullable=False),sa.Column("hostname",sa.String(120),nullable=False),sa.Column("current_job_id",sa.String(36)),sa.Column("status",sa.String(20),nullable=False),sa.Column("version",sa.String(30),nullable=False));op.create_index("ix_worker_instances_last_heartbeat_at","worker_instances",["last_heartbeat_at"]);op.create_index("ix_worker_instances_current_job_id","worker_instances",["current_job_id"]);op.create_index("ix_worker_instances_status","worker_instances",["status"])
def downgrade():
    if "worker_instances" in sa.inspect(op.get_bind()).get_table_names():op.drop_table("worker_instances")
    with op.batch_alter_table("import_jobs") as batch:batch.drop_index("ix_import_jobs_lease_expires_at");batch.drop_column("lease_expires_at")
