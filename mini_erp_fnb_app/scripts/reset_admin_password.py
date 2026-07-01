from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import text
from app.core.db import SessionLocal
from app.core.security import get_password_hash

password = input("New admin password: ").strip()
if not password:
    raise SystemExit("Password cannot be empty")

with SessionLocal() as db:
    db.execute(text("UPDATE dbo.users SET password_hash=:hash WHERE username=N'admin'"), {"hash": get_password_hash(password)})
    db.commit()
print("Admin password updated.")
