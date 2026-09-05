"""Expand telemetry and import jobs for the owned import workflow."""
from alembic import op
import sqlalchemy as sa

revision="0003"
down_revision="0002"
branch_labels=None
depends_on=None

def upgrade():
    inspector=sa.inspect(op.get_bind())
    telemetry={c["name"] for c in inspector.get_columns("telemetry_events")}
    with op.batch_alter_table("telemetry_events") as batch:
        if "source" not in telemetry:batch.add_column(sa.Column("source",sa.String(50),nullable=False,server_default="api"))
        if "import_job_id" not in telemetry:batch.add_column(sa.Column("import_job_id",sa.String(36),nullable=True))
        if "created_at" not in telemetry:batch.add_column(sa.Column("created_at",sa.DateTime(timezone=True),nullable=True))
    indexes={x["name"] for x in sa.inspect(op.get_bind()).get_indexes("telemetry_events")}
    for name,columns in (("ix_telemetry_events_import_job_id",["import_job_id"]),("ix_telemetry_owner_model",["user_id","model"]),("ix_telemetry_owner_provider",["user_id","provider"]),("ix_telemetry_owner_application",["user_id","application"])):
        if name not in indexes:op.create_index(name,"telemetry_events",columns)
    imports={c["name"] for c in sa.inspect(op.get_bind()).get_columns("import_jobs")}
    additions=(
      ("file_size",sa.Integer(),False,"0"),("file_format",sa.String(10),False,"csv"),("storage_id",sa.String(64),True,None),
      ("rows_processed",sa.Integer(),False,"0"),("rows_valid",sa.Integer(),False,"0"),("mapping",sa.JSON(),False,None),
      ("sample_rows",sa.JSON(),False,None),("rejected_rows_json",sa.JSON(),False,None),("detected_encoding",sa.String(20),True,None),
      ("detected_delimiter",sa.String(5),True,None),("failure_reason",sa.String(500),True,None),("updated_at",sa.DateTime(timezone=True),True,None),("completed_at",sa.DateTime(timezone=True),True,None),
    )
    with op.batch_alter_table("import_jobs") as batch:
        for name,type_,nullable,default in additions:
            if name not in imports:batch.add_column(sa.Column(name,type_,nullable=nullable,server_default=default))
    connection=op.get_bind();connection.execute(sa.text("UPDATE import_jobs SET storage_id = id WHERE storage_id IS NULL"))
    unique_names={x["name"] for x in sa.inspect(connection).get_unique_constraints("import_jobs")}
    if "uq_import_jobs_storage_id" not in unique_names:
        with op.batch_alter_table("import_jobs") as batch:batch.create_unique_constraint("uq_import_jobs_storage_id",["storage_id"])
    indexes={x["name"] for x in sa.inspect(connection).get_indexes("import_jobs")}
    for name,columns in (("ix_import_owner_status",["user_id","status"]),("ix_import_owner_created",["user_id","created_at"])):
        if name not in indexes:op.create_index(name,"import_jobs",columns)

def downgrade():
    for name in ("ix_import_owner_created","ix_import_owner_status"):op.drop_index(name,table_name="import_jobs")
    with op.batch_alter_table("import_jobs") as batch:
        unique_names={x["name"] for x in sa.inspect(op.get_bind()).get_unique_constraints("import_jobs")}
        if "uq_import_jobs_storage_id" in unique_names:batch.drop_constraint("uq_import_jobs_storage_id",type_="unique")
        for name in ("completed_at","updated_at","failure_reason","detected_delimiter","detected_encoding","rejected_rows_json","sample_rows","mapping","rows_valid","rows_processed","storage_id","file_format","file_size"):batch.drop_column(name)
    for name in ("ix_telemetry_owner_application","ix_telemetry_owner_provider","ix_telemetry_owner_model","ix_telemetry_events_import_job_id"):op.drop_index(name,table_name="telemetry_events")
    with op.batch_alter_table("telemetry_events") as batch:
        batch.drop_column("created_at");batch.drop_column("import_job_id");batch.drop_column("source")
