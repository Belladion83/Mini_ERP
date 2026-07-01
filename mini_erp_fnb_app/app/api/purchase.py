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
from app.services.purchase_service import PurchaseService

router = APIRouter(prefix="/purchase", tags=["purchase"])
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


def _to_decimal(value, default="0") -> Decimal:
    return parse_decimal(value if value not in (None, "") else default, default)


def _to_int(value, default=0) -> int:
    return int(value) if value not in (None, "") else default


def _master_data(db: Session):
    vendors = db.execute(text("""SELECT id, bp_code, bp_name FROM dbo.business_partners WHERE bp_type IN (N'VENDOR', N'BOTH') AND is_active=1 ORDER BY bp_code""")).mappings().all()
    items = db.execute(text("""SELECT id, item_code, item_name, base_uom, standard_cost, input_tax_code_id, ISNULL(estimate_receive_days, 0) AS estimate_receive_days FROM dbo.items WHERE item_type IN (N'RAW', N'PACKAGING', N'RESALE', N'SERVICE') AND is_active=1 ORDER BY item_code""")).mappings().all()
    warehouses = db.execute(text("SELECT id, warehouse_code, warehouse_name FROM dbo.warehouses WHERE is_active=1 ORDER BY warehouse_code")).mappings().all()
    tax_codes = db.execute(text("""SELECT id, tax_code, tax_name, rate, ISNULL(tax_type, N'INPUT') AS tax_type FROM dbo.tax_codes WHERE is_active=1 AND ISNULL(tax_type, N'INPUT') = N'INPUT' ORDER BY tax_code""")).mappings().all()
    return vendors, items, warehouses, tax_codes


def _unit_options(db: Session):
    """Return selectable UoM codes for transaction lines.

    Important UX rule:
    Order Unit must not be locked to the Item Base Unit.  Even if the UoM
    Master/standard conversion migration has not been run yet, users still need
    to pick common units such as gram/kg/ml/liter.  This helper therefore merges
    units from UoM Master, Item Master, item-specific conversions, standard
    conversions, and a small built-in fallback list.
    """
    units: list[str] = []

    def add_unit(value):
        u = str(value or "").strip()
        if u and u.lower() not in {x.lower() for x in units}:
            units.append(u)

    # Built-in fallback so Order Unit is selectable even before UoM seed data is applied.
    for u in ["pcs", "ea", "box", "pack", "g", "gram", "kg", "ml", "l", "liter", "cm", "m"]:
        add_unit(u)

    try:
        has_uom_master = bool(db.execute(text("SELECT CASE WHEN OBJECT_ID(N'dbo.unit_of_measures', N'U') IS NULL THEN 0 ELSE 1 END")).scalar())
        if has_uom_master:
            rows = db.execute(text("""
                SELECT unit_code AS unit_name
                FROM dbo.unit_of_measures
                WHERE is_active = 1 AND ISNULL(unit_code, N'') <> N''
                ORDER BY unit_code
            """)).mappings().all()
            for r in rows:
                add_unit(r["unit_name"])
    except Exception:
        pass

    try:
        has_conversions = bool(db.execute(text("SELECT CASE WHEN OBJECT_ID(N'dbo.item_unit_conversions', N'U') IS NULL THEN 0 ELSE 1 END")).scalar())
        if has_conversions:
            sql = """
                SELECT unit_name FROM (
                    SELECT LTRIM(RTRIM(base_uom)) AS unit_name FROM dbo.items WHERE ISNULL(base_uom, N'') <> N''
                    UNION
                    SELECT LTRIM(RTRIM(purchase_uom)) AS unit_name FROM dbo.items WHERE ISNULL(purchase_uom, N'') <> N''
                    UNION
                    SELECT LTRIM(RTRIM(sales_uom)) AS unit_name FROM dbo.items WHERE ISNULL(sales_uom, N'') <> N''
                    UNION
                    SELECT LTRIM(RTRIM(order_uom)) AS unit_name FROM dbo.item_unit_conversions WHERE ISNULL(order_uom, N'') <> N''
                ) u
                WHERE unit_name IS NOT NULL AND unit_name <> N''
                ORDER BY unit_name
            """
        else:
            sql = """
                SELECT unit_name FROM (
                    SELECT LTRIM(RTRIM(base_uom)) AS unit_name FROM dbo.items WHERE ISNULL(base_uom, N'') <> N''
                    UNION
                    SELECT LTRIM(RTRIM(purchase_uom)) AS unit_name FROM dbo.items WHERE ISNULL(purchase_uom, N'') <> N''
                    UNION
                    SELECT LTRIM(RTRIM(sales_uom)) AS unit_name FROM dbo.items WHERE ISNULL(sales_uom, N'') <> N''
                ) u
                WHERE unit_name IS NOT NULL AND unit_name <> N''
                ORDER BY unit_name
            """
        rows = db.execute(text(sql)).mappings().all()
        for r in rows:
            add_unit(r["unit_name"])
    except Exception:
        pass

    try:
        has_standard = bool(db.execute(text("SELECT CASE WHEN OBJECT_ID(N'dbo.uom_standard_conversions', N'U') IS NULL THEN 0 ELSE 1 END")).scalar())
        if has_standard:
            rows = db.execute(text("""
                SELECT LTRIM(RTRIM(from_uom)) AS unit_name FROM dbo.uom_standard_conversions WHERE is_active = 1 AND ISNULL(from_uom, N'') <> N''
                UNION
                SELECT LTRIM(RTRIM(to_uom)) AS unit_name FROM dbo.uom_standard_conversions WHERE is_active = 1 AND ISNULL(to_uom, N'') <> N''
            """)).mappings().all()
            for r in rows:
                add_unit(r["unit_name"])
    except Exception:
        pass

    return sorted(units, key=lambda x: x.lower())

def _standard_conversion_rate(db: Session, order_uom: str | None, base_uom: str | None) -> Decimal | None:
    order = (order_uom or "").strip()
    base = (base_uom or "").strip()
    if not order or not base:
        return None
    if order.lower() == base.lower():
        return Decimal("1")
    try:
        has_table = bool(db.execute(text("SELECT CASE WHEN OBJECT_ID(N'dbo.uom_standard_conversions', N'U') IS NULL THEN 0 ELSE 1 END")).scalar())
        if has_table:
            row = db.execute(text("""
                SELECT TOP 1 rate_to_base
                FROM dbo.uom_standard_conversions
                WHERE is_active = 1
                  AND LOWER(from_uom) = LOWER(:order_uom)
                  AND LOWER(to_uom) = LOWER(:base_uom)
                ORDER BY id DESC
            """), {"order_uom": order, "base_uom": base}).mappings().first()
            if row and row["rate_to_base"] is not None:
                rate = Decimal(str(row["rate_to_base"] or 0))
                if rate > 0:
                    return rate
    except Exception:
        pass
    aliases = {
        "g": "gram", "gram": "gram", "grams": "gram",
        "kg": "kg", "kilogram": "kg", "kilograms": "kg",
        "ml": "ml", "milliliter": "ml", "millilitre": "ml",
        "l": "liter", "lt": "liter", "liter": "liter", "litre": "liter",
        "cm": "cm", "centimeter": "cm", "centimetre": "cm",
        "m": "m", "meter": "m", "metre": "m",
    }
    order_key = aliases.get(order.lower(), order.lower())
    base_key = aliases.get(base.lower(), base.lower())
    standard = {
        ("gram", "kg"): Decimal("0.001"),
        ("kg", "gram"): Decimal("1000"),
        ("ml", "liter"): Decimal("0.001"),
        ("liter", "ml"): Decimal("1000"),
        ("cm", "m"): Decimal("0.01"),
        ("m", "cm"): Decimal("100"),
    }
    return standard.get((order_key, base_key))


