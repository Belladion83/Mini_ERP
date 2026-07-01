from __future__ import annotations

import smtplib
from email.message import EmailMessage
from typing import Optional

from app.core.config import ENV_FILE_PATH, get_settings


def send_email(
    to_email: str,
    subject: str,
    body: str,
    html_body: Optional[str] = None,
    from_email_override: Optional[str] = None,
) -> None:
    """Send email using SMTP settings from .env.

    The sender address can be passed from the database, for example the first
    active User Admin email. SMTP_HOST is still required because it identifies
    the mail server used to deliver the message.
    """
    settings = get_settings()
    host = (settings.smtp_host or "").strip()
    port = int(settings.smtp_port or 587)
    username = (settings.smtp_user or "").strip()
    password = (settings.smtp_password or "").strip()
    from_email = (from_email_override or settings.smtp_from or username or "").strip()

    if not host:
        raise RuntimeError(
            f"SMTP chưa được cấu hình. Vui lòng kiểm tra SMTP_HOST trong file {ENV_FILE_PATH}. "
            "Nếu vừa sửa .env, hãy tắt app bằng CTRL+C rồi chạy lại."
        )
    if not from_email:
        raise RuntimeError(
            "Không xác định được email gửi đi. Vui lòng cập nhật email cho User Admin hoặc SMTP_USER trong file .env."
        )

    msg = EmailMessage()
    msg["From"] = from_email
    if username and from_email_override and from_email_override.lower() != username.lower():
        msg["Reply-To"] = from_email_override
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")

    use_tls = str(settings.smtp_use_tls or "yes").lower() in ("1", "true", "yes", "y")
    with smtplib.SMTP(host, port, timeout=20) as server:
        if use_tls:
            server.starttls()
        if username and password:
            server.login(username, password)
        server.send_message(msg)
