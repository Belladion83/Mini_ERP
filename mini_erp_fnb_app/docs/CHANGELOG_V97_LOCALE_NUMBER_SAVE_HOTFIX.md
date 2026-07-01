# V97 - Locale number save hotfix

- Backend now accepts Vietnamese/ERP numeric format when saving master data and transactions.
- Number parsing supports `1.234.567,89`, `150.000`, `150000,50`, and backend decimal strings.
- Item Master number fields, including Sales Price and Target Profit %, are posted safely even if the browser cache keeps locale formatted values.
- Master number fields are rendered as decimal text inputs with locale normalization on submit.
