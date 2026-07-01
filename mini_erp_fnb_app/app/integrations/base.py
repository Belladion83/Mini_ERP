from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass
class ExternalSaleLine:
    external_item_code: str
    item_name: str
    quantity: Decimal
    unit_price: Decimal
    tax_rate: Decimal = Decimal("0")


@dataclass
class ExternalSale:
    external_ref: str
    sale_date: datetime
    customer_code: str | None
    channel_code: str
    lines: list[ExternalSaleLine]
    raw_payload: dict | None = None


class POSConnector(ABC):
    @abstractmethod
    def pull_sales(self, since: datetime | None = None) -> list[ExternalSale]:
        """Pull external sales/receipts from POS."""

    @abstractmethod
    def push_stock_level(self, item_code: str, qty: Decimal) -> None:
        """Push stock level to POS if provider supports it."""
