from datetime import date
from decimal import Decimal
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.services.numbering_service import NumberingService
from app.services.inventory_service import InventoryService
from app.services.posting_service import PostingService


class SalesService:
    def __init__(self, db: Session, user_id: int | None = None):
        self.db = db
        self.user_id = user_id
        self.numbering = NumberingService(db)
        self.inventory = InventoryService(db)
        self.posting = PostingService(db, user_id)

    def check_availability(self, item_id: int, warehouse_id: int, quantity: Decimal) -> dict:
        item_id = int(item_id or 0)
        warehouse_id = int(warehouse_id or 0)
        quantity = Decimal(str(quantity or 0))
        if item_id <= 0:
            raise ValueError("Vui lòng chọn Item trước khi Check Availability.")
        if warehouse_id <= 0:
            raise ValueError("Vui lòng chọn Warehouse trước khi Check Availability.")
        if quantity <= 0:
            raise ValueError("Vui lòng nhập Quantity lớn hơn 0 trước khi Check Availability.")

        # Availability must follow the same stock source used by costing/issue.
        # Use inventory layers first because sales delivery consumes FIFO/LIFO/Weighted layers.
        layer_available = self.db.execute(text("""
            SELECT COALESCE(SUM(remaining_qty), 0) AS available_qty
            FROM dbo.inventory_layers
            WHERE item_id = :item_id
              AND warehouse_id = :warehouse_id
              AND remaining_qty > 0
        """), {"item_id": item_id, "warehouse_id": warehouse_id}).scalar()
        available = Decimal(str(layer_available or 0))

        # Fallback for old demo data that may have movements but no layers yet.
        if available <= 0:
            available = self.inventory.get_available_qty(item_id, warehouse_id)

        shortage = max(Decimal("0"), quantity - available)
        return {
            "item_id": item_id,
            "warehouse_id": warehouse_id,
            "required_qty": quantity,
            "available_qty": available,
            "shortage_qty": shortage,
            "enough": available >= quantity,
        }

    def calculate_sales_price(self, item_id: int, warehouse_id: int, quantity: Decimal, doc_date: date | None = None) -> dict:
        doc_date = doc_date or date.today()
        quantity = Decimal(str(quantity or 1))
        item = self.db.execute(text("""
            SELECT sales_price, standard_cost, ISNULL(profit_percent, 0) AS profit_percent
            FROM dbo.items
            WHERE id=:item_id
        """), {"item_id": item_id}).mappings().first()
        fallback_unit_cost = Decimal(str((item or {}).get("standard_cost") or 0))
        profit_percent = Decimal(str((item or {}).get("profit_percent") or 0))
        preview = self.inventory.preview_issue_cost(item_id, warehouse_id, quantity, doc_date, fallback_unit_cost)
        cost_unit = Decimal(str(preview["unit_cost"] or 0))
        manual_sales_price = (item or {}).get("sales_price")
        if manual_sales_price is not None:
            suggested_price = Decimal(str(manual_sales_price or 0))
            pricing_method = "MANUAL_SALES_PRICE"
        else:
            suggested_price = cost_unit * (Decimal("1") + profit_percent / Decimal("100"))
            pricing_method = "COST_PLUS_TARGET_PROFIT"
        return {
            **preview,
            "method": pricing_method,
            "profit_percent": profit_percent,
            "manual_sales_price": manual_sales_price,
            "suggested_unit_price": suggested_price,
        }

    def create_production_request(self, item_id: int, warehouse_id: int, quantity: Decimal, channel_code: str | None = None, note: str | None = None, source_so_id: int | None = None) -> int:
        quantity = Decimal(str(quantity or 0))
        if quantity <= 0:
            raise ValueError("Quantity must be greater than zero.")
        row = self.db.execute(text("""
            INSERT INTO dbo.sales_production_requests(request_date, requested_by, item_id, warehouse_id, requested_qty, channel_code, source_so_id, status, note)
            OUTPUT INSERTED.id
            VALUES(CAST(GETDATE() AS DATE), :requested_by, :item_id, :warehouse_id, :requested_qty, :channel_code, :source_so_id, N'OPEN', :note)
        """), {
            "requested_by": self.user_id,
            "item_id": item_id,
            "warehouse_id": warehouse_id,
            "requested_qty": quantity,
            "channel_code": channel_code,
            "source_so_id": source_so_id,
            "note": note,
        }).first()
        self.db.commit()
        return int(row[0])

    def create_quick_sale(
        self,
        customer_id: int,
        item_id: int,
        warehouse_id: int,
        quantity: Decimal,
        unit_price: Decimal,
        tax_rate: Decimal = Decimal("10"),
        doc_date: date | None = None,
        channel_code: str = "RETAIL",
        external_ref: str | None = None,
        manual_so_no: str | None = None,
    ) -> str:
        """MVP sales flow: Sales Order + Delivery + AR Invoice + accounting + stock issue."""
        doc_date = doc_date or date.today()
        so_no = manual_so_no or self.numbering.generate("SO", doc_date)
        if manual_so_no:
            self.numbering.ensure_unique("sales_orders", "so_no", manual_so_no)

        # Use Tax Code from Sale Channel master when available.
        # The old default_tax_rate column is kept only as a legacy fallback.
        output_tax_account_id = None
        channel = self.db.execute(text("""
            SELECT
                sc.default_tax_rate,
                tc.rate AS tax_code_rate,
                tc.vat_account_id AS tax_output_account_id
            FROM dbo.sale_channels sc
            LEFT JOIN dbo.tax_codes tc ON tc.id = sc.default_tax_code_id AND ISNULL(tc.tax_type, N'OUTPUT') = N'OUTPUT'
            WHERE sc.channel_code = :channel_code AND sc.is_active = 1
        """), {"channel_code": channel_code}).mappings().first()
        if channel:
            if channel["tax_code_rate"] is not None:
                tax_rate = Decimal(str(channel["tax_code_rate"]))
            elif channel["default_tax_rate"] is not None:
                tax_rate = Decimal(str(channel["default_tax_rate"]))
            output_tax_account_id = channel["tax_output_account_id"]


        # Enforce standard sales eligibility from Item Master.
        eligibility = self.db.execute(text("""
            SELECT i.item_type, ISNULL(i.can_be_sold, 0) AS can_be_sold,
                   CASE WHEN EXISTS (
                        SELECT 1
                        FROM dbo.item_sale_channels isc
                        JOIN dbo.sale_channels sc ON sc.id = isc.sale_channel_id
                        WHERE isc.item_id = i.id AND sc.channel_code = :channel_code AND sc.is_active = 1
                   ) THEN 1 ELSE 0 END AS channel_allowed
            FROM dbo.items i
            WHERE i.id = :item_id AND i.is_active = 1
        """), {"item_id": item_id, "channel_code": channel_code}).mappings().first()
        if not eligibility or eligibility["item_type"] != "FINISHED" or not eligibility["can_be_sold"] or not eligibility["channel_allowed"]:
            raise ValueError("Item is not allowed for standard sales on the selected sale channel. Only enabled FINISHED items can be sold here; non-finished items are reserved for purchasing/production/scrap flows.")

        availability = self.check_availability(item_id, warehouse_id, quantity)
        if not availability["enough"]:
            raise ValueError(f"Not enough stock in selected warehouse. Available={availability['available_qty']}, Required={availability['required_qty']}.")

        amount = Decimal(str(quantity)) * Decimal(str(unit_price))
        tax_amount = amount * Decimal(str(tax_rate)) / Decimal("100")
        grand_total = amount + tax_amount

        # Create SO
        self.db.execute(text("""
            INSERT INTO dbo.sales_orders(so_no, so_date, customer_id, status, channel_code, total_amount, tax_amount, grand_total, external_ref, created_by)
            VALUES(:so_no, :so_date, :customer_id, N'CONFIRMED', :channel_code, :amount, :tax_amount, :grand_total, :external_ref, :created_by)
        """), {"so_no": so_no, "so_date": doc_date, "customer_id": customer_id, "channel_code": channel_code,
              "amount": amount, "tax_amount": tax_amount, "grand_total": grand_total, "external_ref": external_ref, "created_by": self.user_id})
        so_id = self.db.execute(text("SELECT id FROM dbo.sales_orders WHERE so_no=:so_no"), {"so_no": so_no}).scalar_one()
        self.db.execute(text("""
            INSERT INTO dbo.sales_order_lines(so_id, line_no, item_id, warehouse_id, quantity, unit_price, line_amount, tax_amount)
            VALUES(:so_id, 1, :item_id, :warehouse_id, :quantity, :unit_price, :amount, :tax_amount)
        """), {"so_id": so_id, "item_id": item_id, "warehouse_id": warehouse_id, "quantity": quantity, "unit_price": unit_price, "amount": amount, "tax_amount": tax_amount})

        # Delivery and inventory issue
        delivery_no = self.numbering.generate("DL", doc_date)
        item = self.db.execute(text("SELECT standard_cost, inventory_account_id, cogs_account_id, revenue_account_id FROM dbo.items WHERE id=:item_id"), {"item_id": item_id}).mappings().one()
        fallback_unit_cost = Decimal(str(item["standard_cost"] or 0))
        self.db.execute(text("""
            INSERT INTO dbo.deliveries(delivery_no, delivery_date, so_id, customer_id, status)
            VALUES(:delivery_no, :delivery_date, :so_id, :customer_id, N'POSTED')
        """), {"delivery_no": delivery_no, "delivery_date": doc_date, "so_id": so_id, "customer_id": customer_id})
        delivery_id = self.db.execute(text("SELECT id FROM dbo.deliveries WHERE delivery_no=:delivery_no"), {"delivery_no": delivery_no}).scalar_one()
        movement = self.inventory.post_movement(doc_date, "SALE_ISSUE", item_id, warehouse_id, qty_out=quantity, unit_cost=fallback_unit_cost, source_doc_type="DELIVERY", source_doc_id=delivery_id, notes=f"Delivery {delivery_no}")
        unit_cost = Decimal(str(movement.unit_cost or 0))
        cogs_amount = abs(Decimal(str(movement.amount or 0)))
        delivery_line_row = self.db.execute(text("""
            INSERT INTO dbo.delivery_lines(delivery_id, item_id, warehouse_id, quantity, unit_cost)
            OUTPUT INSERTED.id
            VALUES(:delivery_id, :item_id, :warehouse_id, :quantity, :unit_cost)
        """), {"delivery_id": delivery_id, "item_id": item_id, "warehouse_id": warehouse_id, "quantity": quantity, "unit_cost": unit_cost}).first()
        delivery_line_id = int(delivery_line_row[0]) if delivery_line_row else None
        if delivery_line_id:
            self.db.execute(text("""
                INSERT INTO dbo.sales_delivery_layer_allocations(
                    so_id, delivery_id, delivery_line_id, issue_movement_id, layer_id,
                    source_doc_type, source_doc_id, production_order_id, quantity, unit_cost, amount
                )
                SELECT
                    :so_id, :delivery_id, :delivery_line_id, :movement_id, c.layer_id,
                    l.source_doc_type, l.source_doc_id, pr.production_order_id,
                    c.quantity, c.unit_cost, c.amount
                FROM dbo.inventory_layer_consumptions c
                JOIN dbo.inventory_layers l ON l.id = c.layer_id
                LEFT JOIN dbo.production_receipts pr ON pr.id = l.source_doc_id AND l.source_doc_type = N'PRODUCTION_RECEIPT'
                WHERE c.issue_movement_id = :movement_id AND c.quantity > 0
            """), {"so_id": so_id, "delivery_id": delivery_id, "delivery_line_id": delivery_line_id, "movement_id": int(movement.id)})

        if item["cogs_account_id"] and item["inventory_account_id"] and cogs_amount > 0:
            je_cogs = self.posting.post_cogs(doc_date, int(item["cogs_account_id"]), int(item["inventory_account_id"]), item_id, cogs_amount, delivery_id)
            self.db.execute(text("UPDATE dbo.deliveries SET journal_entry_id=:je_id WHERE id=:id"), {"je_id": je_cogs.id, "id": delivery_id})

        # AR invoice and revenue
        ar_no = self.numbering.generate("AR", doc_date)
        self.db.execute(text("""
            INSERT INTO dbo.ar_invoices(ar_no, ar_date, customer_id, delivery_id, status, total_amount, tax_amount, grand_total, external_ref)
            VALUES(:ar_no, :ar_date, :customer_id, :delivery_id, N'POSTED', :amount, :tax_amount, :grand_total, :external_ref)
        """), {"ar_no": ar_no, "ar_date": doc_date, "customer_id": customer_id, "delivery_id": delivery_id, "amount": amount, "tax_amount": tax_amount, "grand_total": grand_total, "external_ref": external_ref})
        ar_id = self.db.execute(text("SELECT id FROM dbo.ar_invoices WHERE ar_no=:ar_no"), {"ar_no": ar_no}).scalar_one()
        self.db.execute(text("""
            INSERT INTO dbo.ar_invoice_lines(ar_id, item_id, quantity, unit_price, line_amount, tax_amount)
            VALUES(:ar_id, :item_id, :quantity, :unit_price, :amount, :tax_amount)
        """), {"ar_id": ar_id, "item_id": item_id, "quantity": quantity, "unit_price": unit_price, "amount": amount, "tax_amount": tax_amount})

        customer = self.db.execute(text("SELECT ar_account_id FROM dbo.business_partners WHERE id=:customer_id"), {"customer_id": customer_id}).mappings().one()
        if output_tax_account_id is None:
            output_tax_account_id = self.db.execute(text("SELECT id FROM dbo.chart_accounts WHERE account_code=N'3331'")).scalar_one()
        if customer["ar_account_id"] and item["revenue_account_id"]:
            je_rev = self.posting.post_sales_revenue(doc_date, customer_id, int(customer["ar_account_id"]), int(item["revenue_account_id"]), int(output_tax_account_id), amount, tax_amount, ar_id)
            self.db.execute(text("UPDATE dbo.ar_invoices SET journal_entry_id=:je_id WHERE id=:id"), {"je_id": je_rev.id, "id": ar_id})

        self.db.execute(text("UPDATE dbo.sales_orders SET status=N'CLOSED' WHERE id=:so_id"), {"so_id": so_id})
        self.db.commit()
        return so_no
