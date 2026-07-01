USE MiniERPFNB;
GO

/* =========================================================
   CHART OF ACCOUNTS STRUCTURE
   ========================================================= */

INSERT INTO dbo.coa_nodes(node_code, node_name, report_section, node_type, parent_node_id, normal_balance, sequence_no) VALUES
(N'BS', N'Balance Sheet', N'BALANCE_SHEET', N'HEADER', NULL, NULL, 10),
(N'BS-ASSET', N'Assets', N'BALANCE_SHEET', N'HEADER', NULL, N'DEBIT', 20),
(N'BS-LIABILITY', N'Liabilities', N'BALANCE_SHEET', N'HEADER', NULL, N'CREDIT', 30),
(N'BS-EQUITY', N'Equity', N'BALANCE_SHEET', N'HEADER', NULL, N'CREDIT', 40),
(N'PL', N'Profit and Loss', N'P_AND_L', N'HEADER', NULL, NULL, 50),
(N'PL-REV', N'Revenue', N'P_AND_L', N'HEADER', NULL, N'CREDIT', 60),
(N'PL-REV-DED', N'Revenue Deductions', N'P_AND_L', N'POSTING_GROUP', NULL, N'DEBIT', 65),
(N'PL-COGS', N'Cost of Goods Sold', N'P_AND_L', N'HEADER', NULL, N'DEBIT', 70),
(N'PL-EXP', N'Operating Expenses', N'P_AND_L', N'HEADER', NULL, N'DEBIT', 80),
(N'PL-OTHER', N'Other Income/Expense', N'P_AND_L', N'HEADER', NULL, NULL, 90);
GO

UPDATE child
SET parent_node_id = parent.id
FROM dbo.coa_nodes child
JOIN dbo.coa_nodes parent ON parent.node_code = CASE
    WHEN child.node_code LIKE N'BS-%' THEN N'BS'
    WHEN child.node_code LIKE N'PL-%' THEN N'PL'
END
WHERE child.parent_node_id IS NULL AND child.node_code IN (N'BS-ASSET', N'BS-LIABILITY', N'BS-EQUITY', N'PL-REV', N'PL-REV-DED', N'PL-COGS', N'PL-EXP', N'PL-OTHER');
GO

/* =========================================================
   G/L MASTER DATA
   ========================================================= */

INSERT INTO dbo.chart_accounts(account_code, account_name, account_type) VALUES
(N'111', N'Tiền mặt', N'ASSET'),
(N'112', N'Tiền gửi ngân hàng', N'ASSET'),
(N'131', N'Phải thu khách hàng', N'ASSET'),
(N'1331', N'Thuế GTGT đầu vào', N'ASSET'),
(N'152', N'Nguyên vật liệu', N'ASSET'),
(N'154', N'Chi phí sản xuất dở dang', N'ASSET'),
(N'155', N'Thành phẩm', N'ASSET'),
(N'156', N'Hàng hóa', N'ASSET'),
(N'331', N'Phải trả nhà cung cấp', N'LIABILITY'),
(N'3331', N'Thuế GTGT đầu ra', N'LIABILITY'),
(N'511', N'Doanh thu bán hàng', N'REVENUE'),
(N'521', N'Các khoản giảm trừ doanh thu', N'REVENUE_DEDUCTION'),
(N'632', N'Giá vốn hàng bán', N'EXPENSE'),
(N'641', N'Chi phí bán hàng', N'EXPENSE'),
(N'642', N'Chi phí quản lý doanh nghiệp', N'EXPENSE'),
(N'711', N'Thu nhập khác', N'REVENUE'),
(N'811', N'Chi phí khác', N'EXPENSE');
GO