def _vendor_price_history(
    db: Session,
    vendor_id: int | None,
    item_id: int | None,
    limit: int = 8,
    order_uom: str | None = None,
    order_to_base_rate: Decimal | str | None = None,
):
    """Return vendor price history as Unit Price in the current line Order Unit.

    Important rule from v94:
    - GR/Inventory stores cost by Base Unit.  Example: 1 kg = 1000 gram,
      receipt amount = 150,000 VND → stock cost = 150 VND/gram.
    - Get Price must return Unit Price for the line's current Order Unit:
        Order Unit gram → 150
        Order Unit kg   → 150,000
    - Do not return GR total amount as unit price.

    To avoid historical rows that may have been saved with the wrong amount,
    PR/PO Get Price derives PURCHASE_ORDER and GOODS_RECEIPT prices directly
    from document lines whenever those tables are available.
    """
    if not vendor_id or not item_id:
        return []

    try:
        target_rate = Decimal(str(order_to_base_rate if order_to_base_rate not in (None, "") else "1"))
        if target_rate <= 0:
            target_rate = Decimal("1")
    except Exception:
        target_rate = Decimal("1")

    # Prefer document-line history because it contains UoM/rate context.
    # The UNION returns prices converted to the requested Order Unit.
    try:
        return db.execute(text("""
            WITH hist AS (
                SELECT
                    po.po_date AS doc_date,
                    N'PURCHASE_ORDER' AS source_doc_type,
                    CAST(
                        CASE
                            WHEN COALESCE(pol.order_to_base_rate, 0) > 0
                                THEN (COALESCE(pol.unit_price, 0) / NULLIF(pol.order_to_base_rate, 0)) * :target_rate
                            ELSE COALESCE(pol.unit_price, 0)
                        END
                    AS DECIMAL(18, 4)) AS unit_price,
                    N'VND' AS currency_code,
                    po.id AS sort_doc_id,
                    pol.id AS sort_line_id
                FROM dbo.purchase_order_lines pol
                JOIN dbo.purchase_orders po ON po.id = pol.po_id
                WHERE po.vendor_id = :vendor_id
                  AND pol.item_id = :item_id
                  AND ISNULL(po.status, N'') <> N'CANCELED'

                UNION ALL

                SELECT
                    gr.gr_date AS doc_date,
                    N'GOODS_RECEIPT' AS source_doc_type,
                    CAST(
                        CASE
                            WHEN COALESCE(grl.unit_cost, 0) > 0
                                THEN COALESCE(grl.unit_cost, 0) * :target_rate
                            WHEN COALESCE(grl.order_to_base_rate, 0) > 0
                                THEN (COALESCE(grl.order_unit_cost, 0) / NULLIF(grl.order_to_base_rate, 0)) * :target_rate
                            ELSE COALESCE(grl.order_unit_cost, 0)
                        END
                    AS DECIMAL(18, 4)) AS unit_price,
                    N'VND' AS currency_code,
                    gr.id AS sort_doc_id,
                    grl.id AS sort_line_id
                FROM dbo.goods_receipt_lines grl
                JOIN dbo.goods_receipts gr ON gr.id = grl.gr_id
                WHERE gr.vendor_id = :vendor_id
                  AND grl.item_id = :item_id
                  AND ISNULL(gr.status, N'') <> N'CANCELED'

                UNION ALL

                SELECT
                    vph.doc_date AS doc_date,
                    vph.source_doc_type AS source_doc_type,
                    CAST(vph.unit_price AS DECIMAL(18, 4)) AS unit_price,
                    COALESCE(vph.currency_code, N'VND') AS currency_code,
                    vph.id AS sort_doc_id,
                    vph.id AS sort_line_id
                FROM dbo.vendor_price_history vph
                WHERE vph.vendor_id = :vendor_id
                  AND vph.item_id = :item_id
                  AND ISNULL(vph.source_doc_type, N'') NOT IN (N'PURCHASE_ORDER', N'GOODS_RECEIPT')
            )
            SELECT TOP (:limit)
                doc_date,
                source_doc_type,
                unit_price,
                currency_code
            FROM hist
            WHERE COALESCE(unit_price, 0) >= 0
            ORDER BY doc_date DESC, sort_doc_id DESC, sort_line_id DESC
        """), {
            "vendor_id": vendor_id,
            "item_id": item_id,
            "limit": limit,
            "target_rate": target_rate,
        }).mappings().all()
    except Exception:
        # Fallback for older databases that do not have the new UoM columns yet.
        return db.execute(text("""
            SELECT TOP (:limit) doc_date, source_doc_type, unit_price, currency_code
            FROM dbo.vendor_price_history
            WHERE vendor_id=:vendor_id AND item_id=:item_id
            ORDER BY doc_date DESC, id DESC
        """), {"vendor_id": vendor_id, "item_id": item_id, "limit": limit}).mappings().all()


def _serialize_price_history(rows):
    return [{"doc_date": r["doc_date"].isoformat() if hasattr(r["doc_date"], "isoformat") else str(r["doc_date"] or ""), "source_doc_type": r["source_doc_type"] or "", "unit_price": str(r["unit_price"] or 0), "currency_code": r["currency_code"] or "VND"} for r in rows]


def _pr_lines(db: Session, pr_id: int):
    return db.execute(text("""
        SELECT l.*, i.item_code, i.item_name, i.base_uom AS item_base_uom, w.warehouse_code, w.warehouse_name, t.tax_code
        FROM dbo.purchase_requisition_lines l
        JOIN dbo.items i ON i.id = l.item_id
        JOIN dbo.warehouses w ON w.id = l.warehouse_id
        LEFT JOIN dbo.tax_codes t ON t.id = l.tax_code_id
        WHERE l.pr_id=:id ORDER BY l.line_no
    """), {"id": pr_id}).mappings().all()


