from datetime import date
from decimal import Decimal
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.domain.models import InventoryMovement
from app.services.numbering_service import NumberingService


class InventoryService:
    def __init__(self, db: Session):
        self.db = db
        self.numbering = NumberingService(db)

    def _get_valuation_method(self, movement_date: date | None = None) -> str:
        movement_date = movement_date or date.today()
        fiscal_year = int(movement_date.year)
        try:
            row = self.db.execute(text("""
                SELECT TOP 1 valuation_method
                FROM dbo.inventory_valuation_policies
                WHERE is_active = 1 AND fiscal_year <= :fiscal_year
                ORDER BY fiscal_year DESC, effective_from DESC, id DESC
            """), {"fiscal_year": fiscal_year}).mappings().first()
            return str((row or {}).get("valuation_method") or "FIFO").upper()
        except Exception:
            return "FIFO"

    def post_movement(
        self,
        movement_date: date,
        movement_type: str,
        item_id: int,
        warehouse_id: int,
        qty_in: Decimal = Decimal("0"),
        qty_out: Decimal = Decimal("0"),
        unit_cost: Decimal = Decimal("0"),
        source_doc_type: str | None = None,
        source_doc_id: int | None = None,
        lot_no: str | None = None,
        expiry_date: date | None = None,
        notes: str | None = None,
    ) -> InventoryMovement:
        """Post inventory movement with policy-driven valuation.

        Supported methods:
        - FIFO
        - LIFO
        - WEIGHTED_AVG (moving weighted average approximation)

        Policy is selected by fiscal year from dbo.inventory_valuation_policies.
        """
        qty_in = Decimal(str(qty_in or 0))
        qty_out = Decimal(str(qty_out or 0))
        unit_cost = Decimal(str(unit_cost or 0))
        method = self._get_valuation_method(movement_date)

        amount = qty_in * unit_cost
        if qty_out > 0:
            amount = Decimal("0")

        movement = InventoryMovement(
            movement_no=self.numbering.generate("IM", movement_date),
            movement_date=movement_date,
            movement_type=movement_type,
            source_doc_type=source_doc_type,
            source_doc_id=source_doc_id,
            item_id=item_id,
            warehouse_id=warehouse_id,
            lot_no=lot_no,
            expiry_date=expiry_date,
            qty_in=qty_in,
            qty_out=qty_out,
            unit_cost=unit_cost,
            amount=amount,
            notes=notes,
        )
        self.db.add(movement)
        self.db.flush()

        if qty_in > 0:
            self._create_fifo_layer(movement, qty_in, unit_cost)
            if method == "WEIGHTED_AVG":
                self._normalize_weighted_average_layers(item_id, warehouse_id)
        elif qty_out > 0:
            if method == "LIFO":
                total_cost = self._consume_layers(
                    movement_id=int(movement.id),
                    item_id=item_id,
                    warehouse_id=warehouse_id,
                    quantity=qty_out,
                    fallback_unit_cost=unit_cost,
                    order_direction="DESC",
                )
            elif method == "WEIGHTED_AVG":
                total_cost = self._consume_weighted_average(
                    movement_id=int(movement.id),
                    item_id=item_id,
                    warehouse_id=warehouse_id,
                    quantity=qty_out,
                    fallback_unit_cost=unit_cost,
                )
            else:
                total_cost = self._consume_layers(
                    movement_id=int(movement.id),
                    item_id=item_id,
                    warehouse_id=warehouse_id,
                    quantity=qty_out,
                    fallback_unit_cost=unit_cost,
                    order_direction="ASC",
                )
            actual_unit_cost = (total_cost / qty_out) if qty_out else Decimal("0")
            movement.unit_cost = actual_unit_cost
            movement.amount = total_cost * Decimal("-1")
            self.db.flush()

        return movement

    def _create_fifo_layer(self, movement: InventoryMovement, quantity: Decimal, unit_cost: Decimal) -> None:
        amount = quantity * unit_cost
        self.db.execute(text("""
            INSERT INTO dbo.inventory_layers(
                item_id, warehouse_id, source_movement_id, source_doc_type, source_doc_id,
                layer_date, quantity, remaining_qty, unit_cost, amount
            )
            VALUES(
                :item_id, :warehouse_id, :movement_id, :source_doc_type, :source_doc_id,
                :layer_date, :quantity, :remaining_qty, :unit_cost, :amount
            )
        """), {
            "item_id": movement.item_id,
            "warehouse_id": movement.warehouse_id,
            "movement_id": movement.id,
            "source_doc_type": movement.source_doc_type,
            "source_doc_id": movement.source_doc_id,
            "layer_date": movement.movement_date,
            "quantity": quantity,
            "remaining_qty": quantity,
            "unit_cost": unit_cost,
            "amount": amount,
        })

    def _consume_layers(self, movement_id: int, item_id: int, warehouse_id: int, quantity: Decimal, fallback_unit_cost: Decimal = Decimal("0"), order_direction: str = "ASC") -> Decimal:
        remaining = Decimal(str(quantity))
        total_cost = Decimal("0")
        order_direction = "DESC" if str(order_direction).upper() == "DESC" else "ASC"

        layers = self.db.execute(text(f"""
            SELECT id, remaining_qty, unit_cost
            FROM dbo.inventory_layers WITH (UPDLOCK, ROWLOCK)
            WHERE item_id = :item_id
              AND warehouse_id = :warehouse_id
              AND remaining_qty > 0
            ORDER BY layer_date {order_direction}, id {order_direction}
        """), {"item_id": item_id, "warehouse_id": warehouse_id}).mappings().all()

        for layer in layers:
            if remaining <= 0:
                break
            available = Decimal(str(layer["remaining_qty"] or 0))
            if available <= 0:
                continue
            take_qty = available if available <= remaining else remaining
            layer_unit_cost = Decimal(str(layer["unit_cost"] or 0))
            take_amount = take_qty * layer_unit_cost

            self.db.execute(text("""
                UPDATE dbo.inventory_layers
                SET remaining_qty = remaining_qty - :take_qty,
                    amount = (remaining_qty - :take_qty) * unit_cost
                WHERE id = :layer_id
            """), {"take_qty": take_qty, "layer_id": layer["id"]})
            self.db.execute(text("""
                INSERT INTO dbo.inventory_layer_consumptions(issue_movement_id, layer_id, quantity, unit_cost, amount)
                VALUES(:movement_id, :layer_id, :quantity, :unit_cost, :amount)
            """), {
                "movement_id": movement_id,
                "layer_id": layer["id"],
                "quantity": take_qty,
                "unit_cost": layer_unit_cost,
                "amount": take_amount,
            })
            total_cost += take_amount
            remaining -= take_qty

        if remaining > 0:
            fallback_amount = remaining * Decimal(str(fallback_unit_cost or 0))
            total_cost += fallback_amount

        return total_cost

    def _normalize_weighted_average_layers(self, item_id: int, warehouse_id: int) -> Decimal:
        row = self.db.execute(text("""
            SELECT COALESCE(SUM(remaining_qty),0) AS total_qty,
                   COALESCE(SUM(remaining_qty * unit_cost),0) AS total_amount
            FROM dbo.inventory_layers
            WHERE item_id = :item_id AND warehouse_id = :warehouse_id AND remaining_qty > 0
        """), {"item_id": item_id, "warehouse_id": warehouse_id}).mappings().first()
        total_qty = Decimal(str((row or {}).get("total_qty") or 0))
        total_amount = Decimal(str((row or {}).get("total_amount") or 0))
        avg_cost = (total_amount / total_qty) if total_qty > 0 else Decimal("0")
        self.db.execute(text("""
            UPDATE dbo.inventory_layers
            SET unit_cost = :avg_cost,
                amount = remaining_qty * :avg_cost
            WHERE item_id = :item_id AND warehouse_id = :warehouse_id AND remaining_qty > 0
        """), {"avg_cost": avg_cost, "item_id": item_id, "warehouse_id": warehouse_id})
        return avg_cost

    def _consume_weighted_average(self, movement_id: int, item_id: int, warehouse_id: int, quantity: Decimal, fallback_unit_cost: Decimal = Decimal("0")) -> Decimal:
        average_cost = self._normalize_weighted_average_layers(item_id, warehouse_id)
        if average_cost <= 0:
            average_cost = Decimal(str(fallback_unit_cost or 0))
        total_cost = self._consume_layers(
            movement_id=movement_id,
            item_id=item_id,
            warehouse_id=warehouse_id,
            quantity=quantity,
            fallback_unit_cost=average_cost,
            order_direction="ASC",
        )
        self._normalize_weighted_average_layers(item_id, warehouse_id)
        return total_cost if total_cost > 0 else Decimal(str(quantity)) * average_cost

    def get_balance(self, item_id: int, warehouse_id: int) -> Decimal:
        row = self.db.execute(text("""
            SELECT COALESCE(SUM(qty_in - qty_out), 0) AS qty
            FROM dbo.inventory_movements
            WHERE item_id = :item_id AND warehouse_id = :warehouse_id
        """), {"item_id": item_id, "warehouse_id": warehouse_id}).mappings().first()
        return Decimal(str(row["qty"] if row else 0))

    def get_fifo_value(self, item_id: int, warehouse_id: int) -> Decimal:
        row = self.db.execute(text("""
            SELECT COALESCE(SUM(remaining_qty * unit_cost), 0) AS amount
            FROM dbo.inventory_layers
            WHERE item_id=:item_id AND warehouse_id=:warehouse_id AND remaining_qty > 0
        """), {"item_id": item_id, "warehouse_id": warehouse_id}).mappings().first()
        return Decimal(str(row["amount"] if row else 0))


    def get_available_qty(self, item_id: int, warehouse_id: int) -> Decimal:
        return self.get_balance(item_id, warehouse_id)

    def preview_issue_cost(self, item_id: int, warehouse_id: int, quantity: Decimal, movement_date: date | None = None, fallback_unit_cost: Decimal = Decimal("0")) -> dict:
        """Preview cost for an outbound transaction without consuming inventory layers."""
        movement_date = movement_date or date.today()
        quantity = Decimal(str(quantity or 0))
        method = self._get_valuation_method(movement_date)
        available = self.get_available_qty(item_id, warehouse_id)
        fallback_unit_cost = Decimal(str(fallback_unit_cost or 0))
        if quantity <= 0:
            return {"method": method, "available_qty": available, "required_qty": quantity, "enough": True, "total_cost": Decimal("0"), "unit_cost": Decimal("0")}

        if method == "WEIGHTED_AVG":
            row = self.db.execute(text("""
                SELECT COALESCE(SUM(remaining_qty),0) AS total_qty,
                       COALESCE(SUM(remaining_qty * unit_cost),0) AS total_amount
                FROM dbo.inventory_layers
                WHERE item_id=:item_id AND warehouse_id=:warehouse_id AND remaining_qty > 0
            """), {"item_id": item_id, "warehouse_id": warehouse_id}).mappings().first()
            total_qty = Decimal(str((row or {}).get("total_qty") or 0))
            total_amount = Decimal(str((row or {}).get("total_amount") or 0))
            unit_cost = (total_amount / total_qty) if total_qty > 0 else fallback_unit_cost
            cost_qty = quantity if available >= quantity else max(available, Decimal("0"))
            total_cost = cost_qty * unit_cost
            if available < quantity:
                total_cost += (quantity - max(available, Decimal("0"))) * fallback_unit_cost
            return {"method": method, "available_qty": available, "required_qty": quantity, "enough": available >= quantity, "total_cost": total_cost, "unit_cost": (total_cost / quantity) if quantity else Decimal("0")}

        direction = "DESC" if method == "LIFO" else "ASC"
        rows = self.db.execute(text(f"""
            SELECT id, remaining_qty, unit_cost, source_doc_type, source_doc_id
            FROM dbo.inventory_layers
            WHERE item_id=:item_id AND warehouse_id=:warehouse_id AND remaining_qty > 0
            ORDER BY layer_date {direction}, id {direction}
        """), {"item_id": item_id, "warehouse_id": warehouse_id}).mappings().all()
        remaining = quantity
        total_cost = Decimal("0")
        layer_breakdown = []
        for row in rows:
            if remaining <= 0:
                break
            avail = Decimal(str(row["remaining_qty"] or 0))
            take = min(avail, remaining)
            unit_cost = Decimal(str(row["unit_cost"] or 0))
            amount = take * unit_cost
            total_cost += amount
            remaining -= take
            layer_breakdown.append({
                "layer_id": int(row["id"]),
                "qty": take,
                "unit_cost": unit_cost,
                "amount": amount,
                "source_doc_type": row["source_doc_type"],
                "source_doc_id": row["source_doc_id"],
            })
        if remaining > 0:
            total_cost += remaining * fallback_unit_cost
        return {"method": method, "available_qty": available, "required_qty": quantity, "enough": available >= quantity, "total_cost": total_cost, "unit_cost": (total_cost / quantity) if quantity else Decimal("0"), "layers": layer_breakdown}

    def stock_card(self, item_id: int | None = None, warehouse_id: int | None = None):
        sql = """
            SELECT m.movement_date, m.movement_no, m.movement_type,
                   i.item_code, i.item_name, w.warehouse_code,
                   m.qty_in, m.qty_out, m.unit_cost, m.amount,
                   SUM(m.qty_in - m.qty_out) OVER (PARTITION BY m.item_id, m.warehouse_id ORDER BY m.movement_date, m.id) AS running_qty
            FROM dbo.inventory_movements m
            JOIN dbo.items i ON i.id = m.item_id
            JOIN dbo.warehouses w ON w.id = m.warehouse_id
            WHERE 1=1
        """
        params = {}
        if item_id:
            sql += " AND m.item_id = :item_id"
            params["item_id"] = item_id
        if warehouse_id:
            sql += " AND m.warehouse_id = :warehouse_id"
            params["warehouse_id"] = warehouse_id
        sql += " ORDER BY m.movement_date DESC, m.id DESC"
        return self.db.execute(text(sql), params).mappings().all()
