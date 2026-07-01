from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.permissions import require_permission
from app.services.numbering_service import NumberingService
from app.services.posting_service import PostingService

router = APIRouter(prefix="/accounting", tags=["accounting"])
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


@router.get("")
def accounting_index(request: Request, db: Session = Depends(get_db), user=Depends(require_permission("ACCOUNTING_VIEW"))):
    trial_balance = db.execute(text("SELECT * FROM dbo.v_trial_balance ORDER BY account_code")).mappings().all()
    journals = db.execute(text("SELECT TOP 30 je_no, je_date, source_doc_type, source_doc_id, memo, status FROM dbo.journal_entries ORDER BY id DESC")).mappings().all()
    try:
        valuation_policies = db.execute(text("""
            SELECT TOP 20 id, fiscal_year, valuation_method, effective_from, note, is_active
            FROM dbo.inventory_valuation_policies
            ORDER BY fiscal_year DESC, effective_from DESC, id DESC
        """)).mappings().all()
    except Exception:
        valuation_policies = []
    asset_summary = {"cost": 0, "accumulated": 0, "nbv": 0, "active_count": 0}
    try:
        row = db.execute(text("""
            SELECT
                COUNT(1) AS active_count,
                SUM(acquisition_cost) AS cost,
                SUM(accumulated_depreciation) AS accumulated,
                SUM(net_book_value) AS nbv
            FROM dbo.v_asset_nbv
            WHERE is_active = 1
        """)).mappings().first()
        if row:
            asset_summary = {
                "cost": row["cost"] or 0,
                "accumulated": row["accumulated"] or 0,
                "nbv": row["nbv"] or 0,
                "active_count": row["active_count"] or 0,
            }
    except Exception:
        pass
    return templates.TemplateResponse("accounting.html", {"request": request, "user": user, "trial_balance": trial_balance, "journals": journals, "asset_summary": asset_summary, "valuation_policies": valuation_policies, "today": date.today()})


@router.post("/valuation-policy/save")
async def save_valuation_policy(request: Request, db: Session = Depends(get_db), user=Depends(require_permission("ACCOUNTING_EDIT"))):
    form = await request.form()
    try:
        fiscal_year = int(form.get("fiscal_year") or date.today().year)
        valuation_method = str(form.get("valuation_method") or "FIFO").upper()
        effective_from = date.fromisoformat(str(form.get("effective_from") or date.today().isoformat()))
        note = str(form.get("note") or "").strip() or None
        if valuation_method not in ("FIFO", "LIFO", "WEIGHTED_AVG"):
            raise ValueError("Valuation method không hợp lệ.")
        db.execute(text("UPDATE dbo.inventory_valuation_policies SET is_active = 0 WHERE fiscal_year = :fiscal_year"), {"fiscal_year": fiscal_year})
        db.execute(text("""
            INSERT INTO dbo.inventory_valuation_policies(fiscal_year, valuation_method, effective_from, note, is_active, created_by)
            VALUES(:fiscal_year, :valuation_method, :effective_from, :note, 1, :created_by)
        """), {
            "fiscal_year": fiscal_year,
            "valuation_method": valuation_method,
            "effective_from": effective_from,
            "note": note,
            "created_by": int(user["id"]),
        })
        db.commit()
        return _safe_redirect("/accounting", success="Inventory valuation policy saved.")
    except (ValueError, SQLAlchemyError) as exc:
        db.rollback()
        return _safe_redirect("/accounting", error=str(exc)[:300])
    except Exception as exc:
        db.rollback()
        return _safe_redirect("/accounting", error=f"Không thể lưu valuation policy: {str(exc)[:300]}")


@router.get("/assets")
def accounting_assets(request: Request, db: Session = Depends(get_db), user=Depends(require_permission("ACCOUNTING_VIEW"))):
    assets = db.execute(text("""
        SELECT TOP 300 *
        FROM dbo.v_asset_nbv
        ORDER BY asset_type, asset_code
    """)).mappings().all()
    runs = db.execute(text("""
        SELECT TOP 30 r.run_no, r.period_year, r.period_month, r.run_type, r.posting_date,
               r.total_amount, r.status, je.je_no
        FROM dbo.asset_depreciation_runs r
        LEFT JOIN dbo.journal_entries je ON je.id = r.journal_entry_id
        ORDER BY r.id DESC
    """)).mappings().all()
    return templates.TemplateResponse("accounting_assets.html", {"request": request, "user": user, "assets": assets, "runs": runs, "today": date.today()})


