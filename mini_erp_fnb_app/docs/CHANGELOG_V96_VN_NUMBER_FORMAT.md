# Changelog v96 - Vietnamese Decimal and Thousand Separators

- Updated Jinja number filters so displayed amounts/quantities use ERP/Vietnamese format: thousand separator `.` and decimal separator `,`.
  - Example: `1234567.89` displays as `1.234.567,89`.
- Added global browser-side number handling for numeric inputs:
  - Users can type decimal comma such as `1,5`.
  - Values are normalized back to backend-safe dot decimal before submit/API calls.
- Updated table sorting/filter parsing to understand the same number format.
- Updated key purchasing, sales, production, and GR calculation scripts to parse/format locale-style numbers.

No SQL migration required.
