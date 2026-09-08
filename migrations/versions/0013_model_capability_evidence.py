"""Evidence-backed model capability scoring foundation."""
from alembic import op
import sqlalchemy as sa

revision="0013";down_revision="0012";branch_labels=None;depends_on=None

def upgrade():
    tables=sa.inspect(op.get_bind()).get_table_names()
    if "model_skills" not in tables:
        op.create_table("model_skills",sa.Column("id",sa.String(36),primary_key=True),sa.Column("key",sa.String(80),nullable=False,unique=True),sa.Column("name",sa.String(120),nullable=False),sa.Column("description",sa.String(500)))
        op.create_index("ix_model_skills_key","model_skills",["key"],unique=True)
    if "model_capability_evidence" not in tables:
        op.create_table("model_capability_evidence",sa.Column("id",sa.String(36),primary_key=True),sa.Column("provider",sa.String(80),nullable=False),sa.Column("model_id",sa.String(160),nullable=False),sa.Column("skill_id",sa.String(36),sa.ForeignKey("model_skills.id",ondelete="CASCADE"),nullable=False),sa.Column("evaluation_name",sa.String(200),nullable=False),sa.Column("raw_score",sa.Float()),sa.Column("evaluation_max",sa.Float()),sa.Column("benchmark_weight",sa.Float(),nullable=False),sa.Column("source_type",sa.String(40),nullable=False),sa.Column("source_url",sa.String(1000),nullable=False),sa.Column("provider_reported",sa.Boolean(),nullable=False),sa.Column("independent",sa.Boolean(),nullable=False),sa.Column("evaluation_date",sa.DateTime(timezone=True),nullable=False),sa.Column("confidence",sa.String(20),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint("provider","model_id","skill_id","evaluation_name","source_url",name="uq_model_capability_evidence"))
        for column in ("provider","model_id","skill_id"):op.create_index(f"ix_model_capability_evidence_{column}","model_capability_evidence",[column])

def downgrade():
    op.drop_table("model_capability_evidence");op.drop_table("model_skills")
