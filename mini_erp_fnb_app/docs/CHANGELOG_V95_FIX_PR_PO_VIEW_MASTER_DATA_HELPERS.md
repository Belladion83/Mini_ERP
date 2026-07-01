# V95 - Fix PR/PO View master data helper

- Fixed 500 error when opening PR/PO by clicking document number.
- PR/PO View routes now load vendors, items, warehouses and tax codes through shared `_master_data(db)` helper.
- Removed stale references to `_vendors`, `_items`, `_warehouses`, and `_tax_codes`.
- No SQL migration required.
