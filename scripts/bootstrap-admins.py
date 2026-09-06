import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from apps.api.aiopt_web.auth import bootstrap_admins
from apps.api.aiopt_web.database import SessionLocal
with SessionLocal() as database:
    created=bootstrap_admins(database)
print("Administrator bootstrap complete; created:",", ".join(created) if created else "none")
