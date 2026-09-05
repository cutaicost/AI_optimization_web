from apps.api.aiopt_web.auth import bootstrap_admins
from apps.api.aiopt_web.database import Base,SessionLocal,engine
Base.metadata.create_all(engine)
with SessionLocal() as database:
    created=bootstrap_admins(database)
print("Administrator bootstrap complete; created:",", ".join(created) if created else "none")
