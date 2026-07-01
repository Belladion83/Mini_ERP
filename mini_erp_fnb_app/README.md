# Mini ERP F&B Application Starter Kit

Python FastAPI + SQL Server starter kit for a small F&B ERP.

## Features

- Multi-user login
- User group and permission-based access
- SQL Server database scripts
- Auto document numbering with optional manual document number
- Purchasing: Quick Goods Receipt
- Sales: Quick Sale
- Inventory: Stock balance and stock card
- Production: Production Order from BOM/Recipe
- Accounting: Journal Entry and Trial Balance
- Integration: CSV POS import preview and connector skeleton
- Optimized UI: sidebar layout, KPI dashboard, status badges, responsive tables

## Quick Start

```bat
cd C:\Mini-ERP\mini_erp_fnb_app
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Open SQL Server Management Studio and run:

```text
database/00_create_database.sql
database/01_schema.sql
database/02_seed_data.sql
```

Copy `.env.example` to `.env` and adjust your SQL Server settings.

### Default instance by port

```env
SQLSERVER_HOST=localhost
SQLSERVER_PORT=1433
SQLSERVER_DATABASE=MiniERPFNB
SQLSERVER_USER=sa
SQLSERVER_PASSWORD=YourStrongPassword
```

### Named instance

Use your SSMS server name and leave `SQLSERVER_PORT` blank.

```env
SQLSERVER_HOST=QU08031999\ERP_DATABASE
SQLSERVER_PORT=
SQLSERVER_DATABASE=MiniERPFNB
SQLSERVER_USER=sa
SQLSERVER_PASSWORD=YourStrongPassword
```

### Windows Authentication

Leave `SQLSERVER_USER` and `SQLSERVER_PASSWORD` blank.

```env
SQLSERVER_HOST=QU08031999\ERP_DATABASE
SQLSERVER_PORT=
SQLSERVER_DATABASE=MiniERPFNB
SQLSERVER_USER=
SQLSERVER_PASSWORD=
```

Run the app:

```bat
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000
```

Demo user:

```text
Username: admin
Password: Admin@123
```

## Recommended Next Improvements

1. Add CRUD screens for Item, Customer, Vendor, Warehouse and Number Range.
2. Add full document screens for PO, SO, AP Invoice, AR Invoice and Stock Adjustment.
3. Add user/group/permission admin UI.
4. Add import-post flow for CSV POS instead of preview only.
5. Add report filters by date range, warehouse, item and channel.

## Master Data Maintenance v2

Bản này đã bổ sung màn hình CRUD cho các master data chính:

- Item Master
- Business Partners
- Warehouses
- Chart of Accounts
- Tax Codes
- Document Numbering / Number Ranges

Quy tắc thiết kế:

- Dùng `Active/Inactive` thay cho xóa cứng để không làm hỏng chứng từ đã phát sinh.
- Người dùng cần quyền `MASTER_VIEW` để xem và `MASTER_EDIT` để tạo/sửa/vô hiệu hóa.
- Với Item/Tax/Business Partner, các tài khoản kế toán được chọn từ `Chart of Accounts` đang Active.
- Nên maintain theo thứ tự: Chart of Accounts → Tax Codes → Warehouses → Items → Business Partners → Document Numbering.


## Master Data v3 update

This version adds three Master Data maintenance features:

1. Copy existing master data
   - Open a master list, click `Copy` on an existing row.
   - The form is prefilled from the source row.
   - The code field is cleared so a new unique code can be generated or entered manually.

2. Auto-generate master codes
   - Supported for Item, Customer/Vendor/BP, Warehouse, Tax Code and Chart of Accounts.
   - On new master forms, leave the code blank and click `Save`, or click `Generate` first.
   - Existing databases should run `database/03_masterdata_numbering_migration.sql` once.

3. Search suggestions
   - Master list search boxes now call the database while typing and show suggestions based on code/name/type fields.

For an existing database, do not rerun `01_schema.sql`. Run only:

```sql
:r database/03_masterdata_numbering_migration.sql
```

or open the file in SSMS and execute it against `MiniERPFNB`.

## Master Data v4 update

This version adds:

1. **Preview-only document/master numbering**
   - Clicking **Generate** on Master Data forms only previews the current number.
   - `next_no` is consumed only when the user successfully saves the master data or document.
   - Repeated Generate clicks return the same preview and do not increase `next_no`.

2. **User & Permission Admin**
   - New menu: **User Admin**.
   - Maintain users, active/inactive status, reset password, assign user groups.
   - Maintain group permissions.

3. **Demo test users**
   - Password for all demo users: `Test@123`.
   - Users: `admin_demo`, `master_user`, `purchase_user`, `sales_user`, `inventory_user`, `production_user`, `accounting_user`, `dashboard_user`.

### Migration for existing database

Run this in SSMS after extracting the update:

```sql
database/04_masterdata_security_numbering_migration.sql
```

Do not re-run `01_schema.sql` on an existing database because it is a clean setup script.

## Update v5 - Form Alignment
- Chuẩn hóa layout form bằng `.erp-form-grid` cho Master Data, Purchasing, Sales, Production, Integration và User Admin.
- Textbox, select/option box, checkbox và button được căn cùng baseline theo từng hàng.
- Nút Generate nằm cùng hàng với ô code nhưng không làm lệch các field kế bên.
- Không cần chạy thêm migration database cho bản v5.

## Update v7 - Label & Checkbox Alignment
- Field name labels are left-aligned consistently across forms.
- Checkbox controls are no longer treated like full-height input boxes and sit close to their field labels.
- No SQL migration required.

## Update v9 - BOM Master Data + Search Toolbar Alignment

After extracting this update, run this migration once in SQL Server Management Studio if your database already exists:

```sql
database/05_bom_masterdata_migration.sql
```

New features:

- Master Data → BOM / Recipe: create, edit, copy and activate/deactivate BOM for Finished Good items.
- BOM header supports auto-generated BOM Code. Generate only previews the code; `next_no` increases only after Save succeeds.
- BOM component lines support Component Item, Qty Per and Scrap %.
- Master Data search toolbars are aligned consistently: search input, checkbox, Search and Reset buttons share the same baseline.

## Update v10 - Sale Channel + COA Structure + G/L Master Data

After extracting this update, run this migration once in SQL Server Management Studio if your database already exists:

```sql
database/06_sale_channel_gl_master_migration.sql
```

New Master Data features:

- **Sale Channels**: maintain retail/POS/online/delivery/marketplace/wholesale channels, default customer, default warehouse, default revenue/fee/discount accounts and default tax rate.
- **Chart of Accounts Structure**: this is now the reporting structure for GL reports, Balance Sheet and P&L. It maintains COA nodes, report sections, parent node, node type and sequence.
- **G/L Master Data**: this now maintains the properties of each posting account, including account group, normal balance, COA report node, posting allowed and open item management.
- **Open Item Management**: mark AR/AP accounts such as 131 and 331 as open item accounts with an open item type of Customer or Vendor.
- **Sales page**: Quick Sale now reads Sale Channel options from Master Data instead of using a static datalist.

Do not re-run `01_schema.sql` on an existing database because it is a clean setup script.

## Update v11 - Sale Channel Tax Code + VAS Revenue Deduction G/L

After extracting this update, run this migration once in SQL Server Management Studio if your database already exists:

```sql
database/07_sale_channel_tax_code_revenue_deduction_migration.sql
```

New Master Data changes:

- **Sale Channels**: `Default Tax Rate %` is replaced by **Tax Code** so each sale channel uses a consistent tax rate and output VAT account from Tax Code Master Data.
- **G/L Master Data**: adds VAS account **521 - Các khoản giảm trừ doanh thu** for sales discounts/revenue deductions.
- **Chart of Accounts Structure**: adds reporting node **PL-REV-DED - Revenue Deductions** under Revenue for P&L reporting.
- Existing `default_tax_rate` remains in the database only as a legacy fallback, but the UI and sales posting logic now use `default_tax_code_id`.

Do not re-run `01_schema.sql` on an existing database because it is a clean setup script.

## v14 - Fixed Assets / Tools

This version adds fixed asset and tool management for Master Data and Accounting:

- Master Data → Asset Classes
- Master Data → Fixed Assets / Tools
- Accounting → Fixed Assets / Tools
- Monthly depreciation/allocation run with posted journal entry

For an existing database, run:

```sql
database/08_fixed_assets_tools_migration.sql
```

Recommended setup order:

1. G/L Master Data: maintain VAS accounts such as 153, 211, 2141, 242, 627/641/642.
2. Asset Classes: define account determination and useful life.
3. Fixed Assets / Tools: create each asset/tool.
4. Accounting → Fixed Assets / Tools: post monthly depreciation/allocation.

## v15 - Business Partner Category

This version adds **Business Partner Category** to Customer/Vendor master data.

For an existing database, run:

```sql
database/09_bp_category_migration.sql
```

New Business Partner category values:

- `COMPANY` - Doanh nghiệp
- `INDIVIDUAL` - Cá nhân
- `BANK` - Ngân hàng
- `ONE_TIME` - Khách/NCC vãng lai

The category is available in:

- Master Data → Business Partners → List
- Master Data → Business Partners → Create/Edit/Copy
- Search/autocomplete for Business Partners

Do not re-run `01_schema.sql` on an existing database because it is a clean setup script.

## Update v19 - Tax Code Single VAT Account

- Tax Code Master no longer uses `BOTH`.
- Each Tax Code is now either `INPUT` or `OUTPUT`.
- Tax Code Master uses a single `VAT Account` field.
- Default VAT Account behavior:
  - `INPUT` → G/L `1331`
  - `OUTPUT` → G/L `3331`
- Sale Channel only selects Output Tax Code.
- PR / Purchasing only selects Input Tax Code.

Run this migration after extracting v19:

```sql
database/13_tax_code_single_vat_account_migration.sql
```
