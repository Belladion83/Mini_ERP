Mini_ERP v75 - Corrected GR Base Unit Quantity / Inventory Value Rule
=====================================================================

No SQL migration is required for this correction.

Correct Goods Receipt valuation rule:
- PR/PO Expected Price / Unit Price remains price per Order Unit.
- GR converts receipt quantity to Base Unit for stock quantity display/posting.
- GR does NOT multiply total inventory value by the conversion rate.
- Inventory total value remains the commercial line amount:

    Base Qty = Receipt Qty in Order Unit x Order-to-Base Rate
    Base Unit Cost = Order Unit Price / Order-to-Base Rate
    Inventory Value = Base Qty x Base Unit Cost
                    = Receipt Qty in Order Unit x Order Unit Price

Example:
- Base Unit = gram
- Order Unit = kg
- Receipt Qty = 1 kg
- Unit Price = 150,000 VND/kg
- Rate = 1000

Result:
- Inventory Qty = 1000 gram
- Base Unit Cost = 150 VND/gram
- Inventory Value = 150,000 VND

This supersedes the earlier v74 wording that incorrectly multiplied value by the
conversion rate.
