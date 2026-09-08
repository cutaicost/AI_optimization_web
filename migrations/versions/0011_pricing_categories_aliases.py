"""Add pricing category, lifecycle, and explicit canonical model mapping."""
from alembic import op
import sqlalchemy as sa
revision="0011";down_revision="0010";branch_labels=None;depends_on=None
def upgrade():
    columns={x["name"] for x in sa.inspect(op.get_bind()).get_columns("pricing_catalog_models")}
    with op.batch_alter_table("pricing_catalog_models") as batch:
        if "pricing_category" not in columns:batch.add_column(sa.Column("pricing_category",sa.String(40),nullable=False,server_default="UNKNOWN"))
        if "lifecycle_status" not in columns:batch.add_column(sa.Column("lifecycle_status",sa.String(30),nullable=False,server_default="UNKNOWN"))
        if "canonical_pricing_model" not in columns:batch.add_column(sa.Column("canonical_pricing_model",sa.String(160)))
def downgrade():
    with op.batch_alter_table("pricing_catalog_models") as batch:
        batch.drop_column("canonical_pricing_model");batch.drop_column("lifecycle_status");batch.drop_column("pricing_category")