UPDATE dbo.chart_accounts
SET account_group = CASE
        WHEN account_code IN (N'111', N'112') THEN N'CASH_BANK'
        WHEN account_code = N'131' THEN N'AR'
        WHEN account_code = N'331' THEN N'AP'
        WHEN account_code IN (N'1331', N'3331') THEN N'TAX'
        WHEN account_code IN (N'152', N'155', N'156') THEN N'INVENTORY'
        WHEN account_code = N'154' THEN N'WIP'
        WHEN account_code IN (N'511', N'711') THEN N'REVENUE'
        WHEN account_code = N'521' THEN N'REVENUE_DEDUCTION'
        WHEN account_code = N'632' THEN N'COGS'
        WHEN account_code IN (N'641', N'642', N'811') THEN N'EXPENSE'
        ELSE N'OTHER' END,
    normal_balance = CASE WHEN account_type IN (N'LIABILITY', N'EQUITY', N'REVENUE') THEN N'CREDIT' ELSE N'DEBIT' END,
    is_open_item = CASE WHEN account_code IN (N'131', N'331') THEN 1 ELSE 0 END,
    open_item_type = CASE WHEN account_code = N'131' THEN N'CUSTOMER' WHEN account_code = N'331' THEN N'VENDOR' ELSE N'NONE' END,
    posting_allowed = 1,
    coa_node_id = (SELECT TOP 1 id FROM dbo.coa_nodes WHERE node_code = CASE
        WHEN account_type = N'ASSET' THEN N'BS-ASSET'
        WHEN account_type = N'LIABILITY' THEN N'BS-LIABILITY'
        WHEN account_type = N'EQUITY' THEN N'BS-EQUITY'
        WHEN account_type = N'REVENUE' THEN N'PL-REV'
        WHEN account_type = N'REVENUE_DEDUCTION' THEN N'PL-REV-DED'
        WHEN account_code = N'632' THEN N'PL-COGS'
        WHEN account_type = N'EXPENSE' THEN N'PL-EXP'
        ELSE N'PL-OTHER' END)
WHERE account_code IN (N'111',N'112',N'131',N'1331',N'152',N'154',N'155',N'156',N'331',N'3331',N'511',N'521',N'632',N'641',N'642',N'711',N'811');
GO

/* =========================================================
   TAX CODES
   ========================================================= */

INSERT INTO dbo.tax_codes(tax_code, tax_name, tax_type, rate, vat_account_id, input_account_id, output_account_id)
SELECT N'VAT10_IN', N'Input VAT 10%', N'INPUT', 10.0000,
       (SELECT id FROM dbo.chart_accounts WHERE account_code=N'1331'),
       (SELECT id FROM dbo.chart_accounts WHERE account_code=N'1331'), NULL;
GO

INSERT INTO dbo.tax_codes(tax_code, tax_name, tax_type, rate, vat_account_id, input_account_id, output_account_id)
SELECT N'VAT10_OUT', N'Output VAT 10%', N'OUTPUT', 10.0000,
       (SELECT id FROM dbo.chart_accounts WHERE account_code=N'3331'),
       NULL, (SELECT id FROM dbo.chart_accounts WHERE account_code=N'3331');
GO

INSERT INTO dbo.tax_codes(tax_code, tax_name, tax_type, rate, vat_account_id, input_account_id, output_account_id)
SELECT N'VAT0_IN', N'Input VAT 0%', N'INPUT', 0.0000,
       (SELECT id FROM dbo.chart_accounts WHERE account_code=N'1331'),
       (SELECT id FROM dbo.chart_accounts WHERE account_code=N'1331'), NULL;
GO

INSERT INTO dbo.tax_codes(tax_code, tax_name, tax_type, rate, vat_account_id, input_account_id, output_account_id)
SELECT N'VAT0_OUT', N'Output VAT 0%', N'OUTPUT', 0.0000,
       (SELECT id FROM dbo.chart_accounts WHERE account_code=N'3331'),
       NULL, (SELECT id FROM dbo.chart_accounts WHERE account_code=N'3331');
GO

/* =========================================================
   WAREHOUSES
   ========================================================= */

INSERT INTO dbo.warehouses(warehouse_code, warehouse_name, warehouse_type) VALUES
(N'MAIN', N'Kho tổng', N'MAIN'),
(N'STORE01', N'Kho cửa hàng 01', N'STORE'),
(N'KITCHEN', N'Kho bếp / sản xuất', N'PRODUCTION');
GO

