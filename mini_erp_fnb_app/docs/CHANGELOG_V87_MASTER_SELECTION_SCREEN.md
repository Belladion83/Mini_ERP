# v87 - Master Data Selection Screen

## Summary
- Replaced the old compact search card in Master Data list screens with the same Selection Screen pattern used by transaction query screens.
- Master Data result rows still support clicking directly on the master data code to open the maintain/edit screen.

## Changed
- Added reusable template partial: `app/templates/partials/master_selection_screen.html`.
- Updated `master_list.html` and `bom_list.html` to use the common master selection screen.
- Added generic selection criteria for Master Data:
  - Code From
  - Code To
  - Search Text Contains
  - Status: Active only / Inactive only / All statuses
- Added backend query parameters for Master Data:
  - `code_from`
  - `code_to`
  - `active_status`
- Kept backward compatibility with the old `q` and `include_inactive` query parameters.

## Notes
- No database migration is required.
- Static cache bumped to `?v=87`.
