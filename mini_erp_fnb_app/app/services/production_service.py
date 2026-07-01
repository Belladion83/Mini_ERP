from datetime import date
from decimal import Decimal
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.services.numbering_service import NumberingService
from app.services.inventory_service import InventoryService
from app.services.posting_service import PostingService


class ProductionService:
    def __init__(self, db: Session, user_id: int | None = None):
        self.db = db
        self.user_id = user_id
        self.numbering = NumberingService(db)
        self.inventory = InventoryService(db)
        self.posting = PostingService(db, user_id)

    def _validate_warehouse_flow(self, issue_warehouse_id: int, receipt_warehouse_id: int) -> None:
        """Validate warehouse selections without merging their business meanings.

        Issue Warehouse = component/raw material source for material issue.
        Receipt Warehouse = finished goods destination for production receipt.
        The two fields may be the same warehouse in a small operation, but they are
        intentionally kept as two independent ERP fields.
        """
        issue_warehouse_id = int(issue_warehouse_id or 0)
        receipt_warehouse_id = int(receipt_warehouse_id or 0)
        if issue_warehouse_id <= 0:
            raise ValueError("Issue Warehouse is required for component/raw material issue.")
        if receipt_warehouse_id <= 0:
            raise ValueError("Receipt Warehouse is required for finished goods receipt.")
        found = self.db.execute(text("""
            SELECT COUNT(*)
            FROM dbo.warehouses
            WHERE id IN (:issue_wh, :receipt_wh)
        """), {"issue_wh": issue_warehouse_id, "receipt_wh": receipt_warehouse_id}).scalar()
        required_count = 1 if issue_warehouse_id == receipt_warehouse_id else 2
        if int(found or 0) < required_count:
            raise ValueError("Selected Issue/Receipt Warehouse does not exist or is inactive.")


    def calculate_bom_cost(self, bom_id: int, planned_qty: Decimal, issue_warehouse_id: int, cost_date: date | None = None) -> dict:
        cost_date = cost_date or date.today()
        planned_qty = Decimal(str(planned_qty or 0))
        if planned_qty <= 0:
            raise ValueError("Planned Qty must be greater than zero.")
        if int(issue_warehouse_id or 0) <= 0:
            raise ValueError("Issue Warehouse is required to preview component cost.")
        bom = self.db.execute(text("""
            SELECT b.id, b.bom_code, b.finished_item_id, b.base_qty, i.item_code, i.item_name
            FROM dbo.boms b
            JOIN dbo.items i ON i.id = b.finished_item_id
            WHERE b.id=:bom_id
        """), {"bom_id": bom_id}).mappings().first()
        if not bom:
            raise ValueError("BOM not found.")
        base_qty = Decimal(str(bom["base_qty"] or 1)) or Decimal("1")
        components = self.db.execute(text("""
            SELECT bc.component_item_id, bc.qty_per, bc.scrap_percent, i.item_code, i.item_name, i.standard_cost
            FROM dbo.bom_components bc
            JOIN dbo.items i ON i.id = bc.component_item_id
            WHERE bc.bom_id=:bom_id
            ORDER BY bc.id
        """), {"bom_id": bom_id}).mappings().all()
        total_cost = Decimal("0")
        rows = []
        for comp in components:
            required_qty = (planned_qty / base_qty) * Decimal(str(comp["qty_per"] or 0)) * (Decimal("1") + Decimal(str(comp["scrap_percent"] or 0)) / Decimal("100"))
            preview = self.inventory.preview_issue_cost(
                int(comp["component_item_id"]),
                int(issue_warehouse_id),
                required_qty,
                cost_date,
                Decimal(str(comp["standard_cost"] or 0)),
            )
            total_cost += Decimal(str(preview["total_cost"] or 0))
            rows.append({
                "item_id": int(comp["component_item_id"]),
                "item_code": comp["item_code"],
                "item_name": comp["item_name"],
                "required_qty": required_qty,
                "available_qty": preview["available_qty"],
                "unit_cost": preview["unit_cost"],
                "total_cost": preview["total_cost"],
                "method": preview["method"],
                "enough": preview["enough"],
            })
        return {
            "bom_id": bom_id,
            "bom_code": bom["bom_code"],
            "finished_item_id": int(bom["finished_item_id"]),
            "finished_item_code": bom["item_code"],
            "finished_item_name": bom["item_name"],
            "planned_qty": planned_qty,
            "total_cost": total_cost,
            "unit_cost": (total_cost / planned_qty) if planned_qty else Decimal("0"),
            "components": rows,
        }

    def create_production_order_from_request(self, request_id: int, issue_warehouse_id: int, receipt_warehouse_id: int, prod_date: date | None = None) -> str:
        self._validate_warehouse_flow(issue_warehouse_id, receipt_warehouse_id)
        request = self.db.execute(text("""
            SELECT r.id, r.item_id, r.requested_qty, r.status, i.item_code
            FROM dbo.sales_production_requests r
            JOIN dbo.items i ON i.id = r.item_id
            WHERE r.id=:id
        """), {"id": request_id}).mappings().first()
        if not request:
            raise ValueError("Production request not found.")
        if request["status"] not in ("OPEN", "REVIEWED"):
            raise ValueError("Only OPEN/REVIEWED production requests can be converted to production order.")
        bom = self.db.execute(text("""
            SELECT TOP 1 id
            FROM dbo.boms
            WHERE finished_item_id=:item_id AND is_active = 1
            ORDER BY id DESC
        """), {"item_id": int(request["item_id"])}).scalar()
        if not bom:
            raise ValueError("No active BOM found for requested finished item.")
        prod_no = self.create_production_order_from_bom(int(request["item_id"]), int(bom), Decimal(str(request["requested_qty"])), issue_warehouse_id, receipt_warehouse_id, prod_date)
        prod_id = self.db.execute(text("SELECT id FROM dbo.production_orders WHERE prod_no=:prod_no"), {"prod_no": prod_no}).scalar()
        try:
            self.db.execute(text("UPDATE dbo.production_orders SET sales_request_id=:request_id WHERE id=:prod_id"), {"request_id": request_id, "prod_id": prod_id})
        except Exception:
            pass
        self.db.execute(text("UPDATE dbo.sales_production_requests SET status=N'CONVERTED', production_order_id=:prod_id WHERE id=:id"), {"prod_id": prod_id, "id": request_id})
        self.db.commit()
        return prod_no

    def create_production_order_from_bom(self, finished_item_id: int, bom_id: int, planned_qty: Decimal, issue_warehouse_id: int, receipt_warehouse_id: int, prod_date: date | None = None) -> str:
        prod_date = prod_date or date.today()
        planned_qty = Decimal(str(planned_qty or 0))
        if planned_qty <= 0:
            raise ValueError("Planned Qty must be greater than zero.")
        self._validate_warehouse_flow(issue_warehouse_id, receipt_warehouse_id)
        prod_no = self.numbering.generate("PROD", prod_date)
        self.db.execute(text("""
            INSERT INTO dbo.production_orders(prod_no, prod_date, finished_item_id, bom_id, planned_qty, status, issue_warehouse_id, receipt_warehouse_id, created_by)
            VALUES(:prod_no, :prod_date, :finished_item_id, :bom_id, :planned_qty, N'RELEASED', :issue_wh, :receipt_wh, :created_by)
        """), {"prod_no": prod_no, "prod_date": prod_date, "finished_item_id": finished_item_id, "bom_id": bom_id, "planned_qty": planned_qty,
              "issue_wh": issue_warehouse_id, "receipt_wh": receipt_warehouse_id, "created_by": self.user_id})
        prod_id = self.db.execute(text("SELECT id FROM dbo.production_orders WHERE prod_no=:prod_no"), {"prod_no": prod_no}).scalar_one()
        components = self.db.execute(text("""
            SELECT component_item_id, qty_per, scrap_percent
            FROM dbo.bom_components
            WHERE bom_id=:bom_id
        """), {"bom_id": bom_id}).mappings().all()
        for comp in components:
            qty = Decimal(str(planned_qty)) * Decimal(str(comp["qty_per"])) * (Decimal("1") + Decimal(str(comp["scrap_percent"] or 0))/Decimal("100"))
            self.db.execute(text("""
                INSERT INTO dbo.production_order_lines(production_order_id, component_item_id, planned_qty)
                VALUES(:prod_id, :item_id, :qty)
            """), {"prod_id": prod_id, "item_id": comp["component_item_id"], "qty": qty})
        self.db.commit()
        return prod_no

    def issue_all_planned_materials(self, production_order_id: int, issue_date: date | None = None) -> str:
        issue_date = issue_date or date.today()
        issue_no = self.numbering.generate("MI", issue_date)
        prod = self.db.execute(text("SELECT issue_warehouse_id FROM dbo.production_orders WHERE id=:id"), {"id": production_order_id}).mappings().one()
        self.db.execute(text("""
            INSERT INTO dbo.material_issues(issue_no, issue_date, production_order_id, status)
            VALUES(:issue_no, :issue_date, :production_order_id, N'POSTED')
        """), {"issue_no": issue_no, "issue_date": issue_date, "production_order_id": production_order_id})
        issue_id = self.db.execute(text("SELECT id FROM dbo.material_issues WHERE issue_no=:issue_no"), {"issue_no": issue_no}).scalar_one()
        lines = self.db.execute(text("""
            SELECT l.id, l.component_item_id, l.planned_qty, i.standard_cost, i.inventory_account_id, i.wip_account_id
            FROM dbo.production_order_lines l
            JOIN dbo.items i ON i.id = l.component_item_id
            WHERE l.production_order_id=:id
        """), {"id": production_order_id}).mappings().all()
        for line in lines:
            qty = Decimal(str(line["planned_qty"]))
            fallback_unit_cost = Decimal(str(line["standard_cost"] or 0))
            movement = self.inventory.post_movement(issue_date, "PRODUCTION_ISSUE", line["component_item_id"], prod["issue_warehouse_id"], qty_out=qty, unit_cost=fallback_unit_cost, source_doc_type="MATERIAL_ISSUE", source_doc_id=issue_id, notes=f"Material issue {issue_no}")
            unit_cost = Decimal(str(movement.unit_cost or 0))
            amount = abs(Decimal(str(movement.amount or 0)))
            self.db.execute(text("""
                INSERT INTO dbo.material_issue_lines(material_issue_id, item_id, warehouse_id, quantity, unit_cost)
                VALUES(:issue_id, :item_id, :warehouse_id, :quantity, :unit_cost)
            """), {"issue_id": issue_id, "item_id": line["component_item_id"], "warehouse_id": prod["issue_warehouse_id"], "quantity": qty, "unit_cost": unit_cost})
            if line["wip_account_id"] and line["inventory_account_id"] and amount > 0:
                je = self.posting.post_production_issue(issue_date, int(line["wip_account_id"]), int(line["inventory_account_id"]), int(line["component_item_id"]), amount, issue_id)
                self.db.execute(text("UPDATE dbo.material_issues SET journal_entry_id=:je_id WHERE id=:id"), {"je_id": je.id, "id": issue_id})
        self.db.execute(text("UPDATE dbo.production_orders SET status=N'MATERIAL_ISSUED' WHERE id=:id"), {"id": production_order_id})
        self.db.commit()
        return issue_no
