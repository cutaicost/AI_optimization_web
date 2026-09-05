"""Initial multi-user web foundation."""
from alembic import op
from apps.api.aiopt_web.database import Base
from apps.api.aiopt_web import models  # noqa: F401
revision="0001";down_revision=None;branch_labels=None;depends_on=None
def upgrade():Base.metadata.create_all(bind=op.get_bind())
def downgrade():Base.metadata.drop_all(bind=op.get_bind())