/* =========================================================
   BUSINESS PARTNERS
   ========================================================= */

INSERT INTO dbo.business_partners(bp_code, bp_name, bp_type, bp_category, phone, email, ar_account_id, ap_account_id) VALUES
(N'CASH', N'Khách lẻ', N'CUSTOMER', N'ONE_TIME', NULL, NULL, (SELECT id FROM dbo.chart_accounts WHERE account_code=N'131'), NULL),
(N'CUST001', N'Khách hàng sỉ mẫu', N'CUSTOMER', N'COMPANY', N'0900000001', N'customer@example.com', (SELECT id FROM dbo.chart_accounts WHERE account_code=N'131'), NULL),
(N'VEND001', N'Nhà cung cấp nguyên vật liệu mẫu', N'VENDOR', N'COMPANY', N'0900000002', N'vendor@example.com', NULL, (SELECT id FROM dbo.chart_accounts WHERE account_code=N'331'));
GO

/* =========================================================
   SALE CHANNELS
   ========================================================= */

INSERT INTO dbo.sale_channels(channel_code, channel_name, channel_type, external_source, default_customer_id, default_warehouse_id, revenue_account_id, discount_account_id, default_tax_code_id, default_tax_rate)
SELECT v.channel_code, v.channel_name, v.channel_type, v.external_source, c.id, w.id, a.id, d.id, t.id, t.rate
FROM (VALUES
    (N'RETAIL', N'Bán lẻ tại cửa hàng', N'RETAIL', N'Manual/POS', N'CASH', N'STORE01', N'511', N'521', N'VAT10_OUT'),
    (N'POS', N'Phần mềm POS', N'POS', N'CSV/API', N'CASH', N'STORE01', N'511', N'521', N'VAT10_OUT'),
    (N'ONLINE', N'Bán hàng online', N'ONLINE', N'Online Store', N'CASH', N'STORE01', N'511', N'521', N'VAT10_OUT'),
    (N'DELIVERY', N'Ứng dụng giao hàng', N'DELIVERY', N'GrabFood/ShopeeFood/BeFood', N'CASH', N'STORE01', N'511', N'521', N'VAT10_OUT'),
    (N'WHOLESALE', N'Bán sỉ/đại lý', N'WHOLESALE', N'Manual', N'CUST001', N'MAIN', N'511', N'521', N'VAT10_OUT')
) v(channel_code, channel_name, channel_type, external_source, customer_code, warehouse_code, revenue_account_code, discount_account_code, tax_code)
LEFT JOIN dbo.business_partners c ON c.bp_code = v.customer_code
LEFT JOIN dbo.warehouses w ON w.warehouse_code = v.warehouse_code
LEFT JOIN dbo.chart_accounts a ON a.account_code = v.revenue_account_code
LEFT JOIN dbo.chart_accounts d ON d.account_code = v.discount_account_code
LEFT JOIN dbo.tax_codes t ON t.tax_code = v.tax_code;
GO

/* =========================================================
   ITEMS
   ========================================================= */

INSERT INTO dbo.items(item_code, item_name, item_type, base_uom, standard_cost, sales_price,
                      input_tax_code_id, output_tax_code_id,
                      inventory_account_id, cogs_account_id, revenue_account_id, wip_account_id,
                      expiry_tracking, lot_tracking)
SELECT N'RM-COFFEE', N'Cà phê hạt', N'RAW', N'gram', 0.2000, 0,
       (SELECT id FROM dbo.tax_codes WHERE tax_code=N'VAT10_IN'), NULL,
       (SELECT id FROM dbo.chart_accounts WHERE account_code=N'152'),
       NULL, NULL,
       (SELECT id FROM dbo.chart_accounts WHERE account_code=N'154'),
       1, 1;
GO

