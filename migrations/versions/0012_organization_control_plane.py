"""Organization control-plane foundation and safe account backfill."""
from datetime import datetime,timezone
from uuid import uuid4
from alembic import op
import sqlalchemy as sa
revision="0012";down_revision="0011";branch_labels=None;depends_on=None
def upgrade():
    # Migration 0001 historically calls current Base.metadata.create_all(), so a
    # brand-new database may already contain this revision's complete schema.
    # Existing deployed databases do not; they take the additive path below.
    inspector=sa.inspect(op.get_bind())
    if "organizations" in inspector.get_table_names() and "is_platform_admin" in {column["name"] for column in inspector.get_columns("users")}:return
    op.create_table("organizations",sa.Column("id",sa.String(36),primary_key=True),sa.Column("name",sa.String(120),nullable=False),sa.Column("slug",sa.String(140),nullable=False,unique=True),sa.Column("status",sa.String(20),nullable=False,server_default="ACTIVE"),sa.Column("plan_id",sa.String(40),nullable=False,server_default="FREE"),sa.Column("plan_status",sa.String(20),nullable=False,server_default="ACTIVE"),sa.Column("created_by",sa.String(36),sa.ForeignKey("users.id",ondelete="RESTRICT"),nullable=False),sa.Column("settings",sa.JSON(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False))
    op.create_index("ix_organizations_slug","organizations",["slug"],unique=True);op.create_index("ix_organizations_status","organizations",["status"]);op.create_index("ix_organizations_created_by","organizations",["created_by"])
    op.create_table("organization_members",sa.Column("id",sa.String(36),primary_key=True),sa.Column("organization_id",sa.String(36),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),sa.Column("user_id",sa.String(36),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("role",sa.String(20),nullable=False),sa.Column("status",sa.String(20),nullable=False),sa.Column("joined_at",sa.DateTime(timezone=True),nullable=False),sa.Column("last_active_at",sa.DateTime(timezone=True)),sa.UniqueConstraint("organization_id","user_id",name="uq_organization_member"))
    for name in ("organization_id","user_id","role","status"):op.create_index(f"ix_organization_members_{name}","organization_members",[name])
    op.create_table("organization_invitations",sa.Column("id",sa.String(36),primary_key=True),sa.Column("organization_id",sa.String(36),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),sa.Column("email",sa.String(320),nullable=False),sa.Column("role",sa.String(20),nullable=False),sa.Column("invited_by",sa.String(36),sa.ForeignKey("users.id",ondelete="RESTRICT"),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("expires_at",sa.DateTime(timezone=True),nullable=False),sa.Column("accepted_at",sa.DateTime(timezone=True)),sa.Column("revoked_at",sa.DateTime(timezone=True)),sa.Column("last_sent_at",sa.DateTime(timezone=True),nullable=False))
    for name in ("organization_id","email","expires_at"):op.create_index(f"ix_organization_invitations_{name}","organization_invitations",[name])
    op.create_table("notification_preferences",sa.Column("id",sa.String(36),primary_key=True),sa.Column("organization_id",sa.String(36),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),sa.Column("user_id",sa.String(36),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("preferences",sa.JSON(),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint("organization_id","user_id",name="uq_notification_preference"));op.create_index("ix_notification_preferences_organization_id","notification_preferences",["organization_id"]);op.create_index("ix_notification_preferences_user_id","notification_preferences",["user_id"])
    op.create_table("feature_flags",sa.Column("key",sa.String(80),primary_key=True),sa.Column("state",sa.String(20),nullable=False),sa.Column("description",sa.String(300),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False),sa.Column("updated_by",sa.String(36)))
    with op.batch_alter_table("users") as batch:batch.add_column(sa.Column("is_platform_admin",sa.Boolean(),nullable=False,server_default=sa.false()));batch.create_index("ix_users_is_platform_admin",["is_platform_admin"])
    with op.batch_alter_table("sessions") as batch:batch.add_column(sa.Column("last_active_at",sa.DateTime(timezone=True)));batch.add_column(sa.Column("client_summary",sa.String(160)))
    with op.batch_alter_table("audit_events") as batch:batch.add_column(sa.Column("organization_id",sa.String(36)));batch.create_index("ix_audit_events_organization_id",["organization_id"])
    bind=op.get_bind();now=datetime.now(timezone.utc);users=bind.execute(sa.text("SELECT id,display_name,organization,role FROM users")).mappings().all()
    for user in users:
        org_id=str(uuid4());statement=sa.text("INSERT INTO organizations (id,name,slug,status,plan_id,plan_status,created_by,settings,created_at,updated_at) VALUES (:id,:name,:slug,'ACTIVE','FREE','ACTIVE',:user,:settings,:now,:now)").bindparams(sa.bindparam("settings",type_=sa.JSON()));bind.execute(statement,{"id":org_id,"name":user["organization"] or f'{user["display_name"]}\'s Organization',"slug":f'org-{user["id"]}',"user":user["id"],"settings":{},"now":now});bind.execute(sa.text("INSERT INTO organization_members (id,organization_id,user_id,role,status,joined_at) VALUES (:id,:org,:user,'OWNER','ACTIVE',:now)"),{"id":str(uuid4()),"org":org_id,"user":user["id"],"now":now})
    bind.execute(sa.text("UPDATE users SET is_platform_admin = true WHERE username IN ('Sith','Beyond')"))
def downgrade():
    with op.batch_alter_table("audit_events") as batch:batch.drop_index("ix_audit_events_organization_id");batch.drop_column("organization_id")
    with op.batch_alter_table("sessions") as batch:batch.drop_column("client_summary");batch.drop_column("last_active_at")
    with op.batch_alter_table("users") as batch:batch.drop_index("ix_users_is_platform_admin");batch.drop_column("is_platform_admin")
    for table in ("feature_flags","notification_preferences","organization_invitations","organization_members","organizations"):op.drop_table(table)
