from datetime import date
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.domain.models import JournalEntry, JournalEntryLine
from app.services.numbering_service import NumberingService


class PostingService:
    def __init__(self, db: Session, user_id: int | None = None):
        self.db = db
        self.user_id = user_id
        self.numbering = NumberingService(db)

    def create_journal_entry(
        self,
        je_date: date,
        memo: str,
        source_doc_type: str | None,
        source_doc_id: int | None,
        lines: list[dict],
    ) -> JournalEntry:
        total_debit = sum(Decimal(str(x.get("debit", 0))) for x in lines)
        total_credit = sum(Decimal(str(x.get("credit", 0))) for x in lines)
        if total_debit.quantize(Decimal("0.0001")) != total_credit.quantize(Decimal("0.0001")):
            raise ValueError(f"Journal entry is not balanced. Debit={total_debit}, Credit={total_credit}")

        je = JournalEntry(
            je_no=self.numbering.generate("JE", je_date),
            je_date=je_date,
            memo=memo,
            source_doc_type=source_doc_type,
            source_doc_id=source_doc_id,
            created_by=self.user_id,
            status="POSTED",
        )
        for idx, line in enumerate(lines, start=1):
            je.lines.append(JournalEntryLine(
                line_no=idx,
                account_id=int(line["account_id"]),
                debit=Decimal(str(line.get("debit", 0))),
                credit=Decimal(str(line.get("credit", 0))),
                bp_id=line.get("bp_id"),
                item_id=line.get("item_id"),
                asset_id=line.get("asset_id"),
                memo=line.get("memo"),
            ))
        self.db.add(je)
        self.db.flush()
        return je



    def reverse_journal_entry(self, original_je_id: int, reverse_date: date | None = None, memo: str | None = None, source_doc_type: str | None = None, source_doc_id: int | None = None):
        reverse_date = reverse_date or date.today()
        header = self.db.execute(text("SELECT id, je_no, memo, status FROM dbo.journal_entries WHERE id=:id"), {"id": original_je_id}).mappings().first()
        if not header:
            raise ValueError("Original journal entry not found.")
        lines = self.db.execute(text("""
            SELECT account_id, debit, credit, bp_id, item_id, asset_id, memo
            FROM dbo.journal_entry_lines
            WHERE journal_entry_id=:id
            ORDER BY line_no
        """), {"id": original_je_id}).mappings().all()
        if not lines:
            raise ValueError("Original journal entry has no lines to reverse.")
        reverse_lines = []
        for line in lines:
            reverse_lines.append({
                "account_id": int(line["account_id"]),
                "debit": Decimal(str(line.get("credit") or 0)),
                "credit": Decimal(str(line.get("debit") or 0)),
                "bp_id": line.get("bp_id"),
                "item_id": line.get("item_id"),
                "asset_id": line.get("asset_id"),
                "memo": f"Reverse: {line.get('memo') or header.get('memo') or ''}"[:500],
            })
        je = self.create_journal_entry(
            je_date=reverse_date,
            memo=memo or f"Reversal of {header['je_no']}",
            source_doc_type=source_doc_type or "REVERSAL",
            source_doc_id=source_doc_id or original_je_id,
            lines=reverse_lines,
        )
        try:
            self.db.execute(text("UPDATE dbo.journal_entries SET reversal_of_journal_entry_id=:orig_id WHERE id=:new_id"), {"orig_id": original_je_id, "new_id": je.id})
        except Exception:
            pass
        try:
            self.db.execute(text("UPDATE dbo.journal_entries SET status=N'REVERSED', reversed_at=SYSUTCDATETIME() WHERE id=:id"), {"id": original_je_id})
        except Exception:
            try:
                self.db.execute(text("UPDATE dbo.journal_entries SET status=N'REVERSED' WHERE id=:id"), {"id": original_je_id})
            except Exception:
                pass
        return je


    def post_purchase_in_transit(self, po_date: date, vendor_id: int, in_transit_account_id: int, ap_account_id: int, amount: Decimal, source_id: int | None = None):
        return self.create_journal_entry(po_date, "Purchase goods in transit posting", "PURCHASE_ORDER", source_id, [
            {"account_id": in_transit_account_id, "debit": amount, "credit": 0, "bp_id": vendor_id, "memo": "Goods in transit"},
            {"account_id": ap_account_id, "debit": 0, "credit": amount, "bp_id": vendor_id, "memo": "Vendor payable for in-transit goods"},
        ])

    def post_goods_receipt_inventory(self, gr_date: date, vendor_id: int, inventory_account_id: int, credit_account_id: int, item_id: int, amount: Decimal, source_id: int | None = None, credit_memo: str = "Goods receipt clearing"):
        return self.create_journal_entry(gr_date, "Goods receipt inventory posting", "GOODS_RECEIPT", source_id, [
            {"account_id": inventory_account_id, "debit": amount, "credit": 0, "bp_id": vendor_id, "item_id": item_id, "memo": "Inventory receipt"},
            {"account_id": credit_account_id, "debit": 0, "credit": amount, "bp_id": vendor_id, "item_id": item_id, "memo": credit_memo},
        ])

    def post_ap_invoice(self, ap_date: date, vendor_id: int, inventory_account_id: int, input_tax_account_id: int | None, ap_account_id: int, amount: Decimal, tax_amount: Decimal, source_id: int | None = None):
        lines = [{"account_id": inventory_account_id, "debit": amount, "credit": 0, "bp_id": vendor_id, "memo": "Purchase value"}]
        if tax_amount and tax_amount > 0 and input_tax_account_id:
            lines.append({"account_id": input_tax_account_id, "debit": tax_amount, "credit": 0, "bp_id": vendor_id, "memo": "Input VAT"})
        lines.append({"account_id": ap_account_id, "debit": 0, "credit": amount + tax_amount, "bp_id": vendor_id, "memo": "Vendor payable"})
        return self.create_journal_entry(ap_date, "AP Invoice posting", "AP_INVOICE", source_id, lines)

    def post_sales_revenue(self, ar_date: date, customer_id: int, ar_account_id: int, revenue_account_id: int, output_tax_account_id: int | None, amount: Decimal, tax_amount: Decimal, source_id: int | None = None):
        lines = [{"account_id": ar_account_id, "debit": amount + tax_amount, "credit": 0, "bp_id": customer_id, "memo": "Customer receivable"},
                 {"account_id": revenue_account_id, "debit": 0, "credit": amount, "bp_id": customer_id, "memo": "Sales revenue"}]
        if tax_amount and tax_amount > 0 and output_tax_account_id:
            lines.append({"account_id": output_tax_account_id, "debit": 0, "credit": tax_amount, "bp_id": customer_id, "memo": "Output VAT"})
        return self.create_journal_entry(ar_date, "AR Invoice posting", "AR_INVOICE", source_id, lines)

    def post_cogs(self, delivery_date: date, cogs_account_id: int, inventory_account_id: int, item_id: int, amount: Decimal, source_id: int | None = None):
        return self.create_journal_entry(delivery_date, "COGS posting", "DELIVERY", source_id, [
            {"account_id": cogs_account_id, "debit": amount, "credit": 0, "item_id": item_id, "memo": "COGS"},
            {"account_id": inventory_account_id, "debit": 0, "credit": amount, "item_id": item_id, "memo": "Inventory issue"},
        ])

    def post_production_issue(self, issue_date: date, wip_account_id: int, inventory_account_id: int, item_id: int, amount: Decimal, source_id: int | None = None):
        return self.create_journal_entry(issue_date, "Material issue to production", "MATERIAL_ISSUE", source_id, [
            {"account_id": wip_account_id, "debit": amount, "credit": 0, "item_id": item_id, "memo": "WIP"},
            {"account_id": inventory_account_id, "debit": 0, "credit": amount, "item_id": item_id, "memo": "Raw material issue"},
        ])

    def post_production_receipt(self, receipt_date: date, inventory_account_id: int, wip_account_id: int, item_id: int, amount: Decimal, source_id: int | None = None):
        return self.create_journal_entry(receipt_date, "Finished goods receipt", "PRODUCTION_RECEIPT", source_id, [
            {"account_id": inventory_account_id, "debit": amount, "credit": 0, "item_id": item_id, "memo": "Finished goods"},
            {"account_id": wip_account_id, "debit": 0, "credit": amount, "item_id": item_id, "memo": "Clear WIP"},
        ])
