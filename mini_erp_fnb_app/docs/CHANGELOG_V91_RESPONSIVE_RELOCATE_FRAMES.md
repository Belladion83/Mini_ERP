# v91 - Responsive Relocation for Selection Screens and Forms

## What changed

- Selection screen fields now reflow automatically inside their card when the browser width changes.
- Buttons such as Execute/Clear/New will wrap inside the card instead of being pushed out of the frame.
- The same responsive grid rule is applied to transaction selection screens and master data selection screens.
- Card headers and page actions can wrap naturally on smaller screens.
- No database migration is required.

## Affected areas

- Master Data selection screens
- PR/PO query selection screens
- Generic ERP form/card layouts

## Browser note

After updating, force refresh the browser with Ctrl + Shift + R or Ctrl + F5 so the new CSS cache version is loaded.
