from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import get_settings

s = get_settings()
print("ENV file path:", s.diagnostic_summary()["env_file_path"])
print("ENV file exists:", s.diagnostic_summary()["env_file_exists"])
print("SQLSERVER_HOST:", s.diagnostic_summary()["sqlserver_host"])
print("SQLSERVER_PORT:", s.diagnostic_summary()["sqlserver_port"])
print("SQLSERVER_EFFECTIVE_SERVER:", s.diagnostic_summary()["sqlserver_effective_server"])
print("SQLSERVER_DATABASE:", s.diagnostic_summary()["sqlserver_database"])
print("SMTP_HOST:", s.smtp_host or "<empty>")
print("SMTP_PORT:", s.smtp_port)
print("SMTP_USER:", s.smtp_user or "<empty>")
print("SMTP_PASSWORD:", "<set>" if s.smtp_password else "<empty>")
print("SMTP_FROM:", s.smtp_from or "<empty>")
print("SMTP_USE_TLS:", s.smtp_use_tls)
