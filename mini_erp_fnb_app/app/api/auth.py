from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.core.db import get_db
from app.core.permissions import user_has_permission
from app.core.security import verify_password
from app.services.email_service import send_email

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _safe_next(next_url: str | None) -> str:
    if next_url and next_url.startswith("/") and not next_url.startswith("//"):
        return next_url
    return "/"


@router.get("/login")
def login_page(request: Request, next: str = ""):
    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": None,
        "next_url": _safe_next(next) if next else "",
    })


@router.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next_url: str = Form(""),
    db: Session = Depends(get_db),
):
    user = db.execute(text("""
        SELECT TOP 1
            id,
            username,
            password_hash,
            full_name,
            is_active,
            ISNULL(failed_login_count, 0) AS failed_login_count,
            ISNULL(is_locked, 0) AS is_locked
        FROM dbo.users
        WHERE LOWER(username)=LOWER(:username)
    """), {"username": username.strip()}).mappings().first()

    if not user:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Sai username hoặc password.",
            "next_url": _safe_next(next_url) if next_url else "",
        })

    if not user["is_active"]:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "User đang bị inactive. Vui lòng liên hệ Admin.",
            "next_url": _safe_next(next_url) if next_url else "",
        })

    if user["is_locked"]:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "User đã bị khóa do nhập sai password quá 5 lần. Vui lòng liên hệ Admin để unlock.",
            "next_url": _safe_next(next_url) if next_url else "",
        })

    if not verify_password(password, user["password_hash"]):
        failed_count = int(user["failed_login_count"] or 0) + 1
        if failed_count >= 5:
            db.execute(text("""
                UPDATE dbo.users
                SET failed_login_count=:failed_count,
                    is_locked=1,
                    locked_at=SYSUTCDATETIME(),
                    last_failed_login_at=SYSUTCDATETIME(),
                    updated_at=SYSUTCDATETIME()
                WHERE id=:id
            """), {"failed_count": failed_count, "id": user["id"]})
            db.commit()
            error = "Bạn đã nhập sai password 5/5 lần. User đã bị khóa, vui lòng liên hệ Admin để unlock."
        else:
            db.execute(text("""
                UPDATE dbo.users
                SET failed_login_count=:failed_count,
                    last_failed_login_at=SYSUTCDATETIME(),
                    updated_at=SYSUTCDATETIME()
                WHERE id=:id
            """), {"failed_count": failed_count, "id": user["id"]})
            db.commit()
            remaining = 5 - failed_count
            error = f"Sai password. Bạn đã nhập sai {failed_count}/5 lần. Còn {remaining} lần trước khi user bị khóa."
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": error,
            "next_url": _safe_next(next_url) if next_url else "",
        })

    db.execute(text("""
        UPDATE dbo.users
        SET failed_login_count=0,
            last_failed_login_at=NULL,
            last_login_at=SYSUTCDATETIME(),
            updated_at=SYSUTCDATETIME()
        WHERE id=:id
    """), {"id": user["id"]})
    db.commit()

    request.session["user"] = {
        "id": int(user["id"]),
        "username": user["username"],
        "full_name": user["full_name"] or user["username"],
    }
    return RedirectResponse(_safe_next(next_url), status_code=303)


@router.get("/forgot-password")
def forgot_password_page(request: Request):
    return templates.TemplateResponse("forgot_password.html", {
        "request": request,
        "error": None,
        "success": None,
    })