INSERT INTO dbo.items(item_code, item_name, item_type, base_uom, standard_cost, sales_price,
                      input_tax_code_id, output_tax_code_id,
                      inventory_account_id, cogs_account_id, revenue_account_id, wip_account_id,
                      expiry_tracking, lot_tracking)
SELECT N'RM-MILK', N'Sữa đặc', N'RAW', N'gram', 0.1000, 0,
       (SELECT id FROM dbo.tax_codes WHERE tax_code=N'VAT10_IN'), NULL,
       (SELECT id FROM dbo.chart_accounts WHERE account_code=N'152'),
       NULL, NULL,
       (SELECT id FROM dbo.chart_accounts WHERE account_code=N'154'),
       1, 1;
GO

INSERT INTO dbo.items(item_code, item_name, item_type, base_uom, standard_cost, sales_price,
                      input_tax_code_id, output_tax_code_id,
                      inventory_account_id, cogs_account_id, revenue_account_id, wip_account_id,
                      expiry_tracking, lot_tracking)
SELECT N'PK-BOTTLE', N'Chai nhựa 250ml', N'PACKAGING', N'piece', 1200, 0,
       (SELECT id FROM dbo.tax_codes WHERE tax_code=N'VAT10_IN'), NULL,
       (SELECT id FROM dbo.chart_accounts WHERE account_code=N'152'),
       NULL, NULL,
       (SELECT id FROM dbo.chart_accounts WHERE account_code=N'154'),
       0, 0;
GO

INSERT INTO dbo.items(item_code, item_name, item_type, base_uom, standard_cost, sales_price,
                      input_tax_code_id, output_tax_code_id,
                      inventory_account_id, cogs_account_id, revenue_account_id, wip_account_id,
                      expiry_tracking, lot_tracking)
SELECT N'FG-COFFEE-BOTTLE', N'Cà phê sữa đóng chai 250ml', N'FINISHED', N'bottle', 12000, 25000,
       NULL, (SELECT id FROM dbo.tax_codes WHERE tax_code=N'VAT10_OUT'),
       (SELECT id FROM dbo.chart_accounts WHERE account_code=N'155'),
       (SELECT id FROM dbo.chart_accounts WHERE account_code=N'632'),
       (SELECT id FROM dbo.chart_accounts WHERE account_code=N'511'),
       (SELECT id FROM dbo.chart_accounts WHERE account_code=N'154'),
       1, 1;
GO

/* =========================================================
   BOM / RECIPE
   ========================================================= */

INSERT INTO dbo.boms(bom_code, finished_item_id, version_no, base_qty)
SELECT N'BOM-COFFEE-BOTTLE-V1', id, N'V1', 1 FROM dbo.items WHERE item_code=N'FG-COFFEE-BOTTLE';
GO

INSERT INTO dbo.bom_components(bom_id, component_item_id, qty_per, scrap_percent)
SELECT (SELECT id FROM dbo.boms WHERE bom_code=N'BOM-COFFEE-BOTTLE-V1'), id, 30, 2 FROM dbo.items WHERE item_code=N'RM-COFFEE';
INSERT INTO dbo.bom_components(bom_id, component_item_id, qty_per, scrap_percent)
SELECT (SELECT id FROM dbo.boms WHERE bom_code=N'BOM-COFFEE-BOTTLE-V1'), id, 20, 1 FROM dbo.items WHERE item_code=N'RM-MILK';
INSERT INTO dbo.bom_components(bom_id, component_item_id, qty_per, scrap_percent)
SELECT (SELECT id FROM dbo.boms WHERE bom_code=N'BOM-COFFEE-BOTTLE-V1'), id, 1, 0 FROM dbo.items WHERE item_code=N'PK-BOTTLE';
GO

/* =========================================================
   NUMBER RANGES
   ========================================================= */

