from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.permissions import require_permission
from app.core.security import get_password_hash

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory="app/templates")


def _redirect(url: str, success: str = "", error: str = ""):
    from urllib.parse import quote_plus
    if success:
        url += ("&" if "?" in url else "?") + "success=" + quote_plus(success)
    if error:
        url += ("&" if "?" in url else "?") + "error=" + quote_plus(error)
    return RedirectResponse(url, status_code=303)


def _groups(db: Session):
    return db.execute(text("""
        SELECT id, group_code, group_name, description, is_active
        FROM dbo.user_groups
        ORDER BY group_code
    """)).mappings().all()


def _permissions(db: Session):
    return db.execute(text("""
        SELECT id, permission_code, permission_name, module_code
        FROM dbo.permissions
        ORDER BY module_code, permission_code
    """)).mappings().all()


def _password_error(password: str) -> str:
    if password and len(password.encode("utf-8")) > 72:
        return "Password không được dài quá 72 bytes khi dùng bcrypt. Vui lòng nhập password ngắn hơn."
    return ""


@router.get("")
def admin_home(request: Request, db: Session = Depends(get_db), user=Depends(require_permission("USER_ADMIN"))):
    user_count = db.execute(text("SELECT COUNT(1) AS cnt FROM dbo.users")).mappings().first()["cnt"]
    group_count = db.execute(text("SELECT COUNT(1) AS cnt FROM dbo.user_groups")).mappings().first()["cnt"]
    permission_count = db.execute(text("SELECT COUNT(1) AS cnt FROM dbo.permissions")).mappings().first()["cnt"]
    return templates.TemplateResponse("admin_home.html", {
        "request": request,
        "user": user,
        "page_title": "User & Permission Admin",
        "user_count": user_count,
        "group_count": group_count,
        "permission_count": permission_count,
    })


@router.get("/users")
def user_list(request: Request, q: str = "", include_inactive: int = 0, db: Session = Depends(get_db), user=Depends(require_permission("USER_ADMIN"))):
    sql = """
        SELECT
            u.id, u.username, u.full_name, u.email, u.is_active, u.created_at,
            ISNULL(u.failed_login_count, 0) AS failed_login_count,
            ISNULL(u.is_locked, 0) AS is_locked,
            u.locked_at,
            STRING_AGG(g.group_code, ', ') WITHIN GROUP (ORDER BY g.group_code) AS group_codes
        FROM dbo.users u
        LEFT JOIN dbo.user_group_members ugm ON ugm.user_id = u.id
        LEFT JOIN dbo.user_groups g ON g.id = ugm.group_id
        WHERE 1=1
    """
    params = {}
    if not include_inactive:
        sql += " AND u.is_active = 1"
    if q.strip():
        sql += " AND (u.username LIKE :q OR u.full_name LIKE :q OR u.email LIKE :q)"
        params["q"] = f"%{q.strip()}%"
    sql += " GROUP BY u.id, u.username, u.full_name, u.email, u.is_active, u.created_at, u.failed_login_count, u.is_locked, u.locked_at ORDER BY u.username"
    rows = db.execute(text(sql), params).mappings().all()
    return templates.TemplateResponse("admin_users.html", {
        "request": request,
        "user": user,
        "rows": rows,
        "q": q,
        "include_inactive": include_inactive,
        "page_title": "User Master Data",
    })


@router.get("/users/new")
def user_new_form(request: Request, db: Session = Depends(get_db), user=Depends(require_permission("USER_ADMIN"))):
    return templates.TemplateResponse("admin_user_form.html", {
        "request": request,
        "user": user,
        "row": {"id": None, "username": "", "full_name": "", "email": "", "is_active": 1, "is_locked": 0, "failed_login_count": 0},
        "groups": _groups(db),
        "selected_group_ids": set(),
        "errors": [],
        "page_title": "Create User",
    })


