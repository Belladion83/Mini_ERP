# v74 - GR Base Unit Inventory Value

## Changed

- Goods Receipt now converts receipt quantity to the item Base Unit before posting inventory.
- Inventory value is calculated using Base Quantity × Unit Cost, following the requested rule.
- PR/PO Expected Price and Unit Price remain editable prices per Order Unit.
- Manual GR and PO-based GR use the same valuation rule.
- Vendor price history still records the Order Unit price.

## No migration

No database schema migration is required.
