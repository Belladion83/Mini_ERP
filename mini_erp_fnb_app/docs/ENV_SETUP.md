# Mini ERP .env Setup

The `.env` file must be located here:

```text
C:\Mini-ERP\mini_erp_fnb_app\.env
```

For a named SQL Server instance, do not use port 1433:

```env
SQLSERVER_HOST=QU08031999\ERP_DATABASE
SQLSERVER_PORT=
SQLSERVER_DATABASE=MiniERPFNB
SQLSERVER_USER=sa
SQLSERVER_PASSWORD=your_sql_password
SQLSERVER_DRIVER=ODBC Driver 18 for SQL Server
SQLSERVER_TRUST_CERTIFICATE=yes
SQLSERVER_ENCRYPT=yes

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_gmail_app_password
SMTP_FROM=
SMTP_USE_TLS=yes
```

For Windows Authentication, leave SQLSERVER_USER and SQLSERVER_PASSWORD blank.

Run this diagnostic command:

```cmd
cd C:\Mini-ERP\mini_erp_fnb_app
.venv\Scripts\activate
python scripts\check_system_settings.py
```
