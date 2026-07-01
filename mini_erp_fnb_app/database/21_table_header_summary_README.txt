V35 - Global Table Header Summary UX

No SQL migration is required for this update.

Changes:
- PR List and PO List now show one header-level row per document instead of one row per line.
- Added summary columns:
  PR: Total Items, Open Items, PO Created Items, Total Qty, First Item, Total Amount.
  PO: Total Items, Open Items, Received Items, Total Qty, Received Qty, First Item, GIT, Grand Total.
- Table toolbar now supports left-side table title, e.g. PR List / PO List.
- Status filter defaults to DRAFT on PR/PO list tables.
- Column filters are searchable text inputs with suggestions from current database rows.
- Quantity, Price, Amount, and Total columns do not get column filters, but still support header sorting.
