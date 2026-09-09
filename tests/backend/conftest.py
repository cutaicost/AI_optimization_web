import os
from pathlib import Path
TEST_DB=Path(__file__).resolve().parents[2]/"test.sqlite"
os.environ["APP_ENV"]="test"
os.environ["MODEL_REFRESH_ENABLED"]="false"
os.environ.setdefault("DATABASE_URL",f"sqlite:///{TEST_DB.as_posix()}")
os.environ["SESSION_SECRET"]="unit-test-session-material-not-production"
os.environ["ADMIN_SITH_PASSWORD"]="".join(("Bootstrap","Sith","123"))
os.environ["ADMIN_BEYOND_PASSWORD"]="".join(("Bootstrap","Beyond","123"))