@router.post("/users/save-new")
async def user_save_new(request: Request, db: Session = Depends(get_db), user=Depends(require_permission("USER_ADMIN"))):
    form = await request.form()
    username = str(form.get("username") or "").strip()
    full_name = str(form.get("full_name") or "").strip()
    email = str(form.get("email") or "").strip()
    password = str(form.get("new_password") or form.get("password") or "").strip()
    is_active = 1 if form.get("is_active") in ("on", "1", "true") else 0
    group_ids = [int(x) for x in form.getlist("group_ids") if str(x).isdigit()]

    errors = []
    if not username:
        errors.append("Username is required.")
    if not password:
        errors.append("Password is required for new user.")
    pw_error = _password_error(password)
    if pw_error:
        errors.append(pw_error)
    if not group_ids:
        errors.append("Assign at least one group.")
    row = {"id": None, "username": username, "full_name": full_name, "email": email, "is_active": is_active, "is_locked": 0, "failed_login_count": 0}
    if errors:
        return templates.TemplateResponse("admin_user_form.html", {"request": request, "user": user, "row": row, "groups": _groups(db), "selected_group_ids": set(group_ids), "errors": errors, "page_title": "Create User"})

    try:
        result = db.execute(text("""
            INSERT INTO dbo.users(username, password_hash, full_name, email, is_active)
            OUTPUT INSERTED.id
            VALUES (:username, :password_hash, :full_name, :email, :is_active)
        """), {
            "username": username,
            "password_hash": get_password_hash(password),
            "full_name": full_name or None,
            "email": email or None,
            "is_active": is_active,
        })
        user_id = int(result.scalar_one())
        for group_id in group_ids:
            db.execute(text("INSERT INTO dbo.user_group_members(user_id, group_id) VALUES (:user_id, :group_id)"), {"user_id": user_id, "group_id": group_id})
        db.commit()
        return _redirect("/admin/users", success="Đã tạo user mới.")
    except IntegrityError:
        db.rollback()
        return templates.TemplateResponse("admin_user_form.html", {"request": request, "user": user, "row": row, "groups": _groups(db), "selected_group_ids": set(group_ids), "errors": ["Username đã tồn tại hoặc group không hợp lệ."], "page_title": "Create User"})
    except ValueError as exc:
        db.rollback()
        return templates.TemplateResponse("admin_user_form.html", {"request": request, "user": user, "row": row, "groups": _groups(db), "selected_group_ids": set(group_ids), "errors": [str(exc)[:300]], "page_title": "Create User"})
    except SQLAlchemyError as exc:
        db.rollback()
        return templates.TemplateResponse("admin_user_form.html", {"request": request, "user": user, "row": row, "groups": _groups(db), "selected_group_ids": set(group_ids), "errors": [str(exc)[:300]], "page_title": "Create User"})


@router.get("/users/{user_id}/edit")
def user_edit_form(user_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_permission("USER_ADMIN"))):
    row = db.execute(text("""
        SELECT id, username, full_name, email, is_active,
               ISNULL(failed_login_count, 0) AS failed_login_count,
               ISNULL(is_locked, 0) AS is_locked,
               locked_at,
               last_failed_login_at,
               last_login_at
        FROM dbo.users
        WHERE id=:id
    """), {"id": user_id}).mappings().first()
    if not row:
        return _redirect("/admin/users", error="Không tìm thấy user.")
    selected = db.execute(text("SELECT group_id FROM dbo.user_group_members WHERE user_id=:id"), {"id": user_id}).scalars().all()
    return templates.TemplateResponse("admin_user_form.html", {
        "request": request,
        "user": user,
        "row": dict(row),
        "groups": _groups(db),
        "selected_group_ids": set(int(x) for x in selected),
        "errors": [],
        "page_title": "Edit User",
    })