def _po_lines(db: Session, po_id: int):
    return db.execute(text("""
        SELECT l.*, i.item_code, i.item_name, i.base_uom AS item_base_uom, w.warehouse_code, w.warehouse_name, t.tax_code, pr.pr_no, prl.line_no AS pr_line_no
        FROM dbo.purchase_order_lines l
        JOIN dbo.items i ON i.id = l.item_id
        JOIN dbo.warehouses w ON w.id = l.warehouse_id
        LEFT JOIN dbo.tax_codes t ON t.id = l.tax_code_id
        LEFT JOIN dbo.purchase_requisition_lines prl ON prl.id = l.pr_line_id
        LEFT JOIN dbo.purchase_requisitions pr ON pr.id = prl.pr_id
        WHERE l.po_id=:id ORDER BY l.line_no
    """), {"id": po_id}).mappings().all()


def _released_pr_lines(db: Session):
    return db.execute(text("""
        SELECT l.id, l.pr_id, pr.pr_no, pr.vendor_id, bp.bp_code, bp.bp_name,
               i.item_code, i.item_name, l.item_id, l.warehouse_id, w.warehouse_code,
               l.line_no, l.quantity, l.base_quantity, COALESCE(l.base_uom, i.base_uom) AS base_uom, COALESCE(l.order_uom, i.base_uom) AS order_uom, COALESCE(l.order_to_base_rate, 1) AS order_to_base_rate, l.expected_unit_price, l.tax_code_id, l.required_date
        FROM dbo.purchase_requisition_lines l
        JOIN dbo.purchase_requisitions pr ON pr.id = l.pr_id
        LEFT JOIN dbo.business_partners bp ON bp.id = pr.vendor_id
        JOIN dbo.items i ON i.id = l.item_id
        JOIN dbo.warehouses w ON w.id = l.warehouse_id
        WHERE pr.status=N'RELEASED' AND l.po_line_id IS NULL
        ORDER BY pr.id DESC, l.line_no
    """)).mappings().all()


def _serialize_released_pr_lines(rows):
    data = []
    for r in rows:
        data.append({
            "id": int(r["id"]),
            "pr_id": int(r["pr_id"]),
            "pr_no": str(r["pr_no"] or ""),
            "vendor_id": int(r["vendor_id"] or 0),
            "bp_code": str(r["bp_code"] or ""),
            "bp_name": str(r["bp_name"] or ""),
            "line_no": int(r["line_no"] or 0),
            "item_id": int(r["item_id"] or 0),
            "item_code": str(r["item_code"] or ""),
            "item_name": str(r["item_name"] or ""),
            "warehouse_id": int(r["warehouse_id"] or 0),
            "warehouse_code": str(r["warehouse_code"] or ""),
            "quantity": str(r["quantity"] or 0),
            "base_quantity": str(r["base_quantity"] or 0),
            "base_uom": str(r["base_uom"] or ""),
            "order_uom": str(r["order_uom"] or ""),
            "order_to_base_rate": str(r["order_to_base_rate"] or 1),
            "expected_unit_price": str(r["expected_unit_price"] or 0),
            "tax_code_id": int(r["tax_code_id"] or 0),
            "required_date": r["required_date"].isoformat() if hasattr(r["required_date"], "isoformat") else str(r["required_date"] or ""),
        })
    return data

def _selected_pr_doc(db: Session, pr_id: int | None):
    if not pr_id:
        return None
    return db.execute(text("""
        SELECT pr.id, pr.pr_no, pr.pr_date, pr.vendor_id, bp.bp_code, bp.bp_name, pr.total_amount
        FROM dbo.purchase_requisitions pr
        LEFT JOIN dbo.business_partners bp ON bp.id = pr.vendor_id
        WHERE pr.id=:id
    """), {"id": pr_id}).mappings().first()


def _released_prs(db: Session):
    return db.execute(text("""
        SELECT pr.id, pr.pr_no, pr.pr_date, pr.vendor_id, bp.bp_code, bp.bp_name,
               pr.total_amount, COUNT(l.id) AS open_line_count
        FROM dbo.purchase_requisitions pr
        LEFT JOIN dbo.business_partners bp ON bp.id = pr.vendor_id
        JOIN dbo.purchase_requisition_lines l ON l.pr_id = pr.id
        WHERE pr.status=N'RELEASED' AND l.po_line_id IS NULL
        GROUP BY pr.id, pr.pr_no, pr.pr_date, pr.vendor_id, bp.bp_code, bp.bp_name, pr.total_amount
        ORDER BY pr.id DESC
    """)).mappings().all()


def _open_po_lines(db: Session):
    return db.execute(text("""
        SELECT l.id, l.po_id, l.line_no, po.po_no, po.po_date, po.vendor_id, bp.bp_code, bp.bp_name,
               i.id AS item_id, i.item_code, i.item_name,
               w.id AS warehouse_id, w.warehouse_code, w.warehouse_name,
               l.quantity, l.received_qty, (l.quantity-l.received_qty) AS open_qty, l.base_quantity, COALESCE(l.base_received_qty, l.received_qty * COALESCE(l.order_to_base_rate, 1)) AS base_received_qty, COALESCE(l.base_uom, i.base_uom) AS base_uom, COALESCE(l.order_uom, i.base_uom) AS order_uom, COALESCE(l.order_to_base_rate, 1) AS order_to_base_rate, l.unit_price,
               po.in_transit_posted
        FROM dbo.purchase_order_lines l
        JOIN dbo.purchase_orders po ON po.id = l.po_id
        JOIN dbo.business_partners bp ON bp.id = po.vendor_id
        JOIN dbo.items i ON i.id = l.item_id
        JOIN dbo.warehouses w ON w.id = l.warehouse_id
        WHERE po.status IN (N'RELEASED', N'PARTIALLY_RECEIVED') AND (l.quantity-l.received_qty) > 0
        ORDER BY po.id DESC, l.line_no
    """)).mappings().all()


