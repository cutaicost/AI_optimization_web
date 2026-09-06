"""Durable worker state and advanced owner-scoped product entities."""
from alembic import op
import sqlalchemy as sa
revision="0004";down_revision="0003";branch_labels=None;depends_on=None
def add_missing(table,columns):
    existing={x["name"] for x in sa.inspect(op.get_bind()).get_columns(table)}
    with op.batch_alter_table(table) as batch:
        for column in columns:
            if column.name not in existing:batch.add_column(column)
def upgrade():
    add_missing("import_jobs",[sa.Column("started_at",sa.DateTime(timezone=True)),sa.Column("executor_id",sa.String(64)),sa.Column("claimed_at",sa.DateTime(timezone=True))])
    indexes={x["name"] for x in sa.inspect(op.get_bind()).get_indexes("import_jobs")}
    if "ix_import_jobs_executor_id" not in indexes:op.create_index("ix_import_jobs_executor_id","import_jobs",["executor_id"])
    add_missing("budgets",[sa.Column("period",sa.String(20),nullable=False,server_default="monthly"),sa.Column("warning_threshold",sa.Float(),nullable=False,server_default="80"),sa.Column("is_active",sa.Boolean(),nullable=False,server_default=sa.true())])
    add_missing("forecast_runs",[sa.Column("organization_id",sa.String(36)),sa.Column("parameters",sa.JSON()),sa.Column("source_start",sa.DateTime(timezone=True)),sa.Column("source_end",sa.DateTime(timezone=True))])
    add_missing("integrations",[sa.Column("secret_reference",sa.String(200)),sa.Column("created_at",sa.DateTime(timezone=True))])
    if "scenario_runs" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table("scenario_runs",sa.Column("id",sa.String(36),primary_key=True),sa.Column("user_id",sa.String(36),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("organization_id",sa.String(36)),sa.Column("parameters",sa.JSON(),nullable=False),sa.Column("result",sa.JSON(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False));op.create_index("ix_scenario_runs_user_id","scenario_runs",["user_id"]);op.create_index("ix_scenario_runs_organization_id","scenario_runs",["organization_id"])
def downgrade():
    if "scenario_runs" in sa.inspect(op.get_bind()).get_table_names():op.drop_table("scenario_runs")
    forecast_indexes={x["name"] for x in sa.inspect(op.get_bind()).get_indexes("forecast_runs")}
    if "ix_forecast_runs_organization_id" in forecast_indexes:op.drop_index("ix_forecast_runs_organization_id",table_name="forecast_runs")
    for table,names in (("integrations",["created_at","secret_reference"]),("forecast_runs",["source_end","source_start","parameters","organization_id"]),("budgets",["is_active","warning_threshold","period"]),("import_jobs",["claimed_at","executor_id","started_at"])):
        with op.batch_alter_table(table) as batch:
            if table=="import_jobs":batch.drop_index("ix_import_jobs_executor_id")
            for name in names:batch.drop_column(name)
