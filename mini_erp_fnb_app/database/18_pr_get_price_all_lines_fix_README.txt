V32 - PR Get Price All Lines Fix

This update fixes the Purchase Requisition Get Price button so it updates every PR line in one click.

Changes:
- Added backend endpoint: GET /purchase/pr/latest-prices
- The endpoint accepts vendor_id and comma-separated item_ids.
- The PR form now collects all PR line item IDs and updates all matching Expected Price fields.
- The Vendor Price History panel still follows the current active line only, but the Get Price action no longer depends on the mouse cursor/focused line.
- No SQL migration is required.
