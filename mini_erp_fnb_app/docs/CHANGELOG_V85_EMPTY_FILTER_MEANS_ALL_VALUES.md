# v85 - Empty Filter Means All Values

## Changed

- Table Filter multi-select fields now treat an empty selection as **All values**.
- Leaving a filter field blank removes that field from the active filter conditions.
- The search box inside a multi-select is used only to find selectable values; it does not become a filter condition by itself.
- Blank / not assigned values are no longer shown as an automatic selectable condition, so users do not accidentally combine blank value filtering with the current filter.
- Static asset cache version bumped to `v85`.

## SQL

No SQL migration is required.
