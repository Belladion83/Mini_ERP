# V77 - PR PO_CREATED Status

## Changes

- Added PR status `PO_CREATED`.
- When a PO is saved from PR lines, the related PR changes from `RELEASED` to `PO_CREATED`.
- PRs with status `PO_CREATED` no longer show the `Create PO` action on the PR detail screen.
- PR lines from `PO_CREATED` PRs are not available in the PO creation selection list.
- If a draft PO is cancelled before GR and the PR line link is cleared, the PR is reopened to `RELEASED`.
- Added migration `database/33_pr_po_created_status_migration.sql` to align existing PR data.

## Rule

`PO_CREATED` means the PR has already been referenced by a PO. It is no longer a source document for creating another PO.
