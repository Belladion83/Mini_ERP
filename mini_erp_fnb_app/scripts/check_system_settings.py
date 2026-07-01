from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from app.core.config import get_settings

s = get_settings()
print("===== Mini ERP Settings Diagnostic =====")
for key, value in s.diagnostic_summary().items():
    print(f"{key}: {value}")

print("\n===== SQL Server Connection Test =====")
try:
    engine = create_engine(s.sqlalchemy_database_url, pool_pre_ping=True, future=True)
    with engine.connect() as conn:
        row = conn.execute(text("SELECT DB_NAME() AS db_name, @@SERVERNAME AS server_name")).mappings().first()
        print("SQL connection: OK")
        print("Connected database:", row["db_name"])
        print("SQL server name:", row["server_name"])
except SQLAlchemyError as exc:
    print("SQL connection: FAILED")
    print(str(exc)[:1500])

print("\nNote: if sqlserver_effective_server is localhost,1433 but your SSMS uses QU08031999\\ERP_DATABASE, update .env.")
