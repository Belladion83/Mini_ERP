V34 - Global Table Sort & Filter
================================
No SQL migration is required.

This update adds a global client-side table enhancement script:
- Global search box above list tables
- Clickable sortable column headers
- Column-level filters under each table header
- Clear Filter button
- Visible row counter

The enhancement is applied automatically to normal list tables inside .table-wrap.
It intentionally skips transaction line-entry tables such as PR Lines, PO Lines,
BOM Lines, and tables containing text/number inputs/select controls, to avoid
breaking data-entry behavior.
