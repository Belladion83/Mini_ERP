from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.core.permissions import require_permission

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
def dashboard(request: Request, db: Session = Depends(get_db), user=Depends(require_permission("DASHBOARD_VIEW"))):
    cards = {}
    queries = {
        "items": "SELECT COUNT(1) FROM dbo.items",
        "customers": "SELECT COUNT(1) FROM dbo.business_partners WHERE bp_type IN (N'CUSTOMER', N'BOTH')",
        "vendors": "SELECT COUNT(1) FROM dbo.business_partners WHERE bp_type IN (N'VENDOR', N'BOTH')",
        "stock_moves": "SELECT COUNT(1) FROM dbo.inventory_movements",
        "journal_entries": "SELECT COUNT(1) FROM dbo.journal_entries",
        "inventory_value": "SELECT ISNULL(SUM(inventory_value), 0) FROM dbo.v_inventory_balance",
        "sales_today": "SELECT ISNULL(SUM(grand_total), 0) FROM dbo.sales_orders WHERE so_date = CAST(GETDATE() AS date)",
        "orders_today": "SELECT COUNT(1) FROM dbo.sales_orders WHERE so_date = CAST(GETDATE() AS date)",
        "production_open": "SELECT COUNT(1) FROM dbo.production_orders WHERE status NOT IN (N'CLOSED', N'CANCELLED', N'COMPLETED')",
        "low_stock_items": "SELECT COUNT(1) FROM dbo.v_inventory_balance WHERE on_hand_qty <= 0",
    }
    for key, sql in queries.items():
        cards[key] = db.execute(text(sql)).scalar_one()

    recent_docs = db.execute(text("""
        SELECT TOP 12 doc_type, doc_no, doc_date, status, amount
        FROM (
            SELECT N'Sales Order' AS doc_type, so_no AS doc_no, so_date AS doc_date, status, grand_total AS amount, id FROM dbo.sales_orders
            UNION ALL
            SELECT N'Goods Receipt', gr_no, gr_date, status, CAST(0 AS DECIMAL(19,4)) AS amount, id FROM dbo.goods_receipts
            UNION ALL
            SELECT N'Production Order', prod_no, prod_date, status, CAST(planned_qty AS DECIMAL(19,4)) AS amount, id FROM dbo.production_orders
            UNION ALL
            SELECT N'Journal Entry', je_no, je_date, status, CAST(0 AS DECIMAL(19,4)) AS amount, id FROM dbo.journal_entries
        ) d
        ORDER BY doc_date DESC, id DESC
    """)).mappings().all()

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "cards": cards,
            "recent_docs": recent_docs,
            "page_title": "Dashboard",
        },
    )
