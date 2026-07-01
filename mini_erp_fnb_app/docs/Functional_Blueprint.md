# Functional Blueprint - Mini ERP F&B

## 1. Scope

This application starter kit covers the core processes for a small F&B business:

- Purchasing
- Sales
- Inventory
- Production / recipe processing
- Accounting integration
- Multi-user security and authorization
- Document numbering
- POS integration layer

## 2. End-to-end process

```text
Purchase raw materials
→ Receive stock
→ Record AP invoice / payable
→ Pay vendor
→ Issue material to production
→ Receive finished goods
→ Sell goods
→ Issue stock and record COGS
→ Record revenue and AR/customer receipt
```

## 3. Module mapping

| Module | Documents | Inventory Effect | Accounting Effect |
|---|---|---|---|
| Purchasing | PO, GR, AP Invoice, Payment | Increase raw/resale stock | Dr 152/156, Dr 1331, Cr 331 |
| Sales | SO, Delivery, AR Invoice, Receipt | Decrease finished/resale stock | Dr 632 Cr 155/156; Dr 131 Cr 511/3331 |
| Inventory | Stock In/Out/Transfer/Adjustment | Increase/decrease/move stock | Depends on source |
| Production | BOM, Production Order, Material Issue, Production Receipt | RM out, FG in | Dr 154 Cr 152; Dr 155 Cr 154 |
| Accounting | JE, GL, Trial Balance | None directly | Main ledger |

## 4. MVP implementation notes

The initial app includes quick transactions for:

- Quick Goods Receipt
- Quick Sale
- Create Production Order from BOM
- Inventory stock card
- Trial balance

Next development steps:

1. Add full document line editing screens.
2. Add approval workflow.
3. Add AP/AR aging reports.
4. Add stock count and stock adjustment screens.
5. Add production receipt posting.
6. Add CSV-to-sales import posting.
7. Add API integration sync scheduler.
