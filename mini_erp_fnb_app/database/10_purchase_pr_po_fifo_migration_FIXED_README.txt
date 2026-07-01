This ZIP only replaces database/10_purchase_pr_po_fifo_migration.sql with a safer idempotent version.

Usage:
1. Extract at C:\Mini-ERP so it overwrites C:\Mini-ERP\mini_erp_fnb_app\database\10_purchase_pr_po_fifo_migration.sql
2. Open SSMS.
3. Run database/10_purchase_pr_po_fifo_migration.sql again.
4. Do not run 01_schema.sql.
