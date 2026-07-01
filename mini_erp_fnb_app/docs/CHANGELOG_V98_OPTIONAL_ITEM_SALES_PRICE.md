# V98 - Optional Item Sales Price

- Item Master → Sales Price can now be left blank.
- Blank Sales Price is saved as NULL instead of triggering a reference/duplicate error.
- New databases define `dbo.items.sales_price` as nullable.
- Existing databases should run `database/34_item_sales_price_nullable_migration.sql`.
- Sales price calculation uses manual Sales Price when maintained; otherwise it falls back to inventory cost + Target Profit %.
