# Mini_ERP

This repo maintains my own business ERP experiments and demos.

## Mini_ERP F&B Web Demo

A static GitHub Pages-ready demo has been added at the repository root.

Expected site URL after Pages is enabled:

```text
https://belladion83.github.io/Mini_ERP/
```

Demo login details are shown directly on the login screen.

### Included modules

- Dashboard
- Master Data: Business Partner, Item Master, GL Master, Tax Code
- Purchasing: Purchase Requisition, Purchase Order, Goods Receipt
- Sales Order
- Production Request
- Reports

### Important behavior included

- Master data codes and document numbers are clickable bold links.
- Clickable records open in View mode first.
- Edit mode only unlocks allowed fields.
- Immutable values such as master codes, document numbers, status, and posted or released documents remain locked.
- PR status includes `PO_CREATED` to prevent duplicate PO creation.
- PR to PO copies unit price and tax code from PR.
- GR updates stock in base unit.
- Tables are horizontally scrollable and forms/buttons wrap responsively.
- Runtime data is stored in browser `localStorage`.

### GitHub Pages setup

The repo includes `.github/workflows/pages.yml` for GitHub Pages deployment through GitHub Actions.

If the site is not live yet, open repository Settings, go to Pages, set Source to GitHub Actions, then run the workflow manually or push to `main` again.

### Static demo limitation

This version does not include FastAPI, SQL Server, SMTP, server-side auth, or real multi-user persistence. It is designed as a free web demo/prototype for business flow review and UI testing.

Pages rebuild trigger.
