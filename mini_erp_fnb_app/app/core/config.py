from functools import lru_cache
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus
import os

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE_PATH = PROJECT_ROOT / ".env"

# Force-load the project .env into os.environ as well as pydantic-settings.
# This makes diagnostics and legacy variable aliases reliable even when uvicorn
# is started from a different working directory.
load_dotenv(ENV_FILE_PATH, override=True)


def _clean(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = str(value).strip().strip('"').strip("'")
    return value if value else None


def _first_env(*names: str) -> Optional[str]:
    for name in names:
        value = _clean(os.getenv(name))
        if value is not None:
            return value
    return None


class Settings(BaseSettings):
    app_name: str = "Mini ERP"
    secret_key: str = "change-this-secret-key"

    # SQL Server connection settings.
    # Official env names are SQLSERVER_*, but v45 also supports legacy DB_* names.
    sqlserver_host: str = "localhost"
    sqlserver_port: Optional[str] = "1433"
    sqlserver_database: str = "MiniERPFNB"
    sqlserver_user: Optional[str] = "sa"
    sqlserver_password: Optional[str] = "YourStrongPassword"
    sqlserver_driver: str = "ODBC Driver 18 for SQL Server"
    sqlserver_trust_certificate: str = "yes"
    sqlserver_encrypt: str = "yes"

    # SMTP settings for forgot-password admin request email
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from: Optional[str] = None
    smtp_use_tls: str = "yes"

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE_PATH),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def _resolved_sqlserver_host(self) -> str:
        return _first_env("SQLSERVER_HOST", "DB_SERVER", "DB_HOST", "DATABASE_HOST") or self.sqlserver_host

    def _resolved_sqlserver_port(self) -> Optional[str]:
        return _first_env("SQLSERVER_PORT", "DB_PORT", "DATABASE_PORT") or _clean(self.sqlserver_port)

    def _resolved_sqlserver_database(self) -> str:
        return _first_env("SQLSERVER_DATABASE", "DB_NAME", "DB_DATABASE", "DATABASE_NAME") or self.sqlserver_database

    def _resolved_sqlserver_user(self) -> Optional[str]:
        return _first_env("SQLSERVER_USER", "DB_USER", "DATABASE_USER") or _clean(self.sqlserver_user)

    def _resolved_sqlserver_password(self) -> Optional[str]:
        return _first_env("SQLSERVER_PASSWORD", "DB_PASSWORD", "DATABASE_PASSWORD") or _clean(self.sqlserver_password)

    def _resolved_sqlserver_driver(self) -> str:
        return _first_env("SQLSERVER_DRIVER", "DB_DRIVER", "DATABASE_DRIVER") or self.sqlserver_driver

    def _resolved_sqlserver_trust_certificate(self) -> str:
        return _first_env("SQLSERVER_TRUST_CERTIFICATE", "DB_TRUST_CERTIFICATE") or self.sqlserver_trust_certificate

    def _resolved_sqlserver_encrypt(self) -> str:
        return _first_env("SQLSERVER_ENCRYPT", "DB_ENCRYPT") or self.sqlserver_encrypt

    @property
    def sqlserver_effective_server(self) -> str:
        host = (_clean(self._resolved_sqlserver_host()) or "localhost")
        port = _clean(self._resolved_sqlserver_port())

        # Do not append a port to a named instance such as PCNAME\SQLEXPRESS.
        if port and "\\" not in host:
            return f"{host},{port}"
        return host

    @property
    def sqlalchemy_database_url(self) -> str:
        database = self._resolved_sqlserver_database()
        user = self._resolved_sqlserver_user()
        password = self._resolved_sqlserver_password()

        parts = [
            f"DRIVER={{{self._resolved_sqlserver_driver()}}}",
            f"SERVER={self.sqlserver_effective_server}",
            f"DATABASE={database}",
            f"TrustServerCertificate={self._resolved_sqlserver_trust_certificate()}",
            f"Encrypt={self._resolved_sqlserver_encrypt()}",
        ]

        if user and password:
            parts.extend([
                f"UID={user}",
                f"PWD={password}",
            ])
        else:
            parts.append("Trusted_Connection=yes")

        params = ";".join(parts) + ";"
        return "mssql+pyodbc:///?odbc_connect=" + quote_plus(params)

    def diagnostic_summary(self) -> dict:
        return {
            "env_file_path": str(ENV_FILE_PATH),
            "env_file_exists": ENV_FILE_PATH.exists(),
            "sqlserver_host": self._resolved_sqlserver_host(),
            "sqlserver_port": self._resolved_sqlserver_port() or "<empty>",
            "sqlserver_effective_server": self.sqlserver_effective_server,
            "sqlserver_database": self._resolved_sqlserver_database(),
            "sqlserver_user": self._resolved_sqlserver_user() or "<windows-auth>",
            "sqlserver_password": "<set>" if self._resolved_sqlserver_password() else "<empty>",
            "sqlserver_driver": self._resolved_sqlserver_driver(),
            "smtp_host": self.smtp_host or "<empty>",
            "smtp_port": self.smtp_port,
            "smtp_user": self.smtp_user or "<empty>",
            "smtp_password": "<set>" if self.smtp_password else "<empty>",
            "smtp_from": self.smtp_from or "<empty>",
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
