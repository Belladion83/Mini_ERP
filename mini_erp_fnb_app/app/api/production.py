from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.core.permissions import require_permission
from app.services.production_service import ProductionService

router = APIRouter(prefix="/production", tags=["production"])
templates = Jinja2Templates(directory="app/templates")


def _safe_redirect(url: str, success: str = "", error: str = ""):
    from urllib.parse import quote_plus
    if success:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}success={quote_plus(success)}"
    if error:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}error={quote_plus(error)}"
    return RedirectResponse(url, status_code=303)


def _production_master_data(db: Session):
    boms = db.execute(text("""
        SELECT b.id, b.bom_code, i.item_code, i.item_name, b.version_no, b.base_qty
        FROM dbo.boms b JOIN dbo.items i ON i.id = b.finished_item_id
        ORDER BY b.bom_code
    """)).mappings().all()
    warehouses = db.execute(text("SELECT id, warehouse_code, warehouse_name FROM dbo.warehouses ORDER BY warehouse_code")).mappings().all()
    return boms, warehouses


def _recent_production_orders(db: Session, limit: int = 20):
    return db.execute(text("""
        SELECT TOP (:limit) po.id, po.prod_no, po.prod_date, i.item_code, i.item_name, po.planned_qty, po.completed_qty, po.status,
               iw.warehouse_code AS issue_warehouse_code, rw.warehouse_code AS receipt_warehouse_code
        FROM dbo.production_orders po
        JOIN dbo.items i ON i.id = po.finished_item_id
        LEFT JOIN dbo.warehouses iw ON iw.id = po.issue_warehouse_id
        LEFT JOIN dbo.warehouses rw ON rw.id = po.receipt_warehouse_id
        ORDER BY po.id DESC
    """), {"limit": limit}).mappings().all()


def _sales_production_requests(db: Session):
    try:
        return db.execute(text("""
            SELECT TOP 50 r.id, r.request_date, r.status, r.requested_qty, r.channel_code,
                   i.item_code, i.item_name, w.warehouse_code, w.warehouse_name AS sales_request_warehouse_name, u.username AS requested_by_username
            FROM dbo.sales_production_requests r
            JOIN dbo.items i ON i.id = r.item_id
            JOIN dbo.warehouses w ON w.id = r.warehouse_id
            LEFT JOIN dbo.users u ON u.id = r.requested_by
            WHERE r.status IN (N'OPEN', N'REVIEWED')
            ORDER BY r.id DESC
        """)).mappings().all()
    except Exception:
        return []


def _production_stats(db: Session):
    try:
        return db.execute(text("""
            SELECT
              (SELECT COUNT(1) FROM dbo.sales_production_requests WHERE status IN (N'OPEN', N'REVIEWED')) AS open_requests,
              (SELECT COUNT(1) FROM dbo.production_orders WHERE status IN (N'DRAFT', N'RELEASED', N'MATERIAL_ISSUED')) AS active_orders,
              (SELECT COUNT(1) FROM dbo.production_orders WHERE CONVERT(date, prod_date) = CONVERT(date, GETDATE())) AS today_orders
        """)).mappings().first()
    except Exception:
        return {"open_requests": 0, "active_orders": 0, "today_orders": 0}


@router.get("")
def production_index(request: Request, db: Session = Depends(get_db), user=Depends(require_permission("PRODUCTION_VIEW"))):
    orders = _recent_production_orders(db, 10)
    requests = _sales_production_requests(db)
    stats = _production_stats(db)
    return templates.TemplateResponse(
        "production.html",
        {"request": request, "user": user, "orders": orders, "requests": requests, "stats": stats},
    )


@router.get("/manual")
def production_manual(request: Request, db: Session = Depends(get_db), user=Depends(require_permission("PRODUCTION_VIEW"))):
    boms, warehouses = _production_master_data(db)
    orders = _recent_production_orders(db, 20)
    return templates.TemplateResponse(
        "production_manual.html",
        {"request": request, "user": user, "boms": boms, "warehouses": warehouses, "orders": orders},
    )


@router.get("/so-requests")
def production_so_requests(request: Request, db: Session = Depends(get_db), user=Depends(require_permission("PRODUCTION_VIEW"))):
    _, warehouses = _production_master_data(db)
    orders = _recent_production_orders(db, 20)
    requests = _sales_production_requests(db)
    return templates.TemplateResponse(
        "production_so_requests.html",
        {"request": request, "user": user, "warehouses": warehouses, "orders": orders, "requests": requests},
    )


@router.get("/api/bom-cost")
def api_bom_cost(bom_id: int, planned_qty: Decimal, issue_warehouse_id: int, db: Session = Depends(get_db), user=Depends(require_permission("PRODUCTION_VIEW"))):
    try:
        data = ProductionService(db, int(user["id"])).calculate_bom_cost(bom_id, planned_qty, issue_warehouse_id, date.today())
        def conv(v):
            if isinstance(v, Decimal):
                return str(v)
            if isinstance(v, list):
                return [{kk: conv(vv) for kk, vv in row.items()} for row in v]
            return v
        return JSONResponse({k: conv(v) for k, v in data.items()})
    except Exception as exc:
        return JSONResponse({"error": str(exc)[:300]}, status_code=400)


@router.post("/create-from-bom")
def create_from_bom(
    bom_id: int = Form(...),
    planned_qty: Decimal = Form(...),
    issue_warehouse_id: int = Form(...),
    receipt_warehouse_id: int = Form(...),
    db: Session = Depends(get_db),
    user=Depends(require_permission("PRODUCTION_EDIT")),
):
    try:
        finished_item_id = db.execute(text("SELECT finished_item_id FROM dbo.boms WHERE id=:id"), {"id": bom_id}).scalar_one()
        ProductionService(db, int(user["id"])).create_production_order_from_bom(finished_item_id, bom_id, planned_qty, issue_warehouse_id, receipt_warehouse_id, prod_date=date.today())
        return _safe_redirect("/production/manual", success="Production order created successfully. The manual production screen is ready for a new transaction.")
    except Exception as exc:
        db.rollback()
        return _safe_redirect("/production/manual", error=str(exc)[:300])


@router.post("/create-from-request")
def create_from_sales_request(
    request_id: int = Form(...),
    issue_warehouse_id: int = Form(...),
    receipt_warehouse_id: int = Form(...),
    db: Session = Depends(get_db),
    user=Depends(require_permission("PRODUCTION_EDIT")),
):
    try:
        ProductionService(db, int(user["id"])).create_production_order_from_request(request_id, issue_warehouse_id, receipt_warehouse_id, date.today())
        return _safe_redirect("/production/so-requests", success="Production order created from Sales Order request. The request list has been refreshed.")
    except Exception as exc:
        db.rollback()
        return _safe_redirect("/production/so-requests", error=str(exc)[:300])
