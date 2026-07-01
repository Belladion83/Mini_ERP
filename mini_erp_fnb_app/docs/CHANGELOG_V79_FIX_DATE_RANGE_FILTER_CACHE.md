# v79 - Fix Date Range Table Filter Loading

- Bumped static asset cache version to v79 in base.html so browser loads the latest CSS/JS.
- Removed legacy inline column filter rows from enhanced tables.
- Date filters are now expected to be used through Filter Conditions modal with date range calendar.
- No SQL migration required.
