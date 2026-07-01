# V99 - Item Sales Price blank hotfix

- Fix Item Master save when Sales Price is blank on existing databases.
- App now checks and makes `dbo.items.sales_price` nullable before saving Item Master.
- Added robust SQL migration `database/35_item_sales_price_nullable_hotfix.sql`.
- Handles databases that have a default constraint on `sales_price`.