INSERT INTO dbo.number_ranges(object_code, subkey, prefix_template, next_no, width, year_mode, allow_manual) VALUES
-- Master Data numbering
(N'CUSTOMER', N'', N'CUST-{YYYY}-{00001}', 1, 5, 1, 1),
(N'VENDOR', N'', N'VEND-{YYYY}-{00001}', 1, 5, 1, 1),
(N'BP', N'', N'BP-{YYYY}-{00001}', 1, 5, 1, 1),
(N'ITEM', N'', N'ITM-{00001}', 1, 5, 0, 1),
(N'ITEM', N'RAW', N'RM-{00001}', 1, 5, 0, 1),
(N'ITEM', N'PACKAGING', N'PK-{00001}', 1, 5, 0, 1),
(N'ITEM', N'FINISHED', N'FG-{00001}', 1, 5, 0, 1),
(N'ITEM', N'RESALE', N'RS-{00001}', 1, 5, 0, 1),
(N'ITEM', N'SERVICE', N'SVC-{00001}', 1, 5, 0, 1),
(N'WAREHOUSE', N'', N'WH-{00001}', 1, 4, 0, 1),
(N'WAREHOUSE', N'MAIN', N'MAIN-{00001}', 1, 3, 0, 1),
(N'WAREHOUSE', N'STORE', N'STORE-{00001}', 1, 3, 0, 1),
(N'WAREHOUSE', N'PRODUCTION', N'PROD-WH-{00001}', 1, 3, 0, 1),
(N'TAX', N'', N'TAX-{00001}', 1, 3, 0, 1),
(N'COA', N'', N'COA-{00001}', 1, 5, 0, 1),
(N'COA', N'BALANCE_SHEET', N'BS-{00001}', 1, 4, 0, 1),
(N'COA', N'P_AND_L', N'PL-{00001}', 1, 4, 0, 1),
(N'GL', N'', N'GL-{00001}', 1, 5, 0, 1),
(N'SALE_CHANNEL', N'', N'CH-{00001}', 1, 4, 0, 1),
(N'BOM', N'', N'BOM-{YYYY}-{00001}', 1, 5, 1, 1),
-- Transaction document numbering
(N'PO', N'', N'PO-{YYYY}-{MM}-{00001}', 1, 5, 1, 1),
(N'GR', N'', N'GR-{YYYY}-{MM}-{00001}', 1, 5, 1, 1),
(N'AP', N'', N'AP-{YYYY}-{MM}-{00001}', 1, 5, 1, 1),
(N'VP', N'', N'VP-{YYYY}-{MM}-{00001}', 1, 5, 1, 1),
(N'SO', N'', N'SO-{YYYY}-{MM}-{00001}', 1, 5, 1, 1),
(N'DL', N'', N'DL-{YYYY}-{MM}-{00001}', 1, 5, 1, 1),
(N'AR', N'', N'AR-{YYYY}-{MM}-{00001}', 1, 5, 1, 1),
(N'CR', N'', N'CR-{YYYY}-{MM}-{00001}', 1, 5, 1, 1),
(N'PROD', N'', N'PROD-{YYYY}-{MM}-{00001}', 1, 5, 1, 1),
(N'MI', N'', N'MI-{YYYY}-{MM}-{00001}', 1, 5, 1, 1),
(N'PR', N'', N'PR-{YYYY}-{MM}-{00001}', 1, 5, 1, 1),
(N'IM', N'', N'IM-{YYYY}-{MM}-{00001}', 1, 5, 1, 0),
(N'JE', N'', N'JE-{YYYY}-{MM}-{00001}', 1, 5, 1, 0);
GO

/* =========================================================
   USERS, GROUPS, PERMISSIONS
   Password for admin: Admin@123
   If bcrypt version issue occurs, run scripts/reset_admin_password.py
   ========================================================= */

INSERT INTO dbo.users(username, password_hash, full_name, email)
VALUES (N'admin', N'sha256$e86f78a8a3caf0b60d8e74e5942aa6d86dc150cd3c03338aef25b7d2d7e3acc7', N'Administrator', N'admin@example.com');
GO