@router.get("")
def purchase_index(request: Request, db: Session = Depends(get_db), user=Depends(require_permission("PURCHASE_VIEW"))):
    stats = db.execute(text("""
        SELECT (SELECT COUNT(1) FROM dbo.purchase_requisitions WHERE status=N'DRAFT') AS draft_pr,
               (SELECT COUNT(1) FROM dbo.purchase_requisitions WHERE status=N'RELEASED') AS released_pr,
               (SELECT COUNT(1) FROM dbo.purchase_requisitions WHERE status=N'PO_CREATED') AS po_created_pr,
               (SELECT COUNT(1) FROM dbo.purchase_orders WHERE status=N'DRAFT') AS draft_po,
               (SELECT COUNT(1) FROM dbo.purchase_orders WHERE status=N'RELEASED') AS released_po,
               (SELECT COUNT(1) FROM dbo.purchase_orders WHERE status=N'PARTIALLY_RECEIVED') AS partial_po,
               (SELECT COUNT(1) FROM dbo.goods_receipts) AS gr_count
    """)).mappings().first()
    recent_pr = db.execute(text("""SELECT TOP 8 pr.id, pr.pr_no, pr.pr_date, pr.status, bp.bp_code, bp.bp_name, pr.total_amount FROM dbo.purchase_requisitions pr LEFT JOIN dbo.business_partners bp ON bp.id = pr.vendor_id ORDER BY pr.id DESC""")).mappings().all()
    recent_po = db.execute(text("""SELECT TOP 8 po.id, po.po_no, po.po_date, po.status, bp.bp_code, bp.bp_name, po.total_amount, po.in_transit_posted FROM dbo.purchase_orders po JOIN dbo.business_partners bp ON bp.id = po.vendor_id ORDER BY po.id DESC""")).mappings().all()
    return templates.TemplateResponse("purchase.html", {"request": request, "user": user, "stats": stats, "recent_pr": recent_pr, "recent_po": recent_po})


@router.get("/pr")
def pr_list(
    request: Request,
    status: str = "DRAFT",
    pr_no_from: str = "",
    pr_no_to: str = "",
    date_from: str = "",
    date_to: str = "",
    vendor_q: str = "",
    amount_from: str = "",
    amount_to: str = "",
    db: Session = Depends(get_db),
    user=Depends(require_permission("PURCHASE_VIEW")),
):
    """PR management query screen.

    The list page is now a selection screen + result list. It should be used to
    find the transaction first; document actions live on the document screen.
    """
    params = {
        "status": (status or "").strip(),
        "pr_no_from": (pr_no_from or "").strip(),
        "pr_no_to": (pr_no_to or "").strip(),
        "date_from": (date_from or "").strip(),
        "date_to": (date_to or "").strip(),
        "vendor_q": f"%{(vendor_q or '').strip()}%" if (vendor_q or "").strip() else "",
        "amount_from": None,
        "amount_to": None,
    }
    try:
        params["amount_from"] = Decimal(str(amount_from)) if str(amount_from or "").strip() else None
    except Exception:
        params["amount_from"] = None
    try:
        params["amount_to"] = Decimal(str(amount_to)) if str(amount_to or "").strip() else None
    except Exception:
        params["amount_to"] = None

    rows = db.execute(text("""
        SELECT TOP 500
               pr.id,
               pr.pr_no,
               pr.pr_date,
               pr.status,
               pr.total_amount,
               bp.bp_code,
               bp.bp_name,
               COUNT(l.id) AS total_items,
               SUM(CASE WHEN l.po_line_id IS NULL THEN 1 ELSE 0 END) AS open_items,
               SUM(CASE WHEN l.po_line_id IS NOT NULL THEN 1 ELSE 0 END) AS po_created_items,
               SUM(ISNULL(l.quantity,0)) AS total_qty,
               MIN(i.item_code) AS first_item_code,
               MIN(i.item_name) AS first_item_name
        FROM dbo.purchase_requisitions pr
        LEFT JOIN dbo.business_partners bp ON bp.id = pr.vendor_id
        LEFT JOIN dbo.purchase_requisition_lines l ON l.pr_id = pr.id
        LEFT JOIN dbo.items i ON i.id = l.item_id
        WHERE (:status = N'' OR pr.status = :status)
          AND (:pr_no_from = N'' OR pr.pr_no >= :pr_no_from)
          AND (:pr_no_to = N'' OR pr.pr_no <= :pr_no_to)
          AND (:date_from = N'' OR pr.pr_date >= CONVERT(date, :date_from))
          AND (:date_to = N'' OR pr.pr_date <= CONVERT(date, :date_to))
          AND (:vendor_q = N'' OR bp.bp_code LIKE :vendor_q OR bp.bp_name LIKE :vendor_q)
          AND (:amount_from IS NULL OR ISNULL(pr.total_amount,0) >= :amount_from)
          AND (:amount_to IS NULL OR ISNULL(pr.total_amount,0) <= :amount_to)
        GROUP BY pr.id, pr.pr_no, pr.pr_date, pr.status, pr.total_amount, bp.bp_code, bp.bp_name
        ORDER BY pr.id DESC
    """), params).mappings().all()
    filters = {
        "status": params["status"],
        "pr_no_from": params["pr_no_from"],
        "pr_no_to": params["pr_no_to"],
        "date_from": params["date_from"],
        "date_to": params["date_to"],
        "vendor_q": (vendor_q or "").strip(),
        "amount_from": str(amount_from or ""),
        "amount_to": str(amount_to or ""),
    }
    existing_statuses = [r["status"] for r in db.execute(text("SELECT DISTINCT status FROM dbo.purchase_requisitions ORDER BY status")).mappings().all()]
    status_options = []
    for st in ["DRAFT", "RELEASED", "PO_CREATED", "CANCELLED", *existing_statuses]:
        if st and st not in status_options:
            status_options.append(st)
    return templates.TemplateResponse("purchase_pr_list.html", {"request": request, "user": user, "rows": rows, "filters": filters, "status_options": status_options})


@router.get("/pr/new")
def pr_new(request: Request, db: Session = Depends(get_db), user=Depends(require_permission("PURCHASE_EDIT"))):
    vendors, items, warehouses, tax_codes = _master_data(db)
    return templates.TemplateResponse("purchase_pr_form.html", {"request": request, "user": user, "mode": "new", "doc": None, "lines": [], "vendors": vendors, "items": items, "warehouses": warehouses, "tax_codes": tax_codes, "unit_options": _unit_options(db), "price_history": [], "default_pr_date": date.today().isoformat(), "default_requested_by": user.get("full_name") or user.get("username") or ""})


@router.get("/pr/price-history")
def pr_price_history(
    vendor_id: int = 0,
    item_id: int = 0,
    order_uom: str = "",
    order_to_base_rate: str = "1",
    db: Session = Depends(get_db),
    user=Depends(require_permission("PURCHASE_VIEW")),
):
    data = _serialize_price_history(_vendor_price_history(db, vendor_id or None, item_id or None, order_uom=order_uom, order_to_base_rate=order_to_base_rate))
    return JSONResponse({"rows": data, "latest_price": data[0]["unit_price"] if data else ""})




@router.get("/pr/latest-prices")
def pr_latest_prices(vendor_id: int = 0, item_ids: str = "", order_to_base_rate: str = "1", db: Session = Depends(get_db), user=Depends(require_permission("PURCHASE_VIEW"))):
    """Return latest vendor price for many PR line items in one request.

    This endpoint intentionally returns a mapping by item_id so the PR screen can
    update every line at once instead of only the active/cursor line.
    """
    item_id_list: list[int] = []
    for raw in str(item_ids or "").split(","):
        raw = raw.strip()
        if not raw:
            continue
        try:
            item_id = int(raw)
        except ValueError:
            continue
        if item_id > 0 and item_id not in item_id_list:
            item_id_list.append(item_id)

    prices: dict[str, str] = {}
    if vendor_id and item_id_list:
        for item_id in item_id_list:
            rows = _vendor_price_history(db, vendor_id, item_id, limit=1, order_to_base_rate=order_to_base_rate)
            if rows:
                prices[str(item_id)] = str(rows[0]["unit_price"] or 0)

    return JSONResponse({"prices": prices})


