# V94 - Fix PR/PO Get Price by Order Unit

## Problem
The PR/PO Get Price button could use the latest Goods Receipt total/commercial value instead of the correct unit cost for the current line Order Unit.

Example:
- Base Unit = gram
- Last GR: 1 kg, total amount 150,000 VND
- Inventory cost = 150 VND/gram

When a new PR/PO line uses Order Unit = gram, Get Price must return 150 VND/gram.
When the line uses Order Unit = kg, Get Price must return 150,000 VND/kg.

## Fix
- Price history for `GOODS_RECEIPT` and `PURCHASE_ORDER` is now derived directly from document line tables.
- The backend converts the historical base-unit cost to the current line's Order Unit using `order_to_base_rate`.
- PR Get Price now sends each line's Order Unit/rate to the backend.
- PO manual Get Price also sends the current line's Order Unit/rate.
- The button no longer applies one item price blindly to every row regardless of UoM.

## No SQL migration
No database schema change is required.