@router.post("/assets/depreciation-run")
async def post_asset_depreciation_run(request: Request, db: Session = Depends(get_db), user=Depends(require_permission("ACCOUNTING_EDIT"))):
    form = await request.form()
    try:
        period_year = int(form.get("period_year") or date.today().year)
        period_month = int(form.get("period_month") or date.today().month)
        if period_month < 1 or period_month > 12:
            raise ValueError("Period month không hợp lệ.")
        posting_date = date.fromisoformat(str(form.get("posting_date") or date.today().isoformat()))
        run_type = str(form.get("run_type") or "MONTHLY_DEPRECIATION")
        memo = str(form.get("memo") or f"Depreciation/allocation {period_year}-{period_month:02d}")

        existing = db.execute(text("""
            SELECT TOP 1 run_no
            FROM dbo.asset_depreciation_runs
            WHERE period_year = :period_year AND period_month = :period_month AND run_type = :run_type AND status = N'POSTED'
        """), {"period_year": period_year, "period_month": period_month, "run_type": run_type}).mappings().first()
        if existing:
            return _safe_redirect("/accounting/assets", error=f"Kỳ này đã post run {existing['run_no']}. Nếu cần chạy lại, hãy reverse/cancel run cũ trước.")

        candidates = db.execute(text("""
            SELECT
                fa.id,
                fa.asset_code,
                fa.asset_name,
                fa.asset_type,
                fa.acquisition_cost,
                fa.residual_value,
                fa.useful_life_months,
                ac.dep_expense_account_id,
                ac.accumulated_dep_account_id,
                ISNULL(SUM(dl.amount), 0) AS accumulated_depreciation
            FROM dbo.fixed_assets fa
            JOIN dbo.asset_classes ac ON ac.id = fa.asset_class_id
            LEFT JOIN dbo.asset_depreciation_run_lines dl ON dl.asset_id = fa.id
            LEFT JOIN dbo.asset_depreciation_runs dr ON dr.id = dl.run_id AND dr.status = N'POSTED'
            WHERE fa.is_active = 1
              AND fa.is_depreciable = 1
              AND fa.asset_status = N'ACTIVE'
              AND (fa.depreciation_start_date IS NULL OR fa.depreciation_start_date <= EOMONTH(DATEFROMPARTS(:period_year, :period_month, 1)))
            GROUP BY fa.id, fa.asset_code, fa.asset_name, fa.asset_type, fa.acquisition_cost, fa.residual_value,
                     fa.useful_life_months, ac.dep_expense_account_id, ac.accumulated_dep_account_id
            ORDER BY fa.asset_code
        """), {"period_year": period_year, "period_month": period_month}).mappings().all()

        line_items = []
        total_amount = Decimal("0")
        for a in candidates:
            if not a["dep_expense_account_id"] or not a["accumulated_dep_account_id"]:
                continue
            useful_life = int(a["useful_life_months"] or 0)
            if useful_life <= 0:
                continue
            cost = Decimal(str(a["acquisition_cost"] or 0))
            residual = Decimal(str(a["residual_value"] or 0))
            accumulated = Decimal(str(a["accumulated_depreciation"] or 0))
            depreciable_base = max(Decimal("0"), cost - residual)
            remaining = max(Decimal("0"), depreciable_base - accumulated)
            if remaining <= 0:
                continue
            monthly = (depreciable_base / Decimal(useful_life)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
            amount = min(monthly, remaining).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
            if amount <= 0:
                continue
            line_items.append({
                "asset_id": int(a["id"]),
                "asset_code": a["asset_code"],
                "asset_name": a["asset_name"],
                "debit_account_id": int(a["dep_expense_account_id"]),
                "credit_account_id": int(a["accumulated_dep_account_id"]),
                "amount": amount,
                "nbv_before": cost - accumulated,
                "nbv_after": cost - accumulated - amount,
            })
            total_amount += amount

        if not line_items:
            return _safe_redirect("/accounting/assets", error="Không có tài sản/CCDC đủ điều kiện để post khấu hao/phân bổ hoặc Asset Class chưa cấu hình đủ tài khoản.")

        run_no = NumberingService(db).generate("ASSET_RUN", posting_date)
        run_row = db.execute(text("""
            INSERT INTO dbo.asset_depreciation_runs(run_no, period_year, period_month, run_type, posting_date, memo, total_amount, status, created_by)
            OUTPUT INSERTED.id
            VALUES(:run_no, :period_year, :period_month, :run_type, :posting_date, :memo, :total_amount, N'DRAFT', :created_by)
        """), {
            "run_no": run_no,
            "period_year": period_year,
            "period_month": period_month,
            "run_type": run_type,
            "posting_date": posting_date,
            "memo": memo,
            "total_amount": total_amount,
            "created_by": int(user["id"]),
        }).first()
        run_id = int(run_row[0])

        je_lines = []
        for item in line_items:
            db.execute(text("""
                INSERT INTO dbo.asset_depreciation_run_lines(run_id, asset_id, debit_account_id, credit_account_id, amount, nbv_before, nbv_after)
                VALUES(:run_id, :asset_id, :debit_account_id, :credit_account_id, :amount, :nbv_before, :nbv_after)
            """), {**item, "run_id": run_id})
            je_lines.append({"account_id": item["debit_account_id"], "debit": item["amount"], "credit": 0, "asset_id": item["asset_id"], "memo": f"Depreciation/allocation {item['asset_code']}"})
            je_lines.append({"account_id": item["credit_account_id"], "debit": 0, "credit": item["amount"], "asset_id": item["asset_id"], "memo": f"Accumulated depreciation/allocation {item['asset_code']}"})

        je = PostingService(db, user_id=int(user["id"])).create_journal_entry(
            je_date=posting_date,
            memo=memo,
            source_doc_type="ASSET_DEPRECIATION",
            source_doc_id=run_id,
            lines=je_lines,
        )
        db.flush()
        db.execute(text("UPDATE dbo.asset_depreciation_runs SET journal_entry_id = :je_id, status = N'POSTED' WHERE id = :run_id"), {"je_id": je.id, "run_id": run_id})
        db.commit()
        return _safe_redirect("/accounting/assets", success=f"Đã post {run_no} với tổng giá trị {total_amount:,.0f}.")
    except (ValueError, SQLAlchemyError) as exc:
        db.rollback()
        return _safe_redirect("/accounting/assets", error=str(exc)[:300])
    except Exception as exc:
        db.rollback()
        return _safe_redirect("/accounting/assets", error=f"Không thể post khấu hao/phân bổ: {str(exc)[:300]}")