INSERT INTO dbo.user_groups(group_code, group_name, description) VALUES
(N'ADMIN', N'Administrators', N'Full system access'),
(N'PURCHASING', N'Purchasing Users', N'Purchase process access'),
(N'SALES', N'Sales Users', N'Sales process access'),
(N'WAREHOUSE', N'Warehouse Users', N'Inventory process access'),
(N'PRODUCTION', N'Production Users', N'Production process access'),
(N'ACCOUNTING', N'Accounting Users', N'Accounting process access');
GO

INSERT INTO dbo.user_group_members(user_id, group_id)
SELECT u.id, g.id FROM dbo.users u CROSS JOIN dbo.user_groups g
WHERE u.username=N'admin' AND g.group_code=N'ADMIN';
GO

INSERT INTO dbo.permissions(permission_code, permission_name, module_code) VALUES
(N'DASHBOARD_VIEW', N'View dashboard', N'CORE'),
(N'MASTER_VIEW', N'View master data', N'MASTER'),
(N'MASTER_EDIT', N'Edit master data', N'MASTER'),
(N'PURCHASE_VIEW', N'View purchasing', N'PURCHASE'),
(N'PURCHASE_EDIT', N'Create/edit purchasing documents', N'PURCHASE'),
(N'SALES_VIEW', N'View sales', N'SALES'),
(N'SALES_EDIT', N'Create/edit sales documents', N'SALES'),
(N'INVENTORY_VIEW', N'View inventory', N'INVENTORY'),
(N'INVENTORY_EDIT', N'Create inventory movements', N'INVENTORY'),
(N'PRODUCTION_VIEW', N'View production', N'PRODUCTION'),
(N'PRODUCTION_EDIT', N'Create production documents', N'PRODUCTION'),
(N'ACCOUNTING_VIEW', N'View accounting', N'ACCOUNTING'),
(N'ACCOUNTING_EDIT', N'Post accounting entries', N'ACCOUNTING'),
(N'USER_ADMIN', N'Manage users and permissions', N'SECURITY'),
(N'INTEGRATION_VIEW', N'View integrations', N'INTEGRATION'),
(N'INTEGRATION_EDIT', N'Edit/run integrations', N'INTEGRATION');
GO

INSERT INTO dbo.group_permissions(group_id, permission_id)
SELECT g.id, p.id FROM dbo.user_groups g CROSS JOIN dbo.permissions p WHERE g.group_code=N'ADMIN';
GO

INSERT INTO dbo.group_permissions(group_id, permission_id)
SELECT g.id, p.id FROM dbo.user_groups g JOIN dbo.permissions p ON p.permission_code IN (N'DASHBOARD_VIEW', N'PURCHASE_VIEW', N'PURCHASE_EDIT') WHERE g.group_code=N'PURCHASING';
INSERT INTO dbo.group_permissions(group_id, permission_id)
SELECT g.id, p.id FROM dbo.user_groups g JOIN dbo.permissions p ON p.permission_code IN (N'DASHBOARD_VIEW', N'SALES_VIEW', N'SALES_EDIT') WHERE g.group_code=N'SALES';
INSERT INTO dbo.group_permissions(group_id, permission_id)
SELECT g.id, p.id FROM dbo.user_groups g JOIN dbo.permissions p ON p.permission_code IN (N'DASHBOARD_VIEW', N'INVENTORY_VIEW', N'INVENTORY_EDIT') WHERE g.group_code=N'WAREHOUSE';
INSERT INTO dbo.group_permissions(group_id, permission_id)
SELECT g.id, p.id FROM dbo.user_groups g JOIN dbo.permissions p ON p.permission_code IN (N'DASHBOARD_VIEW', N'PRODUCTION_VIEW', N'PRODUCTION_EDIT') WHERE g.group_code=N'PRODUCTION';
INSERT INTO dbo.group_permissions(group_id, permission_id)
SELECT g.id, p.id FROM dbo.user_groups g JOIN dbo.permissions p ON p.permission_code IN (N'DASHBOARD_VIEW', N'ACCOUNTING_VIEW', N'ACCOUNTING_EDIT') WHERE g.group_code=N'ACCOUNTING';
GO
