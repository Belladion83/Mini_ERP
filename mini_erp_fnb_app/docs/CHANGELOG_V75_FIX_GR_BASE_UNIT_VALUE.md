# v75 - Fix GR Base Unit Value Calculation

## Fixed

- Goods Receipt still converts stock quantity to Item Base Unit.
- Inventory value no longer multiplies by the UoM conversion rate.
- Inventory unit cost is now recalculated per Base Unit:

  - Base Qty = Receipt Qty × Order-to-Base Rate
  - Base Unit Cost = Order Unit Price ÷ Order-to-Base Rate
  - Inventory Value = Base Qty × Base Unit Cost
  - Equivalent to Receipt Qty × Order Unit Price

## Example

- Base Unit = gram
- Order Unit = kg
- Receipt Qty = 1
- Order Unit Price = 150,000 VND/kg
- Rate = 1000

Inventory posting:

- Qty In = 1000 gram
- Unit Cost = 150 VND/gram
- Amount = 150,000 VND

## No migration

No database schema migration is required.