@router.get("/po/price-history")
def po_price_history(
    vendor_id: int = 0,
    item_id: int = 0,
    order_uom: str = "",
    order_to_base_rate: str = "1",
    db: Session = Depends(get_db),
    user=Depends(require_permission("PURCHASE_VIEW")),
):
    data = _serialize_price_history(_vendor_price_history(db, vendor_id or None, item_id or None, order_uom=order_uom, order_to_base_rate=order_to_base_rate))
    return JSONResponse({"rows": data, "latest_price": data[0]["unit_price"] if data else ""})




@router.get("/item-purchase-defaults")
def item_purchase_defaults(item_id: int = 0, order_uom: str = "", db: Session = Depends(get_db), user=Depends(require_permission("PURCHASE_VIEW"))):
    if not item_id:
        return JSONResponse({"ok": False, "error": "Missing item_id"})
    row = db.execute(text("""
        SELECT id, base_uom, purchase_uom, standard_cost, input_tax_code_id
        FROM dbo.items
        WHERE id=:item_id
    """), {"item_id": item_id}).mappings().first()
    if not row:
        return JSONResponse({"ok": False, "error": "Item not found"})
    base_uom = str(row["base_uom"] or "")
    selected_uom = str(order_uom or row["purchase_uom"] or base_uom or "").strip()
    rate = Decimal("1")
    has_conversion_table = bool(db.execute(text("SELECT CASE WHEN OBJECT_ID(N'dbo.item_unit_conversions', N'U') IS NULL THEN 0 ELSE 1 END")).scalar())
    if has_conversion_table and selected_uom and base_uom and selected_uom.lower() != base_uom.lower():
        conv = db.execute(text("""
            SELECT TOP 1 conversion_rate_to_base
            FROM dbo.item_unit_conversions
            WHERE item_id=:item_id AND LOWER(order_uom)=LOWER(:order_uom) AND is_active=1
            ORDER BY id DESC
        """), {"item_id": item_id, "order_uom": selected_uom}).mappings().first()
        if conv and conv["conversion_rate_to_base"] is not None:
            rate = Decimal(str(conv["conversion_rate_to_base"] or 1))
    if rate <= 0 or (rate == Decimal("1") and selected_uom and base_uom and selected_uom.lower() != base_uom.lower()):
        standard_rate = _standard_conversion_rate(db, selected_uom, base_uom)
        if standard_rate and standard_rate > 0:
            rate = standard_rate
    standard_cost = Decimal(str(row["standard_cost"] or 0))
    return JSONResponse({
        "ok": True,
        "item_id": item_id,
        "base_uom": base_uom,
        "order_uom": selected_uom,
        "order_to_base_rate": str(rate),
        "standard_cost": str(standard_cost),
        "default_order_unit_price": "0",
        "input_tax_code_id": int(row["input_tax_code_id"] or 0),
    })


@router.get("/pr/{pr_id}")
def pr_view(pr_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_permission("PURCHASE_VIEW"))):
    vendors, items, warehouses, tax_codes = _master_data(db)
    doc = db.execute(text("SELECT * FROM dbo.purchase_requisitions WHERE id=:id"), {"id": pr_id}).mappings().first()
    if not doc:
        return _safe_redirect("/purchase/pr", error="PR not found.")
    lines = _pr_lines(db, pr_id)
    first_line = lines[0] if lines else None
    return templates.TemplateResponse("purchase_pr_form.html", {"request": request, "user": user, "mode": "view", "view_mode": True, "doc": doc, "lines": lines, "vendors": vendors, "items": items, "warehouses": warehouses, "tax_codes": tax_codes, "unit_options": _unit_options(db), "price_history": _vendor_price_history(db, doc["vendor_id"] if doc else None, first_line["item_id"] if first_line else None), "default_pr_date": date.today().isoformat(), "default_requested_by": user.get("full_name") or user.get("username") or ""})

@router.get("/pr/{pr_id}/edit")
def pr_edit(pr_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_permission("PURCHASE_EDIT"))):
    vendors, items, warehouses, tax_codes = _master_data(db)
    doc = db.execute(text("SELECT * FROM dbo.purchase_requisitions WHERE id=:id"), {"id": pr_id}).mappings().first()
    lines = _pr_lines(db, pr_id)
    first_line = lines[0] if lines else None
    return templates.TemplateResponse("purchase_pr_form.html", {"request": request, "user": user, "mode": "edit", "doc": doc, "lines": lines, "vendors": vendors, "items": items, "warehouses": warehouses, "tax_codes": tax_codes, "unit_options": _unit_options(db), "price_history": _vendor_price_history(db, doc["vendor_id"] if doc else None, first_line["item_id"] if first_line else None), "default_pr_date": date.today().isoformat(), "default_requested_by": user.get("full_name") or user.get("username") or ""})


def _extract_pr_lines(form) -> list[dict]:
    item_ids, warehouse_ids, quantities, prices = form.getlist("line_item_id"), form.getlist("line_warehouse_id"), form.getlist("line_quantity"), form.getlist("line_expected_unit_price")
    tax_codes, required_dates = form.getlist("line_tax_code_id"), form.getlist("line_required_date")
    order_uoms, rates = form.getlist("line_order_uom"), form.getlist("line_order_to_base_rate")
    lines = []
    for idx, item_id in enumerate(item_ids):
        req = required_dates[idx] if idx < len(required_dates) else ""
        lines.append({"item_id": _to_int(item_id), "warehouse_id": _to_int(warehouse_ids[idx] if idx < len(warehouse_ids) else 0), "quantity": _to_decimal(quantities[idx] if idx < len(quantities) else 0), "order_uom": (order_uoms[idx] if idx < len(order_uoms) else ""), "order_to_base_rate": _to_decimal(rates[idx] if idx < len(rates) else 1, "1"), "expected_unit_price": _to_decimal(prices[idx] if idx < len(prices) else 0), "tax_code_id": _to_int(tax_codes[idx] if idx < len(tax_codes) else 0) or None, "required_date": date.fromisoformat(req) if req else None})
    return lines


