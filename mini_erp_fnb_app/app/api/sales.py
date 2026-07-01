from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.core.permissions import require_permission
from app.core.number_utils import parse_decimal
from app.services.sales_service import SalesService

router = APIRouter(prefix="/sales", tags=["sales"])
templates = Jinja2Templates(directory="app/templates")


@router.get("")
def sales_index(request: Request, db: Session = Depends(get_db), user=Depends(require_permission("SALES_VIEW"))):
    customers = db.execute(text("SELECT id, bp_code, bp_name FROM dbo.business_partners WHERE bp_type IN (N'CUSTOMER', N'BOTH') ORDER BY bp_code")).mappings().all()
    items = db.execute(text("""
        SELECT i.id, i.item_code, i.item_name, i.sales_price, ISNULL(i.delivery_days, 0) AS delivery_days, ISNULL(i.profit_percent, 0) AS profit_percent,
               STUFF((
                   SELECT N',' + sc.channel_code
                   FROM dbo.item_sale_channels isc
                   JOIN dbo.sale_channels sc ON sc.id = isc.sale_channel_id
                   WHERE isc.item_id = i.id AND sc.is_active = 1
                   FOR XML PATH(''), TYPE
               ).value('.', 'NVARCHAR(MAX)'), 1, 1, N'') AS allowed_channels
        FROM dbo.items i
        WHERE i.item_type = N'FINISHED'
          AND ISNULL(i.can_be_sold, 1) = 1
          AND i.is_active = 1
          AND EXISTS (SELECT 1 FROM dbo.item_sale_channels isc WHERE isc.item_id = i.id)
        ORDER BY i.item_code
    """)).mappings().all()
    warehouses = db.execute(text("SELECT id, warehouse_code, warehouse_name FROM dbo.warehouses ORDER BY warehouse_code")).mappings().all()
    channels = db.execute(text("""
        SELECT sc.channel_code, sc.channel_name, sc.channel_type, sc.default_customer_id, sc.default_warehouse_id,
               tc.tax_code AS default_tax_code, tc.rate AS default_tax_rate
        FROM dbo.sale_channels sc
        LEFT JOIN dbo.tax_codes tc ON tc.id = sc.default_tax_code_id
        WHERE sc.is_active = 1
        ORDER BY sc.channel_type, sc.channel_code
    """)).mappings().all()
    orders = db.execute(text("SELECT TOP 20 so_no, so_date, customer_id, status, grand_total, channel_code FROM dbo.sales_orders ORDER BY id DESC")).mappings().all()
    return templates.TemplateResponse("sales.html", {"request": request, "user": user, "customers": customers, "items": items, "warehouses": warehouses, "channels": channels, "orders": orders})


@router.get("/api/check-availability")
def api_check_availability(item_id: int, warehouse_id: int, quantity: Decimal, db: Session = Depends(get_db), user=Depends(require_permission("SALES_VIEW"))):
    try:
        result = SalesService(db, int(user["id"])).check_availability(item_id, warehouse_id, quantity)
        return JSONResponse({k: (str(v) if isinstance(v, Decimal) else v) for k, v in result.items()})
    except ValueError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)


@router.get("/api/calculate-price")
def api_calculate_price(item_id: int, warehouse_id: int, quantity: Decimal = Decimal("1"), db: Session = Depends(get_db), user=Depends(require_permission("SALES_VIEW"))):
    result = SalesService(db, int(user["id"])).calculate_sales_price(item_id, warehouse_id, quantity, date.today())
    return JSONResponse({k: (str(v) if isinstance(v, Decimal) else v) for k, v in result.items() if k != "layers"})


@router.post("/api/production-request")
async def api_create_production_request(request: Request, db: Session = Depends(get_db), user=Depends(require_permission("SALES_EDIT"))):
    form = await request.form()
    try:
        request_id = SalesService(db, int(user["id"])).create_production_request(
            int(form.get("item_id") or 0),
            int(form.get("warehouse_id") or 0),
            parse_decimal(form.get("quantity") or 0),
            str(form.get("channel_code") or ""),
            str(form.get("note") or "Shortage from Sales Check Availability").strip() or None,
        )
        return JSONResponse({"ok": True, "request_id": request_id})
    except Exception as exc:
        db.rollback()
        return JSONResponse({"ok": False, "error": str(exc)[:300]}, status_code=400)


@router.post("/quick-sale")
def quick_sale(
    request: Request,
    customer_id: int = Form(...),
    item_id: int = Form(...),
    warehouse_id: int = Form(...),
    quantity: str = Form(...),
    unit_price: str = Form(...),
    channel_code: str = Form("RETAIL"),
    external_ref: str = Form(""),
    manual_so_no: str = Form(""),
    db: Session = Depends(get_db),
    user=Depends(require_permission("SALES_EDIT")),
):
    try:
        SalesService(db, int(user["id"])).create_quick_sale(customer_id, item_id, warehouse_id, parse_decimal(quantity), parse_decimal(unit_price), doc_date=date.today(), channel_code=channel_code, external_ref=external_ref.strip() or None, manual_so_no=manual_so_no.strip() or None)
        return RedirectResponse("/sales?success=Sales transaction posted successfully.", status_code=303)
    except ValueError as exc:
        db.rollback()
        return RedirectResponse(f"/sales?error={str(exc)}", status_code=303)
