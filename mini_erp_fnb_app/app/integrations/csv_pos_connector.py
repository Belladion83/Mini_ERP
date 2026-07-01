from datetime import datetime
from decimal import Decimal
from pathlib import Path
import pandas as pd
from app.integrations.base import POSConnector, ExternalSale, ExternalSaleLine


class CSVPOSConnector(POSConnector):
    """Generic low-cost integration option.

    Expected CSV columns:
    external_ref, sale_date, customer_code, channel_code,
    item_code, item_name, quantity, unit_price, tax_rate
    """

    def __init__(self, csv_path: str | Path):
        self.csv_path = Path(csv_path)

    def pull_sales(self, since: datetime | None = None) -> list[ExternalSale]:
        df = pd.read_csv(self.csv_path)
        df["sale_date"] = pd.to_datetime(df["sale_date"])
        if since:
            df = df[df["sale_date"] >= pd.Timestamp(since)]

        sales: list[ExternalSale] = []
        for ref, group in df.groupby("external_ref"):
            first = group.iloc[0]
            lines = [
                ExternalSaleLine(
                    external_item_code=str(row["item_code"]),
                    item_name=str(row.get("item_name", row["item_code"])),
                    quantity=Decimal(str(row["quantity"])),
                    unit_price=Decimal(str(row["unit_price"])),
                    tax_rate=Decimal(str(row.get("tax_rate", 0))),
                )
                for _, row in group.iterrows()
            ]
            sales.append(ExternalSale(
                external_ref=str(ref),
                sale_date=first["sale_date"].to_pydatetime(),
                customer_code=str(first.get("customer_code", "CASH") or "CASH"),
                channel_code=str(first.get("channel_code", "POS") or "POS"),
                lines=lines,
                raw_payload={"source": "csv", "file": str(self.csv_path)},
            ))
        return sales

    def push_stock_level(self, item_code: str, qty: Decimal) -> None:
        # CSV mode cannot push stock automatically.
        return None