@router.post("/pr/save")
async def pr_save(request: Request, db: Session = Depends(get_db), user=Depends(require_permission("PURCHASE_EDIT"))):
    form = await request.form()
    saved_id = PurchaseService(db, int(user["id"])).save_pr(_to_int(form.get("pr_id")) or None, str(form.get("manual_pr_no") or "").strip() or None, _to_int(form.get("vendor_id")) or None, _extract_pr_lines(form), date.fromisoformat(str(form.get("pr_date"))) if form.get("pr_date") else date.today(), str(form.get("requested_by_name") or "").strip() or None, str(form.get("notes") or "").strip() or None)
    return _safe_redirect("/purchase/pr/new", success="Purchase requisition saved. The PR entry screen is ready for a new transaction.")


@router.get("/pr/{pr_id}/release")
def pr_release_page(pr_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_permission("PURCHASE_EDIT"))):
    doc = db.execute(text("""
        SELECT pr.*, bp.bp_code, bp.bp_name
        FROM dbo.purchase_requisitions pr
        LEFT JOIN dbo.business_partners bp ON bp.id = pr.vendor_id
        WHERE pr.id=:id
    """), {"id": pr_id}).mappings().first()
    return templates.TemplateResponse("purchase_pr_release.html", {"request": request, "user": user, "doc": doc, "lines": _pr_lines(db, pr_id)})


@router.post("/pr/{pr_id}/release")
def pr_release(pr_id: int, db: Session = Depends(get_db), user=Depends(require_permission("PURCHASE_EDIT"))):
    PurchaseService(db, int(user["id"])).release_pr(pr_id)
    return _safe_redirect("/purchase/pr/new", success="Purchase requisition released. The PR entry screen is ready for a new transaction.")


@router.post("/pr/{pr_id}/cancel")
async def pr_cancel(pr_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_permission("PURCHASE_EDIT"))):
    form = await request.form()
    try:
        PurchaseService(db, int(user["id"])).cancel_pr(pr_id, str(form.get("reason") or "").strip() or None)
        return _safe_redirect("/purchase/pr", success="Purchase requisition cancelled.")
    except Exception as exc:
        db.rollback()
        return _safe_redirect("/purchase/pr", error=str(exc)[:300])


@router.get("/po")
def po_list(
    request: Request,
    status: str = "DRAFT",
    po_no_from: str = "",
    po_no_to: str = "",
    date_from: str = "",
    date_to: str = "",
    vendor_q: str = "",
    amount_from: str = "",
    amount_to: str = "",
    git: str = "",
    db: Session = Depends(get_db),
    user=Depends(require_permission("PURCHASE_VIEW")),
):
    params = {
        "status": (status or "").strip(),
        "po_no_from": (po_no_from or "").strip(),
        "po_no_to": (po_no_to or "").strip(),
        "date_from": (date_from or "").strip(),
        "date_to": (date_to or "").strip(),
        "vendor_q": f"%{(vendor_q or '').strip()}%" if (vendor_q or "").strip() else "",
        "git": (git or "").strip(),
        "amount_from": None,
        "amount_to": None,
    }
    try:
        params["amount_from"] = Decimal(str(amount_from)) if str(amount_from or "").strip() else None
    except Exception:
        params["amount_from"] = None
    try:
        params["amount_to"] = Decimal(str(amount_to)) if str(amount_to or "").strip() else None
    except Exception:
        params["amount_to"] = None

    rows = db.execute(text("""
        SELECT TOP 500
               po.id,
               po.po_no,
               po.po_date,
               po.status,
               po.total_amount,
               po.tax_amount,
               po.grand_total,
               po.in_transit_posted,
               bp.bp_code,
               bp.bp_name,
               COUNT(l.id) AS total_items,
               SUM(CASE WHEN ISNULL(l.quantity,0) - ISNULL(l.received_qty,0) > 0 THEN 1 ELSE 0 END) AS open_items,
               SUM(CASE WHEN ISNULL(l.received_qty,0) > 0 THEN 1 ELSE 0 END) AS received_items,
               SUM(ISNULL(l.quantity,0)) AS total_qty,
               SUM(ISNULL(l.received_qty,0)) AS received_qty,
               MIN(i.item_code) AS first_item_code,
               MIN(i.item_name) AS first_item_name
        FROM dbo.purchase_orders po
        JOIN dbo.business_partners bp ON bp.id = po.vendor_id
        LEFT JOIN dbo.purchase_order_lines l ON l.po_id = po.id
        LEFT JOIN dbo.items i ON i.id = l.item_id
        WHERE (:status = N'' OR po.status = :status)
          AND (:po_no_from = N'' OR po.po_no >= :po_no_from)
          AND (:po_no_to = N'' OR po.po_no <= :po_no_to)
          AND (:date_from = N'' OR po.po_date >= CONVERT(date, :date_from))
          AND (:date_to = N'' OR po.po_date <= CONVERT(date, :date_to))
          AND (:vendor_q = N'' OR bp.bp_code LIKE :vendor_q OR bp.bp_name LIKE :vendor_q)
          AND (:amount_from IS NULL OR ISNULL(po.grand_total,0) >= :amount_from)
          AND (:amount_to IS NULL OR ISNULL(po.grand_total,0) <= :amount_to)
          AND (:git = N'' OR (:git = N'Y' AND po.in_transit_posted = 1) OR (:git = N'N' AND ISNULL(po.in_transit_posted,0) = 0))
        GROUP BY po.id, po.po_no, po.po_date, po.status, po.total_amount, po.tax_amount, po.grand_total, po.in_transit_posted, bp.bp_code, bp.bp_name
        ORDER BY po.id DESC
    """), params).mappings().all()
    filters = {
        "status": params["status"],
        "po_no_from": params["po_no_from"],
        "po_no_to": params["po_no_to"],
        "date_from": params["date_from"],
        "date_to": params["date_to"],
        "vendor_q": (vendor_q or "").strip(),
        "amount_from": str(amount_from or ""),
        "amount_to": str(amount_to or ""),
        "git": params["git"],
    }
    status_options = [r["status"] for r in db.execute(text("SELECT DISTINCT status FROM dbo.purchase_orders ORDER BY status")).mappings().all()]
    return templates.TemplateResponse("purchase_po_list.html", {"request": request, "user": user, "rows": rows, "filters": filters, "status_options": status_options})


