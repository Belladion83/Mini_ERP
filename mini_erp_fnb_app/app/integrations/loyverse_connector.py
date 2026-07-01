from datetime import datetime
from decimal import Decimal
import httpx
from app.integrations.base import POSConnector, ExternalSale, ExternalSaleLine


class LoyverseConnector(POSConnector):
    """Loyverse POS connector skeleton.

    You need a Loyverse developer account and API token.
    This class intentionally keeps only the safe scaffold. Adjust endpoint mapping
    according to the current Loyverse API documentation for your tenant.
    """

    def __init__(self, api_token: str, base_url: str = "https://api.loyverse.com/v1.0"):
        self.api_token = api_token
        self.base_url = base_url.rstrip("/")

    @property
    def headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_token}", "Content-Type": "application/json"}

    def pull_sales(self, since: datetime | None = None) -> list[ExternalSale]:
        params = {}
        if since:
            params["created_at_min"] = since.isoformat()
        with httpx.Client(timeout=30) as client:
            response = client.get(f"{self.base_url}/receipts", headers=self.headers, params=params)
            response.raise_for_status()
            payload = response.json()

        receipts = payload.get("receipts", payload if isinstance(payload, list) else [])
        sales: list[ExternalSale] = []
        for receipt in receipts:
            lines = []
            for line in receipt.get("line_items", []):
                lines.append(ExternalSaleLine(
                    external_item_code=str(line.get("variant_id") or line.get("item_id") or line.get("sku") or ""),
                    item_name=str(line.get("item_name") or line.get("name") or "POS Item"),
                    quantity=Decimal(str(line.get("quantity", 0))),
                    unit_price=Decimal(str(line.get("price", 0))),
                    tax_rate=Decimal("0"),
                ))
            sales.append(ExternalSale(
                external_ref=str(receipt.get("receipt_number") or receipt.get("id")),
                sale_date=datetime.fromisoformat(str(receipt.get("created_at")).replace("Z", "+00:00")),
                customer_code=None,
                channel_code="LOYVERSE",
                lines=lines,
                raw_payload=receipt,
            ))
        return sales

    def push_stock_level(self, item_code: str, qty: Decimal) -> None:
        # Implement if your Loyverse setup allows inventory update endpoint access.
        # Keep disabled by default to avoid accidental stock overwrite.
        raise NotImplementedError("Stock push is intentionally disabled in starter kit.")