@router.post("/users/{user_id}/save")
async def user_save_edit(user_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_permission("USER_ADMIN"))):
    form = await request.form()
    full_name = str(form.get("full_name") or "").strip()
    email = str(form.get("email") or "").strip()
    password = str(form.get("new_password") or "").strip()
    is_active = 1 if form.get("is_active") in ("on", "1", "true") else 0
    is_locked = 1 if form.get("is_locked") in ("on", "1", "true") else 0
    group_ids = [int(x) for x in form.getlist("group_ids") if str(x).isdigit()]
    row = db.execute(text("""
        SELECT id, username, full_name, email, is_active,
               ISNULL(failed_login_count, 0) AS failed_login_count,
               ISNULL(is_locked, 0) AS is_locked,
               locked_at,
               last_failed_login_at,
               last_login_at
        FROM dbo.users
        WHERE id=:id
    """), {"id": user_id}).mappings().first()
    if not row:
        return _redirect("/admin/users", error="Không tìm thấy user.")
    errors = []
    if not group_ids:
        errors.append("Assign at least one group.")
    pw_error = _password_error(password)
    if pw_error:
        errors.append(pw_error)
    if errors:
        row = dict(row); row.update({"full_name": full_name, "email": email, "is_active": is_active, "is_locked": is_locked})
        return templates.TemplateResponse("admin_user_form.html", {"request": request, "user": user, "row": row, "groups": _groups(db), "selected_group_ids": set(group_ids), "errors": errors, "page_title": "Edit User"})

    try:
        if password:
            db.execute(text("""
                UPDATE dbo.users
                SET full_name=:full_name, email=:email, is_active=:is_active,
                    is_locked=:is_locked,
                    failed_login_count=CASE WHEN :is_locked = 1 THEN failed_login_count ELSE 0 END,
                    locked_at=CASE WHEN :is_locked = 1 THEN COALESCE(locked_at, SYSUTCDATETIME()) ELSE NULL END,
                    last_failed_login_at=CASE WHEN :is_locked = 1 THEN last_failed_login_at ELSE NULL END,
                    password_hash=:password_hash, updated_at=SYSUTCDATETIME()
                WHERE id=:id
            """), {"id": user_id, "full_name": full_name or None, "email": email or None, "is_active": is_active, "is_locked": is_locked, "password_hash": get_password_hash(password)})
        else:
            db.execute(text("""
                UPDATE dbo.users
                SET full_name=:full_name, email=:email, is_active=:is_active,
                    is_locked=:is_locked,
                    failed_login_count=CASE WHEN :is_locked = 1 THEN failed_login_count ELSE 0 END,
                    locked_at=CASE WHEN :is_locked = 1 THEN COALESCE(locked_at, SYSUTCDATETIME()) ELSE NULL END,
                    last_failed_login_at=CASE WHEN :is_locked = 1 THEN last_failed_login_at ELSE NULL END,
                    updated_at=SYSUTCDATETIME()
                WHERE id=:id
            """), {"id": user_id, "full_name": full_name or None, "email": email or None, "is_active": is_active, "is_locked": is_locked})
        db.execute(text("DELETE FROM dbo.user_group_members WHERE user_id=:id"), {"id": user_id})
        for group_id in group_ids:
            db.execute(text("INSERT INTO dbo.user_group_members(user_id, group_id) VALUES (:user_id, :group_id)"), {"user_id": user_id, "group_id": group_id})
        db.commit()
        return _redirect("/admin/users", success="Đã cập nhật user.")
    except ValueError as exc:
        db.rollback()
        row = dict(row); row.update({"full_name": full_name, "email": email, "is_active": is_active, "is_locked": is_locked})
        return templates.TemplateResponse("admin_user_form.html", {"request": request, "user": user, "row": row, "groups": _groups(db), "selected_group_ids": set(group_ids), "errors": [str(exc)[:300]], "page_title": "Edit User"})
    except SQLAlchemyError as exc:
        db.rollback()
        row = dict(row); row.update({"full_name": full_name, "email": email, "is_active": is_active, "is_locked": is_locked})
        return templates.TemplateResponse("admin_user_form.html", {"request": request, "user": user, "row": row, "groups": _groups(db), "selected_group_ids": set(group_ids), "errors": [str(exc)[:300]], "page_title": "Edit User"})