@router.get("/po/new")
def po_new(request: Request, pr_id: int = 0, pr_line_id: int = 0, db: Session = Depends(get_db), user=Depends(require_permission("PURCHASE_EDIT"))):
    vendors, items, warehouses, tax_codes = _master_data(db)
    released_pr_lines = _released_pr_lines(db)
    prefill_lines, selected_vendor, selected_pr_id = [], None, pr_id or None
    if pr_id:
        prefill_lines = db.execute(text("""
            SELECT l.id AS pr_line_id, l.*, pr.vendor_id, pr.pr_no
            FROM dbo.purchase_requisition_lines l
            JOIN dbo.purchase_requisitions pr ON pr.id = l.pr_id
            WHERE pr.id=:id AND pr.status=N'RELEASED' AND l.po_line_id IS NULL
            ORDER BY l.line_no
        """), {"id": pr_id}).mappings().all()
        if prefill_lines:
            selected_vendor = prefill_lines[0]["vendor_id"]
        else:
            return _safe_redirect(f"/purchase/pr/{pr_id}/edit", error="This PR is already PO Created or has no open PR lines for PO creation.")
    elif pr_line_id:
        prefill = db.execute(text("""
            SELECT l.id AS pr_line_id, l.*, pr.vendor_id, pr.pr_no, pr.id AS pr_id
            FROM dbo.purchase_requisition_lines l
            JOIN dbo.purchase_requisitions pr ON pr.id = l.pr_id
            WHERE l.id=:id AND pr.status=N'RELEASED' AND l.po_line_id IS NULL
        """), {"id": pr_line_id}).mappings().first()
        if prefill:
            selected_vendor, selected_pr_id, prefill_lines = prefill["vendor_id"], prefill["pr_id"], [prefill]
        else:
            return _safe_redirect("/purchase/po/new", error="This PR line is already used or its PR is not released.")
    return templates.TemplateResponse("purchase_po_form.html", {"request": request, "user": user, "mode": "new", "doc": None, "lines": prefill_lines, "vendors": vendors, "items": items, "warehouses": warehouses, "tax_codes": tax_codes, "unit_options": _unit_options(db), "released_prs": _released_prs(db), "released_pr_lines": released_pr_lines, "released_pr_lines_json": _serialize_released_pr_lines(released_pr_lines), "selected_vendor": selected_vendor, "selected_pr_id": selected_pr_id, "selected_pr_doc": _selected_pr_doc(db, selected_pr_id), "default_po_date": date.today().isoformat()})



@router.get("/po/{po_id}")
def po_view(po_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_permission("PURCHASE_VIEW"))):
    vendors, items, warehouses, tax_codes = _master_data(db)
    doc = db.execute(text("SELECT * FROM dbo.purchase_orders WHERE id=:id"), {"id": po_id}).mappings().first()
    if not doc:
        return _safe_redirect("/purchase/po", error="PO not found.")
    released_pr_lines = _released_pr_lines(db)
    selected_pr_id = doc["pr_id"] if doc and doc["pr_id"] else 0
    return templates.TemplateResponse("purchase_po_form.html", {"request": request, "user": user, "mode": "view", "view_mode": True, "doc": doc, "lines": _po_lines(db, po_id), "vendors": vendors, "items": items, "warehouses": warehouses, "tax_codes": tax_codes, "unit_options": _unit_options(db), "released_prs": _released_prs(db), "released_pr_lines": released_pr_lines, "released_pr_lines_json": _serialize_released_pr_lines(released_pr_lines), "selected_vendor": doc["vendor_id"] if doc else None, "selected_pr_id": selected_pr_id, "selected_pr_doc": _selected_pr_doc(db, selected_pr_id), "default_po_date": date.today().isoformat()})

@router.get("/po/{po_id}/edit")
def po_edit(po_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_permission("PURCHASE_EDIT"))):
    vendors, items, warehouses, tax_codes = _master_data(db)
    doc = db.execute(text("SELECT * FROM dbo.purchase_orders WHERE id=:id"), {"id": po_id}).mappings().first()
    released_pr_lines = _released_pr_lines(db)
    selected_pr_id = doc["pr_id"] if doc and "pr_id" in doc else None
    return templates.TemplateResponse("purchase_po_form.html", {"request": request, "user": user, "mode": "edit", "doc": doc, "lines": _po_lines(db, po_id), "vendors": vendors, "items": items, "warehouses": warehouses, "tax_codes": tax_codes, "unit_options": _unit_options(db), "released_prs": _released_prs(db), "released_pr_lines": released_pr_lines, "released_pr_lines_json": _serialize_released_pr_lines(released_pr_lines), "selected_vendor": doc["vendor_id"] if doc else None, "selected_pr_id": selected_pr_id, "selected_pr_doc": _selected_pr_doc(db, selected_pr_id), "default_po_date": date.today().isoformat()})


def _extract_po_lines(form) -> list[dict]:
    pr_line_ids, item_ids, warehouse_ids, quantities, prices, tax_codes = form.getlist("line_pr_line_id"), form.getlist("line_item_id"), form.getlist("line_warehouse_id"), form.getlist("line_quantity"), form.getlist("line_unit_price"), form.getlist("line_tax_code_id")
    order_uoms, rates = form.getlist("line_order_uom"), form.getlist("line_order_to_base_rate")
    lines = []
    for idx, item_id in enumerate(item_ids):
        lines.append({"pr_line_id": _to_int(pr_line_ids[idx] if idx < len(pr_line_ids) else 0) or None, "item_id": _to_int(item_id), "warehouse_id": _to_int(warehouse_ids[idx] if idx < len(warehouse_ids) else 0), "quantity": _to_decimal(quantities[idx] if idx < len(quantities) else 0), "order_uom": (order_uoms[idx] if idx < len(order_uoms) else ""), "order_to_base_rate": _to_decimal(rates[idx] if idx < len(rates) else 1, "1"), "unit_price": _to_decimal(prices[idx] if idx < len(prices) else 0), "tax_code_id": _to_int(tax_codes[idx] if idx < len(tax_codes) else 0) or None})
    return lines


@router.post("/po/save")
async def po_save(request: Request, db: Session = Depends(get_db), user=Depends(require_permission("PURCHASE_EDIT"))):
    form = await request.form()
    saved_id = PurchaseService(db, int(user["id"])).save_po(_to_int(form.get("po_id")) or None, str(form.get("manual_po_no") or "").strip() or None, _to_int(form.get("vendor_id")), _extract_po_lines(form), date.fromisoformat(str(form.get("po_date"))) if form.get("po_date") else date.today(), str(form.get("notes") or "").strip() or None, reference_pr_id=_to_int(form.get("reference_pr_id")) or None)
    return _safe_redirect("/purchase/po/new", success="Purchase order saved. The PO entry screen is ready for a new transaction.")


@router.get("/po/{po_id}/release")
def po_release_page(po_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_permission("PURCHASE_EDIT"))):
    doc = db.execute(text("""
        SELECT po.*, bp.bp_code, bp.bp_name
        FROM dbo.purchase_orders po
        JOIN dbo.business_partners bp ON bp.id = po.vendor_id
        WHERE po.id=:id
    """), {"id": po_id}).mappings().first()
    return templates.TemplateResponse("purchase_po_release.html", {"request": request, "user": user, "doc": doc, "lines": _po_lines(db, po_id)})


@router.post("/po/{po_id}/release")
def po_release(po_id: int, post_in_transit: str = Form(""), db: Session = Depends(get_db), user=Depends(require_permission("PURCHASE_EDIT"))):
    PurchaseService(db, int(user["id"])).release_po(po_id, post_in_transit == "on")
    return _safe_redirect("/purchase/po/new", success="Purchase order released. The PO entry screen is ready for a new transaction.")