@router.post("/forgot-password")
def forgot_password_request(
    request: Request,
    username: str = Form(...),
    db: Session = Depends(get_db),
):
    """Receive a password recovery request by username.

    The user enters only their ERP username. The system sends a notification
    email to active User Admin accounts maintained in User Master Data.
    """
    requested_username = username.strip()
    try:
        requester = db.execute(text("""
            SELECT TOP 1 id, username, full_name, email, is_active
            FROM dbo.users
            WHERE LOWER(username) = LOWER(:username)
        """), {"username": requested_username}).mappings().first()
    except SQLAlchemyError as exc:
        return templates.TemplateResponse("forgot_password.html", {
            "request": request,
            "error": "Không kết nối được SQL Server. Vui lòng kiểm tra cấu hình SQLSERVER_HOST/SQLSERVER_PORT trong file .env.",
            "success": None,
        })

    if not requester or not requester["is_active"]:
        return templates.TemplateResponse("forgot_password.html", {
            "request": request,
            "error": "Không tìm thấy username hoặc user đang bị khóa.",
            "success": None,
        })

    admin_rows = db.execute(text("""
        SELECT DISTINCT u.id, u.username, u.full_name, u.email
        FROM dbo.users u
        JOIN dbo.user_group_members ugm ON ugm.user_id = u.id
        JOIN dbo.user_groups g ON g.id = ugm.group_id
        JOIN dbo.group_permissions gp ON gp.group_id = g.id
        JOIN dbo.permissions p ON p.id = gp.permission_id
        WHERE u.is_active = 1
          AND g.is_active = 1
          AND p.permission_code = 'USER_ADMIN'
          AND NULLIF(LTRIM(RTRIM(u.email)), '') IS NOT NULL
    """)).mappings().all()

    if not admin_rows:
        return templates.TemplateResponse("forgot_password.html", {
            "request": request,
            "error": "Chưa có User Admin nào có email trong User Master Data. Vui lòng cập nhật email cho Admin.",
            "success": None,
        })

    base_url = str(request.base_url).rstrip("/")
    admin_link = f"{base_url}/login?next={quote_plus('/admin/users')}"
    requester_name = requester["full_name"] or requester["username"]
    subject = "Mini ERP - User yêu cầu cấp lại mật khẩu"
    sent_to = []

    # Use User Admin email from database as fallback sender when SMTP_FROM is not set.
    # This keeps the flow controlled by User Master Data while SMTP_HOST remains the
    # required mail server setting.
    admin_from_email = next((a["email"] for a in admin_rows if a["email"]), None)

    for admin in admin_rows:
        admin_name = admin["full_name"] or admin["username"]
        body = f"""Xin chào {admin_name},

User {requester['username']} gửi yêu cầu cấp lại mật khẩu hệ thống ERP.

Thông tin user:
- Username: {requester['username']}
- Họ tên: {requester_name}
- Email: {requester['email'] or ''}

Vui lòng đăng nhập bằng tài khoản Admin và vào mục User Admin để kiểm tra/reset mật khẩu cho user này:
{admin_link}

Nếu đây không phải yêu cầu hợp lệ, vui lòng kiểm tra lại với user hoặc bỏ qua email này.
"""
        html = f"""
        <p>Xin chào <strong>{admin_name}</strong>,</p>
        <p><strong>User {requester['username']} gửi yêu cầu cấp lại mật khẩu hệ thống ERP.</strong></p>
        <p>Thông tin user:</p>
        <ul>
            <li><strong>Username:</strong> {requester['username']}</li>
            <li><strong>Họ tên:</strong> {requester_name}</li>
            <li><strong>Email:</strong> {requester['email'] or ''}</li>
        </ul>
        <p>Vui lòng đăng nhập bằng tài khoản Admin và vào mục <strong>User Admin</strong> để kiểm tra/reset mật khẩu cho user này.</p>
        <p><a href="{admin_link}">Mở User Admin</a></p>
        <p>Nếu đây không phải yêu cầu hợp lệ, vui lòng kiểm tra lại với user hoặc bỏ qua email này.</p>
        """
        try:
            send_email(admin["email"], subject, body, html, from_email_override=admin_from_email)
            sent_to.append(admin["email"])
        except Exception as exc:
            return templates.TemplateResponse("forgot_password.html", {
                "request": request,
                "error": f"Không gửi được email đến Admin {admin['username']}: {str(exc)[:240]}",
                "success": None,
            })

    return templates.TemplateResponse("forgot_password.html", {
        "request": request,
        "error": None,
        "success": f"Đã gửi yêu cầu khôi phục mật khẩu đến {len(sent_to)} User Admin.",
    })


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