@router.get("/groups")
def group_list(request: Request, db: Session = Depends(get_db), user=Depends(require_permission("USER_ADMIN"))):
    rows = db.execute(text("""
        SELECT g.id, g.group_code, g.group_name, g.description, g.is_active,
               COUNT(DISTINCT ugm.user_id) AS user_count,
               COUNT(DISTINCT gp.permission_id) AS permission_count
        FROM dbo.user_groups g
        LEFT JOIN dbo.user_group_members ugm ON ugm.group_id = g.id
        LEFT JOIN dbo.group_permissions gp ON gp.group_id = g.id
        GROUP BY g.id, g.group_code, g.group_name, g.description, g.is_active
        ORDER BY g.group_code
    """)).mappings().all()
    return templates.TemplateResponse("admin_groups.html", {"request": request, "user": user, "rows": rows, "page_title": "User Groups & Permissions"})


@router.get("/groups/{group_id}/edit")
def group_edit_form(group_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_permission("USER_ADMIN"))):
    row = db.execute(text("SELECT id, group_code, group_name, description, is_active FROM dbo.user_groups WHERE id=:id"), {"id": group_id}).mappings().first()
    if not row:
        return _redirect("/admin/groups", error="Không tìm thấy group.")
    selected = db.execute(text("SELECT permission_id FROM dbo.group_permissions WHERE group_id=:id"), {"id": group_id}).scalars().all()
    return templates.TemplateResponse("admin_group_form.html", {
        "request": request,
        "user": user,
        "row": dict(row),
        "permissions": _permissions(db),
        "selected_permission_ids": set(int(x) for x in selected),
        "errors": [],
        "page_title": "Edit User Group",
    })


@router.post("/groups/{group_id}/save")
async def group_save(group_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_permission("USER_ADMIN"))):
    form = await request.form()
    group_name = str(form.get("group_name") or "").strip()
    description = str(form.get("description") or "").strip()
    is_active = 1 if form.get("is_active") in ("on", "1", "true") else 0
    permission_ids = [int(x) for x in form.getlist("permission_ids") if str(x).isdigit()]
    row = db.execute(text("SELECT id, group_code, group_name, description, is_active FROM dbo.user_groups WHERE id=:id"), {"id": group_id}).mappings().first()
    if not row:
        return _redirect("/admin/groups", error="Không tìm thấy group.")
    if not group_name:
        row = dict(row); row.update({"group_name": group_name, "description": description, "is_active": is_active})
        return templates.TemplateResponse("admin_group_form.html", {"request": request, "user": user, "row": row, "permissions": _permissions(db), "selected_permission_ids": set(permission_ids), "errors": ["Group name is required."], "page_title": "Edit User Group"})
    try:
        db.execute(text("UPDATE dbo.user_groups SET group_name=:group_name, description=:description, is_active=:is_active WHERE id=:id"), {"id": group_id, "group_name": group_name, "description": description or None, "is_active": is_active})
        db.execute(text("DELETE FROM dbo.group_permissions WHERE group_id=:id"), {"id": group_id})
        for permission_id in permission_ids:
            db.execute(text("INSERT INTO dbo.group_permissions(group_id, permission_id) VALUES (:group_id, :permission_id)"), {"group_id": group_id, "permission_id": permission_id})
        db.commit()
        return _redirect("/admin/groups", success="Đã cập nhật quyền cho group.")
    except SQLAlchemyError as exc:
        db.rollback()
        row = dict(row); row.update({"group_name": group_name, "description": description, "is_active": is_active})
        return templates.TemplateResponse("admin_group_form.html", {"request": request, "user": user, "row": row, "permissions": _permissions(db), "selected_permission_ids": set(permission_ids), "errors": [str(exc)[:300]], "page_title": "Edit User Group"})
