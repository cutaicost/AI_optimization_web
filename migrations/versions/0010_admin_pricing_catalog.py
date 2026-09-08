"""Separate authenticated catalog discovery from pricing data."""
from alembic import op
import sqlalchemy as sa
revision="0010";down_revision="0009";branch_labels=None;depends_on=None
def upgrade():
    columns={x["name"] for x in sa.inspect(op.get_bind()).get_columns("pricing_refreshes")}
    with op.batch_alter_table("pricing_refreshes") as batch:
        if "provider" not in columns:batch.add_column(sa.Column("provider",sa.String(80),nullable=False,server_default="openai"))
        if "provider_credential_id" not in columns:batch.add_column(sa.Column("provider_credential_id",sa.String(36)))
        if "models_retrieved" not in columns:batch.add_column(sa.Column("models_retrieved",sa.Integer(),nullable=False,server_default="0"))
        if "prices_retrieved" not in columns:batch.add_column(sa.Column("prices_retrieved",sa.Integer(),nullable=False,server_default="0"))
        if "source_type" not in columns:batch.add_column(sa.Column("source_type",sa.String(60),nullable=False,server_default="MANUAL_MAINTAINED_CATALOG"))
    if "pricing_catalog_models" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table("pricing_catalog_models",sa.Column("id",sa.String(36),primary_key=True),sa.Column("provider",sa.String(80),nullable=False),sa.Column("model_id",sa.String(160),nullable=False),sa.Column("display_name",sa.String(200),nullable=False),sa.Column("availability_status",sa.String(30),nullable=False),sa.Column("catalog_source_type",sa.String(60),nullable=False),sa.Column("catalog_source_reference",sa.String(500),nullable=False),sa.Column("discovered_by_credential_id",sa.String(36)),sa.Column("retrieved_at",sa.DateTime(timezone=True),nullable=False),sa.Column("extra_pricing_dimensions",sa.JSON(),nullable=False),sa.UniqueConstraint("provider","model_id",name="uq_pricing_catalog_provider_model"));op.create_index("ix_pricing_catalog_models_provider","pricing_catalog_models",["provider"]);op.create_index("ix_pricing_catalog_models_model_id","pricing_catalog_models",["model_id"])
def downgrade():
    op.drop_table("pricing_catalog_models")
    with op.batch_alter_table("pricing_refreshes") as batch:
        batch.drop_column("source_type");batch.drop_column("prices_retrieved");batch.drop_column("models_retrieved");batch.drop_column("provider_credential_id");batch.drop_column("provider")
