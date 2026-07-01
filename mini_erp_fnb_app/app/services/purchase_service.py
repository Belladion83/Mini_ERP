from datetime import date
from decimal import Decimal
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.number_utils import parse_decimal
from app.services.numbering_service import NumberingService
from app.services.inventory_service import InventoryService
from app.services.posting_service import PostingService


class PurchaseService:
    def __init__(self, db: Session, user_id: int | None = None):
        self.db = db
        self.user_id = user_id
        self.numbering = NumberingService(db)
        self.inventory = InventoryService(db)
        self.posting = PostingService(db, user_id)

    def _ensure_cancel_metadata_columns(self) -> None:
        """Hotfix safety net for existing databases that did not run migration 26.

        The cancel flow writes cancelled_by/cancelled_at/cancel_reason.
        Some user databases may already have purchasing tables but miss these
        metadata columns, which causes SQL Server error 207 Invalid column name.
        Keep this idempotent and narrow: it only adds nullable metadata columns.
        """
        statements = [
            """
            IF OBJECT_ID(N'dbo.purchase_requisitions', N'U') IS NOT NULL
               AND COL_LENGTH(N'dbo.purchase_requisitions', N'cancelled_by') IS NULL
            BEGIN
                ALTER TABLE dbo.purchase_requisitions ADD cancelled_by BIGINT NULL;
            END
            """,
            """
            IF OBJECT_ID(N'dbo.purchase_requisitions', N'U') IS NOT NULL
               AND COL_LENGTH(N'dbo.purchase_requisitions', N'cancelled_at') IS NULL
            BEGIN
                ALTER TABLE dbo.purchase_requisitions ADD cancelled_at DATETIME2 NULL;
            END
            """,
            """
            IF OBJECT_ID(N'dbo.purchase_requisitions', N'U') IS NOT NULL
               AND COL_LENGTH(N'dbo.purchase_requisitions', N'cancel_reason') IS NULL
            BEGIN
                ALTER TABLE dbo.purchase_requisitions ADD cancel_reason NVARCHAR(500) NULL;
            END
            """,
            """
            IF OBJECT_ID(N'dbo.purchase_orders', N'U') IS NOT NULL
               AND COL_LENGTH(N'dbo.purchase_orders', N'cancelled_by') IS NULL
            BEGIN
                ALTER TABLE dbo.purchase_orders ADD cancelled_by BIGINT NULL;
            END
            """,
            """
            IF OBJECT_ID(N'dbo.purchase_orders', N'U') IS NOT NULL
               AND COL_LENGTH(N'dbo.purchase_orders', N'cancelled_at') IS NULL
            BEGIN
                ALTER TABLE dbo.purchase_orders ADD cancelled_at DATETIME2 NULL;
            END
            """,
            """
            IF OBJECT_ID(N'dbo.purchase_orders', N'U') IS NOT NULL
               AND COL_LENGTH(N'dbo.purchase_orders', N'cancel_reason') IS NULL
            BEGIN
                ALTER TABLE dbo.purchase_orders ADD cancel_reason NVARCHAR(500) NULL;
            END
            """,
            """
            IF OBJECT_ID(N'dbo.goods_receipts', N'U') IS NOT NULL
               AND COL_LENGTH(N'dbo.goods_receipts', N'cancelled_by') IS NULL
            BEGIN
                ALTER TABLE dbo.goods_receipts ADD cancelled_by BIGINT NULL;
            END
            """,
            """
            IF OBJECT_ID(N'dbo.goods_receipts', N'U') IS NOT NULL
               AND COL_LENGTH(N'dbo.goods_receipts', N'cancelled_at') IS NULL
            BEGIN
                ALTER TABLE dbo.goods_receipts ADD cancelled_at DATETIME2 NULL;
            END
            """,
            """
            IF OBJECT_ID(N'dbo.goods_receipts', N'U') IS NOT NULL
               AND COL_LENGTH(N'dbo.goods_receipts', N'cancel_reason') IS NULL
            BEGIN
                ALTER TABLE dbo.goods_receipts ADD cancel_reason NVARCHAR(500) NULL;
            END
            """,
        ]
        for stmt in statements:
            self.db.execute(text(stmt))
        self.db.flush()

    def _tax_amount(self, quantity: Decimal, unit_price: Decimal, tax_code_id: int | None) -> Decimal:
        if not tax_code_id:
            return Decimal("0")
        row = self.db.execute(text("SELECT rate FROM dbo.tax_codes WHERE id=:id"), {"id": tax_code_id}).mappings().first()
        rate = Decimal(str(row["rate"] if row else 0))
        return Decimal(str(quantity)) * Decimal(str(unit_price)) * rate / Decimal("100")

    def _default_account_id(self, account_code: str) -> int:
        account_id = self.db.execute(text("SELECT id FROM dbo.chart_accounts WHERE account_code=:code"), {"code": account_code}).scalar()
        if not account_id:
            raise ValueError(f"G/L account {account_code} is not configured.")
        return int(account_id)

    def _require_draft_pr(self, pr_id: int) -> None:
        status = self.db.execute(
            text("SELECT status FROM dbo.purchase_requisitions WHERE id=:id"),
            {"id": pr_id},
        ).scalar()
        if status != "DRAFT":
            raise ValueError("Only Draft purchase requisitions can be changed or released.")

    def _require_draft_po(self, po_id: int) -> None:
        status = self.db.execute(
            text("SELECT status FROM dbo.purchase_orders WHERE id=:id"),
            {"id": po_id},
        ).scalar()
        if status != "DRAFT":
            raise ValueError("Only Draft purchase orders can be changed or released.")

    def _pr_ids_for_po(self, po_id: int | None) -> set[int]:
        """Return all PR ids referenced by a PO.

        This is used to keep PR document status synchronized after PO save/cancel.
        """
        if not po_id:
            return set()
        rows = self.db.execute(text("""
            SELECT DISTINCT prl.pr_id
            FROM dbo.purchase_order_lines pol
            JOIN dbo.purchase_requisition_lines prl ON prl.id = pol.pr_line_id
            WHERE pol.po_id = :po_id AND prl.pr_id IS NOT NULL
        """), {"po_id": int(po_id)}).mappings().all()
        return {int(r["pr_id"]) for r in rows if r["pr_id"] is not None}

    def _validate_pr_line_reference(self, pr_line_id: int, current_po_id: int | None = None) -> int:
        """Validate that a PR line can be referenced by the current PO.

        Business rule from v77:
        - A PR can be used to create PO only while it is RELEASED.
        - Once any PR line is assigned to a PO, the PR status becomes PO_CREATED.
        - PO_CREATED PRs must not be selectable for creating another PO.
        - Editing the same draft PO may keep its existing PR line references.
        """
        row = self.db.execute(text("""
            SELECT prl.id, prl.pr_id, pr.status, prl.po_line_id, pol.po_id AS linked_po_id
            FROM dbo.purchase_requisition_lines prl
            JOIN dbo.purchase_requisitions pr ON pr.id = prl.pr_id
            LEFT JOIN dbo.purchase_order_lines pol ON pol.id = prl.po_line_id
            WHERE prl.id = :pr_line_id
        """), {"pr_line_id": int(pr_line_id)}).mappings().first()
        if not row:
            raise ValueError("Referenced PR line does not exist.")

        linked_po_id = int(row["linked_po_id"]) if row["linked_po_id"] is not None else None
        if current_po_id and linked_po_id == int(current_po_id):
            return int(row["pr_id"])

        if row["po_line_id"] is not None:
            raise ValueError("This PR line has already been used to create a PO.")
        if row["status"] != "RELEASED":
            raise ValueError("Only RELEASED PR lines can be used to create PO. PO_CREATED PRs cannot create another PO.")
        return int(row["pr_id"])

    def _sync_pr_po_created_status(self, pr_ids: set[int] | list[int] | tuple[int, ...]) -> None:
        """Synchronize PR status based on whether its lines are already linked to PO.

        DRAFT and CANCELLED are terminal/user-controlled for this rule. For released
        PRs, any linked PO line means the PR has moved to PO_CREATED and should no
        longer show Create PO. If all PO links are removed, such as when cancelling
        the related PO before GR, the PR is reopened to RELEASED.
        """
        for pr_id in {int(x) for x in (pr_ids or []) if x}:
            row = self.db.execute(text("""
                SELECT pr.status,
                       COUNT(l.id) AS line_count,
                       SUM(CASE WHEN l.po_line_id IS NOT NULL THEN 1 ELSE 0 END) AS linked_count
                FROM dbo.purchase_requisitions pr
                LEFT JOIN dbo.purchase_requisition_lines l ON l.pr_id = pr.id
                WHERE pr.id = :pr_id
                GROUP BY pr.status
            """), {"pr_id": pr_id}).mappings().first()
            if not row:
                continue
            status = str(row["status"] or "")
            if status in ("DRAFT", "CANCELLED"):
                continue
            linked_count = int(row["linked_count"] or 0)
            new_status = "PO_CREATED" if linked_count > 0 else ("RELEASED" if status == "PO_CREATED" else status)
            if new_status != status:
                self.db.execute(text("""
                    UPDATE dbo.purchase_requisitions
                    SET status = :status
                    WHERE id = :pr_id AND status NOT IN (N'DRAFT', N'CANCELLED')
                """), {"status": new_status, "pr_id": pr_id})

    def _goods_in_transit_account_id(self) -> int:
        # Business convention: use sub-account 1519 for goods-in-transit / GR clearing.
        # Keep fallback to old 159 and 151 only for backward compatibility with previous test data.
        for account_code in ("1519", "159", "151"):
            account_id = self.db.execute(
                text("SELECT id FROM dbo.chart_accounts WHERE account_code=:code"),
                {"code": account_code},
            ).scalar()
            if account_id:
                return int(account_id)
        raise ValueError("G/L account 1519 is not configured.")

    def _vendor_ap_account_id(self, vendor_id: int) -> int:
        ap_account_id = self.db.execute(text("SELECT ap_account_id FROM dbo.business_partners WHERE id=:id"), {"id": vendor_id}).scalar()
        return int(ap_account_id or self._default_account_id("331"))

    def _item_inventory_account_id(self, item_id: int) -> int:
        account_id = self.db.execute(text("SELECT inventory_account_id FROM dbo.items WHERE id=:id"), {"id": item_id}).scalar()
        if not account_id:
            raise ValueError("Inventory account is not maintained for this item.")
        return int(account_id)

    def _item_base_uom(self, item_id: int) -> str:
        return str(self.db.execute(text("SELECT base_uom FROM dbo.items WHERE id=:id"), {"id": item_id}).scalar() or "")

    def _standard_conversion_rate(self, order_uom: str | None, base_uom: str | None) -> Decimal | None:
        """Return standard conversion where 1 order_uom = rate base_uom.

        Item-specific conversion remains the first priority. This standard fallback
        reduces Item Master maintenance for universal pairs such as kg/gram and
        liter/ml.
        """
        order = (order_uom or "").strip()
        base = (base_uom or "").strip()
        if not order or not base:
            return None
        if order.lower() == base.lower():
            return Decimal("1")

        try:
            has_table = bool(self.db.execute(text("SELECT CASE WHEN OBJECT_ID(N'dbo.uom_standard_conversions', N'U') IS NULL THEN 0 ELSE 1 END")).scalar())
            if has_table:
                row = self.db.execute(text("""
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

        # Hardcoded safety fallback in case migration 31 has not been run yet.
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

    def _conversion_rate(self, item_id: int, order_uom: str | None, base_uom: str | None = None, fallback: Decimal = Decimal("1")) -> Decimal:
        order_uom = (order_uom or base_uom or "").strip()
        base_uom = (base_uom or self._item_base_uom(item_id)).strip()
        if not order_uom or order_uom.lower() == base_uom.lower():
            return Decimal("1")
        row = self.db.execute(text("""
            SELECT TOP 1 conversion_rate_to_base
            FROM dbo.item_unit_conversions
            WHERE item_id=:item_id AND LOWER(order_uom)=LOWER(:order_uom) AND is_active=1
            ORDER BY id DESC
        """), {"item_id": item_id, "order_uom": order_uom}).mappings().first()
        if row and row["conversion_rate_to_base"] is not None:
            return Decimal(str(row["conversion_rate_to_base"] or 1))
        standard_rate = self._standard_conversion_rate(order_uom, base_uom)
        if standard_rate and standard_rate > 0:
            return standard_rate
        return Decimal(str(fallback or 1))

    def _uom_values(self, item_id: int, order_uom: str | None = None, rate: Decimal | str | None = None) -> tuple[str, str, Decimal]:
        base_uom = self._item_base_uom(item_id)
        order_uom = (order_uom or base_uom or "").strip()
        try:
            fallback_rate = Decimal(str(rate or 0))
        except Exception:
            fallback_rate = Decimal("0")
        if fallback_rate <= 0:
            fallback_rate = Decimal("1")
        # Prefer the conversion maintained on Item Master.
        # This prevents stale UI/default rate=1 from producing wrong base quantity and amount.
        rate_dec = self._conversion_rate(item_id, order_uom, base_uom, fallback_rate)
        if rate_dec <= 0:
            rate_dec = fallback_rate if fallback_rate > 0 else Decimal("1")
        return base_uom, order_uom, rate_dec

    def _receipt_inventory_values(self, order_qty: Decimal, order_unit_cost: Decimal, rate: Decimal) -> tuple[Decimal, Decimal, Decimal, Decimal]:
        """Return GR valuation values using the corrected base-unit inventory rule.

        The purchase price / expected price is entered per Order Unit and remains
        editable on PR/PO. At Goods Receipt, only the inventory quantity is converted
        to the Item Base Unit. The total inventory value must remain equal to the
        commercial line amount from the PO/GR line.

            Base Qty = Order Qty × Order-to-Base Rate
            Inventory Unit Cost per Base Unit = Order Unit Price ÷ Order-to-Base Rate
            Inventory Value = Base Qty × Inventory Unit Cost per Base Unit
                            = Order Qty × Order Unit Price

        Example: Base Unit = gram, Order Unit = kg, Qty = 1, Price = 150,000 VND/kg,
        Rate = 1000 → Base Qty = 1000 gram, Unit Cost = 150 VND/gram,
        Inventory Value = 150,000 VND.

        commercial_amount is kept as the source-of-truth transaction amount.
        """
        order_qty = Decimal(str(order_qty or 0))
        order_unit_cost = Decimal(str(order_unit_cost or 0))
        rate = Decimal(str(rate or 1))
        if rate <= 0:
            rate = Decimal("1")
        base_qty = order_qty * rate
        commercial_amount = order_qty * order_unit_cost
        inventory_unit_cost = (order_unit_cost / rate) if rate else order_unit_cost
        inventory_amount = commercial_amount
        return base_qty, inventory_unit_cost, inventory_amount, commercial_amount

    def _record_vendor_price(self, vendor_id: int, item_id: int, unit_price: Decimal, doc_date: date, source_doc_type: str, source_doc_id: int | None, currency_code: str = "VND") -> None:
        self.db.execute(text("""
            INSERT INTO dbo.vendor_price_history(vendor_id, item_id, source_doc_type, source_doc_id, doc_date, unit_price, currency_code)
            VALUES(:vendor_id, :item_id, :source_doc_type, :source_doc_id, :doc_date, :unit_price, :currency_code)
        """), {
            "vendor_id": vendor_id,
            "item_id": item_id,
            "source_doc_type": source_doc_type,
            "source_doc_id": source_doc_id,
            "doc_date": doc_date,
            "unit_price": unit_price,
            "currency_code": currency_code,
        })

    def _normalize_lines(self, lines: list[dict], price_field: str) -> list[dict]:
        normalized: list[dict] = []
        for raw in lines:
            item_id = int(raw.get("item_id") or 0)
            warehouse_id = int(raw.get("warehouse_id") or 0)
            order_quantity = parse_decimal(raw.get("quantity") or 0)
            unit_price = parse_decimal(raw.get(price_field) or 0)
            if not item_id or not warehouse_id or order_quantity <= 0:
                continue
            base_uom, order_uom, order_to_base_rate = self._uom_values(item_id, raw.get("order_uom"), raw.get("order_to_base_rate"))
            base_quantity = order_quantity * order_to_base_rate
            # Unit Price / Expected Price must remain user-entered or vendor-history-driven.
            # Do not default it from Item Master standard_cost.
            if unit_price < 0:
                unit_price = Decimal("0")
            tax_code_id = raw.get("tax_code_id")
            tax_code_id = int(tax_code_id) if tax_code_id else None
            if not tax_code_id:
                tax_code_id = self.db.execute(
                    text("SELECT input_tax_code_id FROM dbo.items WHERE id=:item_id"),
                    {"item_id": item_id},
                ).scalar()
                tax_code_id = int(tax_code_id) if tax_code_id else None
            normalized.append({
                **raw,
                "item_id": item_id,
                "warehouse_id": warehouse_id,
                "quantity": order_quantity,  # Order Unit quantity on PR/PO
                price_field: unit_price,      # Price per Order Unit
                "tax_code_id": tax_code_id,
                "base_uom": base_uom,
                "order_uom": order_uom,
                "order_to_base_rate": order_to_base_rate,
                "base_quantity": base_quantity,
            })
        if not normalized:
            raise ValueError("At least one valid line is required.")
        return normalized

    def save_pr(self, pr_id: int | None, manual_pr_no: str | None, vendor_id: int | None, lines: list[dict], pr_date: date | None = None, requested_by_name: str | None = None, notes: str | None = None) -> int:
        pr_date = pr_date or date.today()
        lines = self._normalize_lines(lines, "expected_unit_price")
        total_amount = sum(Decimal(str(x["quantity"])) * Decimal(str(x["expected_unit_price"])) for x in lines)
        if pr_id:
            self._require_draft_pr(int(pr_id))
            self.db.execute(text("""
                UPDATE dbo.purchase_requisitions
                SET pr_date=:pr_date, vendor_id=:vendor_id, requested_by_name=:requested_by_name, notes=:notes, total_amount=:total_amount
                WHERE id=:id AND status=N'DRAFT'
            """), {"id": pr_id, "pr_date": pr_date, "vendor_id": vendor_id, "requested_by_name": requested_by_name, "notes": notes, "total_amount": total_amount})
            self.db.execute(text("DELETE FROM dbo.purchase_requisition_lines WHERE pr_id=:id"), {"id": pr_id})
        else:
            pr_no = manual_pr_no.strip() if manual_pr_no else ""
            if pr_no:
                self.numbering.ensure_unique("purchase_requisitions", "pr_no", pr_no)
                self.numbering.consume_if_current_preview("PRQ", pr_date, pr_no)
            else:
                pr_no = self.numbering.generate("PRQ", pr_date)
            self.db.execute(text("""
                INSERT INTO dbo.purchase_requisitions(pr_no, pr_date, vendor_id, requested_by_name, status, notes, total_amount, created_by)
                VALUES(:pr_no, :pr_date, :vendor_id, :requested_by_name, N'DRAFT', :notes, :total_amount, :created_by)
            """), {"pr_no": pr_no, "pr_date": pr_date, "vendor_id": vendor_id, "requested_by_name": requested_by_name, "notes": notes, "total_amount": total_amount, "created_by": self.user_id})
            pr_id = self.db.execute(text("SELECT id FROM dbo.purchase_requisitions WHERE pr_no=:pr_no"), {"pr_no": pr_no}).scalar_one()
        for idx, line in enumerate(lines, start=1):
            line_amount = Decimal(str(line["quantity"])) * Decimal(str(line["expected_unit_price"]))
            self.db.execute(text("""
                INSERT INTO dbo.purchase_requisition_lines(
                    pr_id, line_no, item_id, warehouse_id, quantity, base_quantity, base_uom, order_uom, order_to_base_rate,
                    suggested_vendor_id, expected_unit_price, tax_code_id, required_date, line_amount
                )
                VALUES(
                    :pr_id, :line_no, :item_id, :warehouse_id, :quantity, :base_quantity, :base_uom, :order_uom, :order_to_base_rate,
                    :vendor_id, :expected_unit_price, :tax_code_id, :required_date, :line_amount
                )
            """), {"pr_id": pr_id, "line_no": idx, "item_id": line["item_id"], "warehouse_id": line["warehouse_id"], "quantity": line["quantity"], "base_quantity": line["base_quantity"], "base_uom": line["base_uom"], "order_uom": line["order_uom"], "order_to_base_rate": line["order_to_base_rate"], "vendor_id": vendor_id, "expected_unit_price": line["expected_unit_price"], "tax_code_id": line.get("tax_code_id"), "required_date": line.get("required_date"), "line_amount": line_amount})
        self.db.commit()
        return int(pr_id)

    def release_pr(self, pr_id: int) -> None:
        self._require_draft_pr(int(pr_id))
        self.db.execute(text("""
            UPDATE dbo.purchase_requisitions SET status=N'RELEASED', released_by=:user_id, released_at=SYSUTCDATETIME()
            WHERE id=:id AND status=N'DRAFT'
        """), {"id": pr_id, "user_id": self.user_id})
        self.db.commit()

    def save_po(self, po_id: int | None, manual_po_no: str | None, vendor_id: int, lines: list[dict], po_date: date | None = None, notes: str | None = None, currency_code: str = "VND", reference_pr_id: int | None = None) -> int:
        po_date = po_date or date.today()
        current_po_id = int(po_id) if po_id else None
        affected_pr_ids: set[int] = self._pr_ids_for_po(current_po_id) if current_po_id else set()

        # Validate PR references before mutating any existing draft PO lines.
        for raw in lines:
            pr_line_id = int(raw.get("pr_line_id") or 0)
            if pr_line_id:
                affected_pr_ids.add(self._validate_pr_line_reference(pr_line_id, current_po_id))

        # If a PO line references a PR line, fill missing/zero price directly from PR.
        # This is a backend safety net for cases where the UI failed to copy PR price.
        enriched_lines = []
        for raw in lines:
            pr_line_id = int(raw.get("pr_line_id") or 0)
            unit_price = parse_decimal(raw.get("unit_price") or 0)
            if pr_line_id and unit_price <= 0:
                pr_line = self.db.execute(text("""
                    SELECT expected_unit_price, item_id, warehouse_id, quantity, order_uom, order_to_base_rate, tax_code_id
                    FROM dbo.purchase_requisition_lines
                    WHERE id=:id
                """), {"id": pr_line_id}).mappings().first()
                if pr_line:
                    raw = {**raw}
                    raw["unit_price"] = Decimal(str(pr_line["expected_unit_price"] or 0))
                    raw["item_id"] = raw.get("item_id") or pr_line["item_id"]
                    raw["warehouse_id"] = raw.get("warehouse_id") or pr_line["warehouse_id"]
                    raw["quantity"] = raw.get("quantity") or pr_line["quantity"]
                    raw["order_uom"] = raw.get("order_uom") or pr_line["order_uom"]
                    raw["order_to_base_rate"] = raw.get("order_to_base_rate") or pr_line["order_to_base_rate"]
                    raw["tax_code_id"] = raw.get("tax_code_id") or pr_line["tax_code_id"]
            enriched_lines.append(raw)
        lines = self._normalize_lines(enriched_lines, "unit_price")
        total_amount = Decimal("0")
        total_tax = Decimal("0")
        first_pr_id = None
        for line in lines:
            amount = Decimal(str(line["quantity"])) * Decimal(str(line["unit_price"]))
            tax_amount = self._tax_amount(line["quantity"], line["unit_price"], line.get("tax_code_id"))
            total_amount += amount
            total_tax += tax_amount
            if line.get("pr_line_id") and first_pr_id is None:
                first_pr_id = self.db.execute(text("SELECT pr_id FROM dbo.purchase_requisition_lines WHERE id=:id"), {"id": int(line["pr_line_id"])}).scalar()
        if reference_pr_id and not first_pr_id:
            first_pr_id = int(reference_pr_id)
        grand_total = total_amount + total_tax
        if po_id:
            self._require_draft_po(int(po_id))
            self.db.execute(text("""
                UPDATE prl SET po_line_id = NULL
                FROM dbo.purchase_requisition_lines prl JOIN dbo.purchase_order_lines pol ON pol.pr_line_id = prl.id
                WHERE pol.po_id = :po_id
            """), {"po_id": po_id})
            self.db.execute(text("""
                UPDATE dbo.purchase_orders
                SET po_date=:po_date, vendor_id=:vendor_id, pr_id=:pr_id, notes=:notes, currency_code=:currency_code, total_amount=:amount, tax_amount=:tax_amount, grand_total=:grand_total
                WHERE id=:id AND status=N'DRAFT'
            """), {"id": po_id, "po_date": po_date, "vendor_id": vendor_id, "pr_id": first_pr_id, "notes": notes, "currency_code": currency_code, "amount": total_amount, "tax_amount": total_tax, "grand_total": grand_total})
            self.db.execute(text("DELETE FROM dbo.purchase_order_lines WHERE po_id=:id"), {"id": po_id})
        else:
            po_no = manual_po_no.strip() if manual_po_no else ""
            if po_no:
                self.numbering.ensure_unique("purchase_orders", "po_no", po_no)
                self.numbering.consume_if_current_preview("PO", po_date, po_no)
            else:
                po_no = self.numbering.generate("PO", po_date)
            self.db.execute(text("""
                INSERT INTO dbo.purchase_orders(po_no, po_date, vendor_id, pr_id, status, currency_code, total_amount, tax_amount, grand_total, notes, created_by)
                VALUES(:po_no, :po_date, :vendor_id, :pr_id, N'DRAFT', :currency_code, :amount, :tax_amount, :grand_total, :notes, :created_by)
            """), {"po_no": po_no, "po_date": po_date, "vendor_id": vendor_id, "pr_id": first_pr_id, "currency_code": currency_code, "amount": total_amount, "tax_amount": total_tax, "grand_total": grand_total, "notes": notes, "created_by": self.user_id})
            po_id = self.db.execute(text("SELECT id FROM dbo.purchase_orders WHERE po_no=:po_no"), {"po_no": po_no}).scalar_one()
        for idx, line in enumerate(lines, start=1):
            amount = Decimal(str(line["quantity"])) * Decimal(str(line["unit_price"]))
            tax_amount = self._tax_amount(line["quantity"], line["unit_price"], line.get("tax_code_id"))
            pr_line_id = int(line["pr_line_id"]) if line.get("pr_line_id") else None
            self.db.execute(text("""
                INSERT INTO dbo.purchase_order_lines(
                    po_id, line_no, pr_line_id, item_id, warehouse_id, quantity, base_quantity, base_uom, order_uom, order_to_base_rate,
                    unit_price, tax_code_id, line_amount, tax_amount
                )
                VALUES(
                    :po_id, :line_no, :pr_line_id, :item_id, :warehouse_id, :quantity, :base_quantity, :base_uom, :order_uom, :order_to_base_rate,
                    :unit_price, :tax_code_id, :amount, :tax_amount
                )
            """), {"po_id": po_id, "line_no": idx, "pr_line_id": pr_line_id, "item_id": line["item_id"], "warehouse_id": line["warehouse_id"], "quantity": line["quantity"], "base_quantity": line["base_quantity"], "base_uom": line["base_uom"], "order_uom": line["order_uom"], "order_to_base_rate": line["order_to_base_rate"], "unit_price": line["unit_price"], "tax_code_id": line.get("tax_code_id"), "amount": amount, "tax_amount": tax_amount})
            if pr_line_id:
                self.db.execute(text("UPDATE dbo.purchase_requisition_lines SET po_line_id=(SELECT TOP 1 id FROM dbo.purchase_order_lines WHERE po_id=:po_id AND line_no=:line_no) WHERE id=:pr_line_id"), {"po_id": po_id, "line_no": idx, "pr_line_id": pr_line_id})
                affected_pr_ids.add(self._validate_pr_line_reference(pr_line_id, int(po_id)))
        self._sync_pr_po_created_status(affected_pr_ids)
        self.db.commit()
        return int(po_id)

    def release_po(self, po_id: int, post_in_transit: bool = False) -> None:
        self._require_draft_po(int(po_id))
        po = self.db.execute(text("SELECT id, po_date, vendor_id, total_amount, in_transit_posted FROM dbo.purchase_orders WHERE id=:id"), {"id": po_id}).mappings().one()
        je_id = None
        in_transit_posted = bool(po["in_transit_posted"])
        if post_in_transit and not in_transit_posted and Decimal(str(po["total_amount"] or 0)) > 0:
            in_transit_account_id = self._goods_in_transit_account_id()
            ap_account_id = self._vendor_ap_account_id(int(po["vendor_id"]))
            je = self.posting.post_purchase_in_transit(po["po_date"], int(po["vendor_id"]), in_transit_account_id, ap_account_id, Decimal(str(po["total_amount"])), po_id)
            je_id = je.id
            in_transit_posted = True
        self.db.execute(text("""
            UPDATE dbo.purchase_orders SET status=N'RELEASED', released_by=:user_id, released_at=SYSUTCDATETIME(), in_transit_posted=:in_transit_posted, in_transit_journal_entry_id=COALESCE(:je_id, in_transit_journal_entry_id)
            WHERE id=:id AND status=N'DRAFT'
        """), {"id": po_id, "user_id": self.user_id, "in_transit_posted": 1 if in_transit_posted else 0, "je_id": je_id})
        lines = self.db.execute(text("SELECT item_id, unit_price FROM dbo.purchase_order_lines WHERE po_id=:id"), {"id": po_id}).mappings().all()
        for line in lines:
            self._record_vendor_price(int(po["vendor_id"]), int(line["item_id"]), Decimal(str(line["unit_price"])), po["po_date"], "PURCHASE_ORDER", po_id)
        self.db.commit()

    def create_quick_purchase_receipt(self, vendor_id: int, item_id: int, warehouse_id: int, quantity: Decimal, unit_cost: Decimal, tax_rate: Decimal = Decimal("10"), doc_date: date | None = None, manual_gr_no: str | None = None) -> str:
        return self.post_manual_receipt(vendor_id, item_id, warehouse_id, quantity, unit_cost, doc_date, manual_gr_no)

    def post_manual_receipt(self, vendor_id: int, item_id: int, warehouse_id: int, quantity: Decimal, unit_cost: Decimal, doc_date: date | None = None, manual_gr_no: str | None = None, notes: str | None = None, order_uom: str | None = None, order_to_base_rate: Decimal | str | None = None) -> str:
        doc_date = doc_date or date.today()
        gr_no = manual_gr_no or self.numbering.generate("GR", doc_date)
        if manual_gr_no:
            self.numbering.ensure_unique("goods_receipts", "gr_no", manual_gr_no)
            self.numbering.consume_if_current_preview("GR", doc_date, manual_gr_no)
        base_uom, order_uom, rate = self._uom_values(item_id, order_uom, order_to_base_rate)
        order_qty = Decimal(str(quantity))
        order_unit_cost = Decimal(str(unit_cost))
        base_qty, base_unit_cost, amount, commercial_amount = self._receipt_inventory_values(order_qty, order_unit_cost, rate)
        quantity = base_qty
        unit_cost = base_unit_cost
        self.db.execute(text("""
            INSERT INTO dbo.goods_receipts(gr_no, gr_date, vendor_id, status, created_by, notes)
            VALUES(:gr_no, :gr_date, :vendor_id, N'POSTED', :created_by, :notes)
        """), {"gr_no": gr_no, "gr_date": doc_date, "vendor_id": vendor_id, "created_by": self.user_id, "notes": notes})
        gr_id = self.db.execute(text("SELECT id FROM dbo.goods_receipts WHERE gr_no=:gr_no"), {"gr_no": gr_no}).scalar_one()
        self.db.execute(text("""
            INSERT INTO dbo.goods_receipt_lines(gr_id, item_id, warehouse_id, quantity, unit_cost, line_amount, base_uom, order_uom, order_qty, order_to_base_rate, order_unit_cost)
            VALUES(:gr_id, :item_id, :warehouse_id, :quantity, :unit_cost, :line_amount, :base_uom, :order_uom, :order_qty, :order_to_base_rate, :order_unit_cost)
        """), {"gr_id": gr_id, "item_id": item_id, "warehouse_id": warehouse_id, "quantity": quantity, "unit_cost": unit_cost, "line_amount": amount, "base_uom": base_uom, "order_uom": order_uom, "order_qty": order_qty, "order_to_base_rate": rate, "order_unit_cost": order_unit_cost})
        self.inventory.post_movement(doc_date, "PURCHASE_RECEIPT", item_id, warehouse_id, qty_in=quantity, unit_cost=unit_cost, source_doc_type="GOODS_RECEIPT", source_doc_id=gr_id, notes=f"Goods receipt {gr_no}")
        inventory_account_id = self._item_inventory_account_id(item_id)
        ap_account_id = self._vendor_ap_account_id(vendor_id)
        if amount > 0:
            je = self.posting.post_goods_receipt_inventory(doc_date, vendor_id, inventory_account_id, ap_account_id, item_id, amount, gr_id, "Vendor payable from manual GR")
            self.db.execute(text("UPDATE dbo.goods_receipts SET journal_entry_id=:je_id WHERE id=:id"), {"je_id": je.id, "id": gr_id})
        self._record_vendor_price(vendor_id, item_id, order_unit_cost, doc_date, "GOODS_RECEIPT", gr_id)
        self.db.commit()
        return gr_no

    def post_manual_receipt_lines(self, vendor_id: int, lines: list[dict], doc_date: date | None = None, manual_gr_no: str | None = None, notes: str | None = None) -> str:
        doc_date = doc_date or date.today()
        valid_lines = []
        for raw in lines:
            item_id = int(raw.get("item_id") or 0)
            warehouse_id = int(raw.get("warehouse_id") or 0)
            order_qty = parse_decimal(raw.get("quantity") or 0)
            order_unit_cost = parse_decimal(raw.get("unit_cost") or 0)
            if not item_id or not warehouse_id or order_qty <= 0:
                continue
            base_uom, order_uom, rate = self._uom_values(item_id, raw.get("order_uom"), raw.get("order_to_base_rate"))
            base_qty, base_unit_cost, amount, commercial_amount = self._receipt_inventory_values(order_qty, order_unit_cost, rate)
            valid_lines.append({
                "item_id": item_id,
                "warehouse_id": warehouse_id,
                "order_qty": order_qty,
                "order_unit_cost": order_unit_cost,
                "base_qty": base_qty,
                "base_unit_cost": base_unit_cost,
                "amount": amount,
                "base_uom": base_uom,
                "order_uom": order_uom,
                "rate": rate,
            })
        if not valid_lines:
            raise ValueError("At least one valid manual GR line is required.")

        gr_no = manual_gr_no or self.numbering.generate("GR", doc_date)
        if manual_gr_no:
            self.numbering.ensure_unique("goods_receipts", "gr_no", manual_gr_no)
            self.numbering.consume_if_current_preview("GR", doc_date, manual_gr_no)

        self.db.execute(text("""
            INSERT INTO dbo.goods_receipts(gr_no, gr_date, vendor_id, status, created_by, notes)
            VALUES(:gr_no, :gr_date, :vendor_id, N'POSTED', :created_by, :notes)
        """), {"gr_no": gr_no, "gr_date": doc_date, "vendor_id": vendor_id, "created_by": self.user_id, "notes": notes})
        gr_id = self.db.execute(text("SELECT id FROM dbo.goods_receipts WHERE gr_no=:gr_no"), {"gr_no": gr_no}).scalar_one()

        je_lines: list[dict] = []
        total_amount = Decimal("0")
        for line in valid_lines:
            self.db.execute(text("""
                INSERT INTO dbo.goods_receipt_lines(gr_id, item_id, warehouse_id, quantity, unit_cost, line_amount, base_uom, order_uom, order_qty, order_to_base_rate, order_unit_cost)
                VALUES(:gr_id, :item_id, :warehouse_id, :quantity, :unit_cost, :line_amount, :base_uom, :order_uom, :order_qty, :order_to_base_rate, :order_unit_cost)
            """), {
                "gr_id": gr_id,
                "item_id": line["item_id"],
                "warehouse_id": line["warehouse_id"],
                "quantity": line["base_qty"],
                "unit_cost": line["base_unit_cost"],
                "line_amount": line["amount"],
                "base_uom": line["base_uom"],
                "order_uom": line["order_uom"],
                "order_qty": line["order_qty"],
                "order_to_base_rate": line["rate"],
                "order_unit_cost": line["order_unit_cost"],
            })
            self.inventory.post_movement(doc_date, "PURCHASE_RECEIPT", line["item_id"], line["warehouse_id"], qty_in=line["base_qty"], unit_cost=line["base_unit_cost"], source_doc_type="GOODS_RECEIPT", source_doc_id=gr_id, notes=f"Manual goods receipt {gr_no}")
            je_lines.append({"account_id": self._item_inventory_account_id(line["item_id"]), "debit": line["amount"], "credit": 0, "bp_id": vendor_id, "item_id": line["item_id"], "memo": "Inventory receipt - manual GR"})
            total_amount += line["amount"]
            self._record_vendor_price(vendor_id, line["item_id"], line["order_unit_cost"], doc_date, "GOODS_RECEIPT", gr_id)

        if total_amount > 0:
            ap_account_id = self._vendor_ap_account_id(vendor_id)
            je_lines.append({"account_id": ap_account_id, "debit": 0, "credit": total_amount, "bp_id": vendor_id, "memo": "Vendor payable from manual GR"})
            je = self.posting.create_journal_entry(doc_date, "Manual goods receipt inventory posting", "GOODS_RECEIPT", gr_id, je_lines)
            self.db.execute(text("UPDATE dbo.goods_receipts SET journal_entry_id=:je_id WHERE id=:id"), {"je_id": je.id, "id": gr_id})

        self.db.commit()
        return gr_no

    def _create_gr_header(self, gr_no: str, gr_date: date, vendor_id: int, po_id: int | None, notes: str | None) -> int:
        self.db.execute(text("""
            INSERT INTO dbo.goods_receipts(gr_no, gr_date, po_id, vendor_id, status, created_by, notes)
            VALUES(:gr_no, :gr_date, :po_id, :vendor_id, N'POSTED', :created_by, :notes)
        """), {"gr_no": gr_no, "gr_date": gr_date, "po_id": po_id, "vendor_id": vendor_id, "created_by": self.user_id, "notes": notes})
        return int(self.db.execute(text("SELECT id FROM dbo.goods_receipts WHERE gr_no=:gr_no"), {"gr_no": gr_no}).scalar_one())

    def _post_receipt_for_po_lines(self, po_id: int, receipt_lines: list[dict], doc_date: date, manual_gr_no: str | None, notes: str | None) -> str:
        if not receipt_lines:
            raise ValueError("No PO line is available for receipt.")
        vendor_id = int(receipt_lines[0]["vendor_id"])
        gr_no = manual_gr_no or self.numbering.generate("GR", doc_date)
        if manual_gr_no:
            self.numbering.ensure_unique("goods_receipts", "gr_no", manual_gr_no)
            self.numbering.consume_if_current_preview("GR", doc_date, manual_gr_no)
        gr_id = self._create_gr_header(gr_no, doc_date, vendor_id, po_id, notes)
        je_lines: list[dict] = []
        total_amount = Decimal("0")
        for line in receipt_lines:
            order_qty = Decimal(str(line["receipt_qty"]))
            order_unit_cost = Decimal(str(line["unit_price"] or 0))
            base_uom = str(line.get("base_uom") or self._item_base_uom(int(line["item_id"])))
            order_uom = str(line.get("order_uom") or base_uom)
            rate = Decimal(str(line.get("order_to_base_rate") or 1))
            if rate <= 0:
                rate = Decimal("1")
            quantity, unit_cost, amount, commercial_amount = self._receipt_inventory_values(order_qty, order_unit_cost, rate)
            total_amount += amount
            self.db.execute(text("""
                INSERT INTO dbo.goods_receipt_lines(gr_id, po_line_id, item_id, warehouse_id, quantity, unit_cost, line_amount, base_uom, order_uom, order_qty, order_to_base_rate, order_unit_cost)
                VALUES(:gr_id, :po_line_id, :item_id, :warehouse_id, :quantity, :unit_cost, :line_amount, :base_uom, :order_uom, :order_qty, :order_to_base_rate, :order_unit_cost)
            """), {"gr_id": gr_id, "po_line_id": line["po_line_id"], "item_id": line["item_id"], "warehouse_id": line["warehouse_id"], "quantity": quantity, "unit_cost": unit_cost, "line_amount": amount, "base_uom": base_uom, "order_uom": order_uom, "order_qty": order_qty, "order_to_base_rate": rate, "order_unit_cost": order_unit_cost})
            self.inventory.post_movement(doc_date, "PURCHASE_RECEIPT", int(line["item_id"]), int(line["warehouse_id"]), qty_in=quantity, unit_cost=unit_cost, source_doc_type="GOODS_RECEIPT", source_doc_id=gr_id, notes=f"Goods receipt {gr_no} from PO {line['po_no']}")
            je_lines.append({"account_id": self._item_inventory_account_id(int(line["item_id"])), "debit": amount, "credit": 0, "bp_id": vendor_id, "item_id": int(line["item_id"]), "memo": f"Inventory receipt - PO line {line['line_no']}"})
            self.db.execute(text("UPDATE dbo.purchase_order_lines SET received_qty = received_qty + :order_qty, base_received_qty = COALESCE(base_received_qty, 0) + :base_qty WHERE id=:id"), {"order_qty": order_qty, "base_qty": quantity, "id": line["po_line_id"]})
            self._record_vendor_price(vendor_id, int(line["item_id"]), order_unit_cost, doc_date, "GOODS_RECEIPT", gr_id)
        if total_amount > 0:
            po = self.db.execute(text("SELECT in_transit_posted FROM dbo.purchase_orders WHERE id=:po_id"), {"po_id": po_id}).mappings().one()
            if bool(po["in_transit_posted"]):
                credit_account_id = self._goods_in_transit_account_id()
                credit_memo = "Clear goods in transit"
            else:
                credit_account_id = self._vendor_ap_account_id(vendor_id)
                credit_memo = "Vendor payable from GR"
            je_lines.append({"account_id": credit_account_id, "debit": 0, "credit": total_amount, "bp_id": vendor_id, "memo": credit_memo})
            je = self.posting.create_journal_entry(doc_date, "Goods receipt inventory posting", "GOODS_RECEIPT", gr_id, je_lines)
            self.db.execute(text("UPDATE dbo.goods_receipts SET journal_entry_id=:je_id WHERE id=:id"), {"je_id": je.id, "id": gr_id})
        remaining = self.db.execute(text("SELECT SUM(quantity - received_qty) AS open_qty FROM dbo.purchase_order_lines WHERE po_id=:po_id"), {"po_id": po_id}).scalar()
        new_status = "FULLY_RECEIVED" if Decimal(str(remaining or 0)) <= 0 else "PARTIALLY_RECEIVED"
        self.db.execute(text("UPDATE dbo.purchase_orders SET status=:status WHERE id=:po_id"), {"status": new_status, "po_id": po_id})
        self.db.commit()
        return gr_no

    def post_po_receipt_lines(self, po_id: int, line_quantities: list[dict], doc_date: date | None = None, manual_gr_no: str | None = None, notes: str | None = None) -> str:
        doc_date = doc_date or date.today()
        if not line_quantities:
            raise ValueError("Please select at least one PO line to receipt.")
        requested = {int(x["po_line_id"]): Decimal(str(x.get("receipt_qty") or 0)) for x in line_quantities if int(x.get("po_line_id") or 0)}
        if not requested:
            raise ValueError("Please select at least one valid PO line to receipt.")
        if not po_id:
            first_line_id = next(iter(requested.keys()))
            po_id = int(self.db.execute(text("SELECT po_id FROM dbo.purchase_order_lines WHERE id=:id"), {"id": first_line_id}).scalar() or 0)
        id_params = {f"id{i}": line_id for i, line_id in enumerate(requested.keys())}
        id_clause = ", ".join(f":id{i}" for i in range(len(id_params)))
        rows = self.db.execute(text(f"""
            SELECT pol.id AS po_line_id, pol.line_no, pol.po_id, pol.item_id, pol.warehouse_id, pol.quantity, pol.received_qty, pol.unit_price, pol.base_uom, pol.order_uom, pol.order_to_base_rate,
                   po.po_no, po.vendor_id, po.status, po.in_transit_posted, (pol.quantity - pol.received_qty) AS open_qty
            FROM dbo.purchase_order_lines pol
            JOIN dbo.purchase_orders po ON po.id = pol.po_id
            WHERE pol.po_id=:po_id AND pol.id IN ({id_clause})
            ORDER BY pol.line_no
        """), {"po_id": po_id, **id_params}).mappings().all()
        if len(rows) != len(requested):
            raise ValueError("One or more selected PO lines do not belong to the selected PO.")
        receipt_lines = []
        for row in rows:
            if row["status"] not in ("RELEASED", "PARTIALLY_RECEIVED"):
                raise ValueError("Only released PO can be received.")
            receipt_qty = Decimal(str(requested[int(row["po_line_id"])]))
            open_qty = Decimal(str(row["open_qty"] or 0))
            if receipt_qty <= 0 or receipt_qty > open_qty:
                raise ValueError(f"Receipt quantity for PO line {row['line_no']} must be between 0 and open quantity {open_qty}.")
            d = dict(row)
            d["receipt_qty"] = receipt_qty
            receipt_lines.append(d)
        return self._post_receipt_for_po_lines(po_id, receipt_lines, doc_date, manual_gr_no, notes)

    def post_po_receipt(self, po_line_id: int, quantity: Decimal, doc_date: date | None = None, manual_gr_no: str | None = None, notes: str | None = None) -> str:
        doc_date = doc_date or date.today()
        line = self.db.execute(text("""
            SELECT pol.id AS po_line_id, pol.line_no, pol.po_id, pol.item_id, pol.warehouse_id, pol.quantity, pol.received_qty, pol.unit_price, pol.base_uom, pol.order_uom, pol.order_to_base_rate, po.po_no, po.vendor_id, po.status, po.in_transit_posted
            FROM dbo.purchase_order_lines pol JOIN dbo.purchase_orders po ON po.id = pol.po_id WHERE pol.id=:po_line_id
        """), {"po_line_id": po_line_id}).mappings().one()
        if line["status"] not in ("RELEASED", "PARTIALLY_RECEIVED"):
            raise ValueError("Only released PO can be received.")
        open_qty = Decimal(str(line["quantity"])) - Decimal(str(line["received_qty"] or 0))
        quantity = Decimal(str(quantity))
        if quantity <= 0 or quantity > open_qty:
            raise ValueError(f"Receipt quantity must be between 0 and open quantity {open_qty}.")
        receipt_line = dict(line)
        receipt_line["receipt_qty"] = quantity
        return self._post_receipt_for_po_lines(int(line["po_id"]), [receipt_line], doc_date, manual_gr_no, notes)

    def post_po_receipt_all(self, po_id: int, doc_date: date | None = None, manual_gr_no: str | None = None, notes: str | None = None) -> str:
        doc_date = doc_date or date.today()
        rows = self.db.execute(text("""
            SELECT pol.id AS po_line_id, pol.line_no, pol.po_id, pol.item_id, pol.warehouse_id, pol.quantity, pol.received_qty, pol.unit_price, pol.base_uom, pol.order_uom, pol.order_to_base_rate, po.po_no, po.vendor_id, po.status, po.in_transit_posted, (pol.quantity - pol.received_qty) AS open_qty
            FROM dbo.purchase_order_lines pol JOIN dbo.purchase_orders po ON po.id = pol.po_id
            WHERE po.id=:po_id AND po.status IN (N'RELEASED', N'PARTIALLY_RECEIVED') AND (pol.quantity - pol.received_qty) > 0
            ORDER BY pol.line_no
        """), {"po_id": po_id}).mappings().all()
        receipt_lines = []
        for row in rows:
            d = dict(row)
            d["receipt_qty"] = Decimal(str(row["open_qty"] or 0))
            receipt_lines.append(d)
        return self._post_receipt_for_po_lines(po_id, receipt_lines, doc_date, manual_gr_no, notes)


    def cancel_pr(self, pr_id: int, reason: str | None = None) -> None:
        self._ensure_cancel_metadata_columns()
        pr = self.db.execute(text("SELECT id, status FROM dbo.purchase_requisitions WHERE id=:id"), {"id": pr_id}).mappings().first()
        if not pr:
            raise ValueError("Purchase requisition not found.")
        if pr["status"] == "CANCELLED":
            raise ValueError("Purchase requisition is already cancelled.")
        linked_po = self.db.execute(text("SELECT COUNT(1) FROM dbo.purchase_requisition_lines WHERE pr_id=:id AND po_line_id IS NOT NULL"), {"id": pr_id}).scalar()
        if int(linked_po or 0) > 0:
            raise ValueError("Cannot cancel PR because one or more lines are already referenced by PO.")
        self.db.execute(text("""
            UPDATE dbo.purchase_requisitions
            SET status=N'CANCELLED', cancelled_by=:user_id, cancelled_at=SYSUTCDATETIME(), cancel_reason=:reason
            WHERE id=:id
        """), {"id": pr_id, "user_id": self.user_id, "reason": reason})
        self.db.commit()

    def cancel_po(self, po_id: int, reason: str | None = None, cancel_date: date | None = None) -> None:
        self._ensure_cancel_metadata_columns()
        cancel_date = cancel_date or date.today()
        affected_pr_ids = self._pr_ids_for_po(po_id)
        po = self.db.execute(text("""
            SELECT id, status, in_transit_journal_entry_id
            FROM dbo.purchase_orders
            WHERE id=:id
        """), {"id": po_id}).mappings().first()
        if not po:
            raise ValueError("Purchase order not found.")
        if po["status"] == "CANCELLED":
            raise ValueError("Purchase order is already cancelled.")
        gr_count = self.db.execute(text("SELECT COUNT(1) FROM dbo.goods_receipts WHERE po_id=:po_id AND status <> N'CANCELLED'"), {"po_id": po_id}).scalar()
        if int(gr_count or 0) > 0:
            raise ValueError("Cannot cancel PO because goods receipt already exists. Cancel the GR first.")
        if po.get("in_transit_journal_entry_id"):
            self.posting.reverse_journal_entry(int(po["in_transit_journal_entry_id"]), reverse_date=cancel_date, memo=f"Reverse in-transit posting for PO #{po_id}", source_doc_type="PURCHASE_ORDER_CANCEL", source_doc_id=po_id)
        self.db.execute(text("""
            UPDATE prl SET po_line_id = NULL
            FROM dbo.purchase_requisition_lines prl
            JOIN dbo.purchase_order_lines pol ON pol.pr_line_id = prl.id
            WHERE pol.po_id = :po_id
        """), {"po_id": po_id})
        self.db.execute(text("""
            UPDATE dbo.purchase_orders
            SET status=N'CANCELLED', cancelled_by=:user_id, cancelled_at=SYSUTCDATETIME(), cancel_reason=:reason
            WHERE id=:id
        """), {"id": po_id, "user_id": self.user_id, "reason": reason})
        self._sync_pr_po_created_status(affected_pr_ids)
        self.db.commit()

    def cancel_goods_receipt(self, gr_id: int, reason: str | None = None, cancel_date: date | None = None) -> None:
        self._ensure_cancel_metadata_columns()
        cancel_date = cancel_date or date.today()
        gr = self.db.execute(text("""
            SELECT id, gr_no, po_id, vendor_id, status, journal_entry_id
            FROM dbo.goods_receipts WHERE id=:id
        """), {"id": gr_id}).mappings().first()
        if not gr:
            raise ValueError("Goods receipt not found.")
        if gr["status"] == "CANCELLED":
            raise ValueError("Goods receipt is already cancelled.")
        untouched = self.db.execute(text("""
            SELECT COUNT(1)
            FROM dbo.inventory_layers
            WHERE source_doc_type = N'GOODS_RECEIPT' AND source_doc_id = :gr_id AND quantity <> remaining_qty
        """), {"gr_id": gr_id}).scalar()
        if int(untouched or 0) > 0:
            raise ValueError("Cannot cancel GR because its stock was already consumed by another transaction.")
        lines = self.db.execute(text("""
            SELECT grl.id, grl.po_line_id, grl.item_id, grl.warehouse_id, grl.quantity, grl.order_qty, grl.unit_cost, grl.line_amount
            FROM dbo.goods_receipt_lines grl
            WHERE grl.gr_id=:gr_id
            ORDER BY grl.id
        """), {"gr_id": gr_id}).mappings().all()
        for line in lines:
            movement_no = self.numbering.generate("IM", cancel_date)
            qty = Decimal(str(line["quantity"] or 0))
            unit_cost = Decimal(str(line["unit_cost"] or 0))
            amount = qty * unit_cost * Decimal("-1")
            self.db.execute(text("""
                INSERT INTO dbo.inventory_movements(movement_no, movement_date, movement_type, source_doc_type, source_doc_id, item_id, warehouse_id, qty_in, qty_out, unit_cost, amount, notes)
                VALUES(:movement_no, :movement_date, N'PURCHASE_RECEIPT_CANCEL', N'GOODS_RECEIPT_CANCEL', :source_doc_id, :item_id, :warehouse_id, 0, :qty_out, :unit_cost, :amount, :notes)
            """), {
                "movement_no": movement_no,
                "movement_date": cancel_date,
                "source_doc_id": gr_id,
                "item_id": int(line["item_id"]),
                "warehouse_id": int(line["warehouse_id"]),
                "qty_out": qty,
                "unit_cost": unit_cost,
                "amount": amount,
                "notes": f"Reversal of GR {gr['gr_no']}"
            })
            self.db.execute(text("""
                UPDATE dbo.inventory_layers
                SET remaining_qty = 0, amount = 0
                WHERE source_doc_type = N'GOODS_RECEIPT' AND source_doc_id = :gr_id AND item_id=:item_id AND warehouse_id=:warehouse_id AND remaining_qty = quantity
            """), {"gr_id": gr_id, "item_id": int(line["item_id"]), "warehouse_id": int(line["warehouse_id"])})
            if line.get("po_line_id"):
                order_qty = Decimal(str(line.get("order_qty") or qty))
                self.db.execute(text("UPDATE dbo.purchase_order_lines SET received_qty = CASE WHEN received_qty >= :order_qty THEN received_qty - :order_qty ELSE 0 END, base_received_qty = CASE WHEN COALESCE(base_received_qty,0) >= :base_qty THEN COALESCE(base_received_qty,0) - :base_qty ELSE 0 END WHERE id=:id"), {"order_qty": order_qty, "base_qty": qty, "id": int(line["po_line_id"])})
        if gr.get("journal_entry_id"):
            self.posting.reverse_journal_entry(int(gr["journal_entry_id"]), reverse_date=cancel_date, memo=f"Reverse GR {gr['gr_no']}", source_doc_type="GOODS_RECEIPT_CANCEL", source_doc_id=gr_id)
        if gr.get("po_id"):
            remaining = self.db.execute(text("SELECT SUM(quantity - received_qty) AS open_qty, SUM(received_qty) AS received_qty FROM dbo.purchase_order_lines WHERE po_id=:po_id"), {"po_id": int(gr["po_id"])}).mappings().first()
            open_qty = Decimal(str((remaining or {}).get("open_qty") or 0))
            rec_qty = Decimal(str((remaining or {}).get("received_qty") or 0))
            new_status = "RELEASED" if rec_qty <= 0 else ("FULLY_RECEIVED" if open_qty <= 0 else "PARTIALLY_RECEIVED")
            self.db.execute(text("UPDATE dbo.purchase_orders SET status=:status WHERE id=:po_id"), {"status": new_status, "po_id": int(gr["po_id"])})
        self.db.execute(text("""
            UPDATE dbo.goods_receipts
            SET status=N'CANCELLED', cancelled_by=:user_id, cancelled_at=SYSUTCDATETIME(), cancel_reason=:reason
            WHERE id=:id
        """), {"id": gr_id, "user_id": self.user_id, "reason": reason})
        self.db.commit()
