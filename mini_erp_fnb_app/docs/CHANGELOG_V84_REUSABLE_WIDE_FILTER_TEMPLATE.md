# V84 - Reusable Wide Table Filter Template

## Changes

- Enlarged the Table Query / Filter modal so users have more working space.
- Added a reusable `erp-table-filter-template` in `base.html` so future query/report tables reuse the same filter UI template.
- Updated `erp_tables.js` to clone the shared template when available, with a fallback modal for special pages.
- Kept searchable multi-select filters, number From/To filters, and date range calendar filters.
- Bumped static cache version to `?v=84`.

## SQL

No SQL migration is required.
