from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.db import get_db


def get_current_user(request: Request):
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/login"})
    return user


def user_has_permission(db: Session, user_id: int, permission_code: str) -> bool:
    sql = text("""
        SELECT COUNT(1) AS cnt
        FROM dbo.users u
        JOIN dbo.user_group_members ugm ON ugm.user_id = u.id
        JOIN dbo.user_groups g ON g.id = ugm.group_id
        JOIN dbo.group_permissions gp ON gp.group_id = g.id
        JOIN dbo.permissions p ON p.id = gp.permission_id
        WHERE u.id = :user_id
          AND u.is_active = 1
          AND g.is_active = 1
          AND p.permission_code = :permission_code
    """)
    row = db.execute(sql, {"user_id": user_id, "permission_code": permission_code}).mappings().first()
    return bool(row and row["cnt"] > 0)


def require_permission(permission_code: str):
    def dependency(
        request: Request,
        db: Session = Depends(get_db),
        user: dict = Depends(get_current_user),
    ):
        if not user_has_permission(db, int(user["id"]), permission_code):
            raise HTTPException(status_code=403, detail=f"Missing permission: {permission_code}")
        return user
    return dependency