@router.post("/po/{po_id}/cancel")
async def po_cancel(po_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_permission("PURCHASE_EDIT"))):
    form = await request.form()
    try:
        PurchaseService(db, int(user["id"])).cancel_po(po_id, str(form.get("reason") or "").strip() or None)
        return _safe_redirect("/purchase/po", success="Purchase order cancelled and reversal posted if needed.")
    except Exception as exc:
        db.rollback()
        return _safe_redirect("/purchase/po", error=str(exc)[:300])


@router.post("/receipt/{gr_id}/cancel")
async def receipt_cancel(gr_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_permission("PURCHASE_EDIT"))):
    form = await request.form()
    try:
        PurchaseService(db, int(user["id"])).cancel_goods_receipt(gr_id, str(form.get("reason") or "").strip() or None)
        return _safe_redirect("/purchase/receipts", success="Goods receipt cancelled and reversal posted.")
    except Exception as exc:
        db.rollback()
        return _safe_redirect("/purchase/receipts", error=str(exc)[:300])


@router.get("/receipts")
def receipt_page(request: Request, po_id: int = 0, po_line_id: int = 0, db: Session = Depends(get_db), user=Depends(require_permission("PURCHASE_VIEW"))):
    vendors, items, warehouses, _ = _master_data(db)
    open_po_lines = _open_po_lines(db)
    open_pos = db.execute(text("""
        SELECT po.id, po.po_no, po.po_date, po.vendor_id, bp.bp_code, bp.bp_name, SUM(l.quantity-l.received_qty) AS open_qty, SUM((l.quantity-l.received_qty) * l.unit_price) AS open_amount, MAX(CAST(po.in_transit_posted AS INT)) AS in_transit_posted
        FROM dbo.purchase_orders po JOIN dbo.business_partners bp ON bp.id = po.vendor_id JOIN dbo.purchase_order_lines l ON l.po_id = po.id
        WHERE po.status IN (N'RELEASED', N'PARTIALLY_RECEIVED') AND (l.quantity-l.received_qty) > 0
        GROUP BY po.id, po.po_no, po.po_date, po.vendor_id, bp.bp_code, bp.bp_name ORDER BY po.id DESC
    """)).mappings().all()
    receipts = db.execute(text("""
        SELECT TOP 30 gr.id, gr.gr_no, gr.gr_date, gr.status, bp.bp_code, bp.bp_name, je.je_no, po.po_no
        FROM dbo.goods_receipts gr
        JOIN dbo.business_partners bp ON bp.id = gr.vendor_id
        LEFT JOIN dbo.journal_entries je ON je.id = gr.journal_entry_id
        LEFT JOIN dbo.purchase_orders po ON po.id = gr.po_id
        ORDER BY gr.id DESC
    """)).mappings().all()
    return templates.TemplateResponse("purchase_receipt.html", {"request": request, "user": user, "vendors": vendors, "items": items, "warehouses": warehouses, "unit_options": _unit_options(db), "open_po_lines": open_po_lines, "open_pos": open_pos, "receipts": receipts, "selected_po_id": po_id, "selected_po_line_id": po_line_id})


@router.post("/receipt/post")
async def receipt_post(request: Request, db: Session = Depends(get_db), user=Depends(require_permission("PURCHASE_EDIT"))):
    form = await request.form()
    service = PurchaseService(db, int(user["id"]))
    mode = str(form.get("receipt_mode") or "manual")
    manual_gr_no = str(form.get("manual_gr_no") or "").strip() or None
    notes = str(form.get("notes") or "").strip() or None

    if mode == "po_line":
        selected_ids = [int(x) for x in form.getlist("selected_po_line_ids") if str(x).strip()]
        # Backward compatible fallback for older forms/bookmarks.
        if not selected_ids and _to_int(form.get("po_line_id")):
            selected_ids = [_to_int(form.get("po_line_id"))]
        line_quantities = []
        for line_id in selected_ids:
            qty_value = form.get(f"receipt_qty_{line_id}") or form.get("quantity")
            line_quantities.append({"po_line_id": line_id, "receipt_qty": _to_decimal(qty_value)})
        service.post_po_receipt_lines(_to_int(form.get("po_id")), line_quantities, date.today(), manual_gr_no, notes)
    elif mode == "po_all" and _to_int(form.get("po_id")):
        service.post_po_receipt_all(_to_int(form.get("po_id")), date.today(), manual_gr_no, notes)
    else:
        item_ids = form.getlist("manual_line_item_id") or form.getlist("item_id")
        warehouse_ids = form.getlist("manual_line_warehouse_id") or form.getlist("warehouse_id")
        quantities = form.getlist("manual_line_quantity") or form.getlist("quantity")
        unit_costs = form.getlist("manual_line_unit_cost") or form.getlist("unit_cost")
        order_uoms = form.getlist("manual_line_order_uom") or form.getlist("manual_order_uom")
        rates = form.getlist("manual_line_order_to_base_rate") or form.getlist("manual_order_to_base_rate")
        manual_lines = []
        for idx, item_id in enumerate(item_ids):
            manual_lines.append({
                "item_id": _to_int(item_id),
                "warehouse_id": _to_int(warehouse_ids[idx] if idx < len(warehouse_ids) else 0),
                "quantity": _to_decimal(quantities[idx] if idx < len(quantities) else 0),
                "unit_cost": _to_decimal(unit_costs[idx] if idx < len(unit_costs) else 0),
                "order_uom": str(order_uoms[idx] if idx < len(order_uoms) else "").strip() or None,
                "order_to_base_rate": _to_decimal(rates[idx] if idx < len(rates) else 1, "1"),
            })
        service.post_manual_receipt_lines(_to_int(form.get("vendor_id")), manual_lines, date.today(), manual_gr_no, notes)
    return _safe_redirect("/purchase/receipts", success="Goods receipt posted and FIFO layer created. The receipt screen is ready for a new transaction.")


@router.post("/quick-receipt")
def quick_receipt(request: Request, vendor_id: int = Form(...), item_id: int = Form(...), warehouse_id: int = Form(...), quantity: Decimal = Form(...), unit_cost: Decimal = Form(...), manual_gr_no: str = Form(""), db: Session = Depends(get_db), user=Depends(require_permission("PURCHASE_EDIT"))):
    PurchaseService(db, int(user["id"])).create_quick_purchase_receipt(vendor_id, item_id, warehouse_id, quantity, unit_cost, doc_date=date.today(), manual_gr_no=manual_gr_no.strip() or None)
    return _safe_redirect("/purchase/receipts", success="Goods receipt posted successfully. The receipt screen is ready for a new transaction.")
