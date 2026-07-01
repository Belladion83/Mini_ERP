v36 - Default status filter behavior

No SQL migration is required.

Changes:
- PR List / PO List still open with Status = DRAFT by default.
- Clear Filter now means All Status and does not re-apply DRAFT automatically.
- Status filter is now a selectable dropdown with All Status and every status available in the table.
- Users can switch from DRAFT to RELEASED / PARTIALLY_RECEIVED / CLOSED / other statuses directly.
