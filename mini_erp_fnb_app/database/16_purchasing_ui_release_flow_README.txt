Migration: Not required.

v23 changes only update FastAPI routes, Jinja templates, CSS, and purchasing UI behavior:
- PO Release button uses green success style.
- PO Header now has a Reference PR Header selector; PO lines then filter PR Line options by selected PR.
- Edit PO bottom action bar: GIT checkbox on the left, Save/Release buttons on the right.
- PR/PO list pages now use select-before-action toolbar for Create/Edit/Release.
- Separate release confirmation screens have been added for PR and PO.
- Goods Receipt accepts preselected PO/PO line query parameters and auto-fills related fields.

Do not run SQL migration for this update.
