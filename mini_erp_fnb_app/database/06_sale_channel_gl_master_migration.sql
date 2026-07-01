USE MiniERPFNB;
GO

/* =========================================================
   v10 Migration - Sale Channel + COA Structure + G/L Master
   Safe to run on existing database. Do not rerun 01_schema.sql
   if you already have transaction/master data.
   ========================================================= */

/* 1) Chart of Accounts report structure table */
IF OBJECT_ID('dbo.coa_nodes', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.coa_nodes (
        id BIGINT IDENTITY(1,1) CONSTRAINT PK_coa_nodes PRIMARY KEY,
        node_code NVARCHAR(50) NOT NULL CONSTRAINT UQ_coa_node_code UNIQUE,
        node_name NVARCHAR(200) NOT NULL,
        report_section NVARCHAR(50) NOT NULL,
        node_type NVARCHAR(50) NOT NULL CONSTRAINT DF_coa_node_type DEFAULT N'HEADER',
        parent_node_id BIGINT NULL,
        normal_balance NVARCHAR(20) NULL,
        sequence_no INT NOT NULL CONSTRAINT DF_coa_node_seq DEFAULT 10,
        is_active BIT NOT NULL CONSTRAINT DF_coa_node_active DEFAULT 1,
        CONSTRAINT FK_coa_node_parent FOREIGN KEY(parent_node_id) REFERENCES dbo.coa_nodes(id)
    );
END;
GO

MERGE dbo.coa_nodes AS tgt
USING (VALUES
    (N'BS', N'Balance Sheet', N'BALANCE_SHEET', N'HEADER', NULL, NULL, 10),
    (N'BS-ASSET', N'Assets', N'BALANCE_SHEET', N'HEADER', N'BS', N'DEBIT', 20),
    (N'BS-LIABILITY', N'Liabilities', N'BALANCE_SHEET', N'HEADER', N'BS', N'CREDIT', 30),
    (N'BS-EQUITY', N'Equity', N'BALANCE_SHEET', N'HEADER', N'BS', N'CREDIT', 40),
    (N'PL', N'Profit and Loss', N'P_AND_L', N'HEADER', NULL, NULL, 50),
    (N'PL-REV', N'Revenue', N'P_AND_L', N'HEADER', N'PL', N'CREDIT', 60),
    (N'PL-COGS', N'Cost of Goods Sold', N'P_AND_L', N'HEADER', N'PL', N'DEBIT', 70),
    (N'PL-EXP', N'Operating Expenses', N'P_AND_L', N'HEADER', N'PL', N'DEBIT', 80),
    (N'PL-OTHER', N'Other Income/Expense', N'P_AND_L', N'HEADER', N'PL', NULL, 90)
) src(node_code, node_name, report_section, node_type, parent_node_code, normal_balance, sequence_no)
ON tgt.node_code = src.node_code
WHEN NOT MATCHED THEN
    INSERT(node_code, node_name, report_section, node_type, parent_node_id, normal_balance, sequence_no, is_active)
    VALUES(src.node_code, src.node_name, src.report_section, src.node_type, NULL, src.normal_balance, src.sequence_no, 1)
WHEN MATCHED THEN
    UPDATE SET node_name = src.node_name,
               report_section = src.report_section,
               node_type = src.node_type,
               normal_balance = src.normal_balance,
               sequence_no = src.sequence_no;
GO

UPDATE child
SET parent_node_id = parent.id
FROM dbo.coa_nodes child
JOIN (VALUES
    (N'BS-ASSET', N'BS'),
    (N'BS-LIABILITY', N'BS'),
    (N'BS-EQUITY', N'BS'),
    (N'PL-REV', N'PL'),
    (N'PL-COGS', N'PL'),
    (N'PL-EXP', N'PL'),
    (N'PL-OTHER', N'PL')
) map(child_code, parent_code) ON map.child_code = child.node_code
JOIN dbo.coa_nodes parent ON parent.node_code = map.parent_code;
GO

/* 2) Extend existing dbo.chart_accounts to become G/L Master Data */
IF COL_LENGTH('dbo.chart_accounts', 'account_group') IS NULL
    ALTER TABLE dbo.chart_accounts ADD account_group NVARCHAR(50) NULL;
GO
IF COL_LENGTH('dbo.chart_accounts', 'normal_balance') IS NULL
    ALTER TABLE dbo.chart_accounts ADD normal_balance NVARCHAR(20) NULL;
GO
IF COL_LENGTH('dbo.chart_accounts', 'coa_node_id') IS NULL
    ALTER TABLE dbo.chart_accounts ADD coa_node_id BIGINT NULL;
GO
IF COL_LENGTH('dbo.chart_accounts', 'is_open_item') IS NULL
    ALTER TABLE dbo.chart_accounts ADD is_open_item BIT NOT NULL CONSTRAINT DF_gl_open_item DEFAULT 0;
GO
IF COL_LENGTH('dbo.chart_accounts', 'open_item_type') IS NULL
    ALTER TABLE dbo.chart_accounts ADD open_item_type NVARCHAR(30) NOT NULL CONSTRAINT DF_gl_open_type DEFAULT N'NONE';
GO
IF COL_LENGTH('dbo.chart_accounts', 'posting_allowed') IS NULL
    ALTER TABLE dbo.chart_accounts ADD posting_allowed BIT NOT NULL CONSTRAINT DF_gl_posting_allowed DEFAULT 1;
GO

IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = N'FK_gl_coa_node')
BEGIN
    ALTER TABLE dbo.chart_accounts WITH CHECK
    ADD CONSTRAINT FK_gl_coa_node FOREIGN KEY(coa_node_id) REFERENCES dbo.coa_nodes(id);
END;
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
        WHEN account_code = N'632' THEN N'COGS'
        WHEN account_code IN (N'641', N'642', N'811') THEN N'EXPENSE'
        ELSE ISNULL(account_group, N'OTHER') END,
    normal_balance = CASE WHEN account_type IN (N'LIABILITY', N'EQUITY', N'REVENUE') THEN N'CREDIT' ELSE N'DEBIT' END,
    is_open_item = CASE WHEN account_code IN (N'131', N'331') THEN 1 ELSE ISNULL(is_open_item, 0) END,
    open_item_type = CASE WHEN account_code = N'131' THEN N'CUSTOMER' WHEN account_code = N'331' THEN N'VENDOR' ELSE ISNULL(open_item_type, N'NONE') END,
    posting_allowed = ISNULL(posting_allowed, 1),
    coa_node_id = COALESCE(coa_node_id, (SELECT TOP 1 id FROM dbo.coa_nodes WHERE node_code = CASE
        WHEN account_type = N'ASSET' THEN N'BS-ASSET'
        WHEN account_type = N'LIABILITY' THEN N'BS-LIABILITY'
        WHEN account_type = N'EQUITY' THEN N'BS-EQUITY'
        WHEN account_type = N'REVENUE' THEN N'PL-REV'
        WHEN account_code = N'632' THEN N'PL-COGS'
        WHEN account_type = N'EXPENSE' THEN N'PL-EXP'
        ELSE N'PL-OTHER' END))
WHERE is_active = 1;
GO

/* 3) Sale Channel master */
IF OBJECT_ID('dbo.sale_channels', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.sale_channels (
        id BIGINT IDENTITY(1,1) CONSTRAINT PK_sale_channels PRIMARY KEY,
        channel_code NVARCHAR(50) NOT NULL CONSTRAINT UQ_sale_channels_code UNIQUE,
        channel_name NVARCHAR(200) NOT NULL,
        channel_type NVARCHAR(50) NOT NULL CONSTRAINT DF_sale_channel_type DEFAULT N'RETAIL',
        external_source NVARCHAR(100) NULL,
        default_customer_id BIGINT NULL,
        default_warehouse_id BIGINT NULL,
        revenue_account_id BIGINT NULL,
        discount_account_id BIGINT NULL,
        fee_account_id BIGINT NULL,
        default_tax_rate DECIMAL(9,4) NOT NULL CONSTRAINT DF_sale_channel_tax DEFAULT 10,
        is_active BIT NOT NULL CONSTRAINT DF_sale_channels_active DEFAULT 1,
        CONSTRAINT FK_sale_channel_customer FOREIGN KEY(default_customer_id) REFERENCES dbo.business_partners(id),
        CONSTRAINT FK_sale_channel_warehouse FOREIGN KEY(default_warehouse_id) REFERENCES dbo.warehouses(id),
        CONSTRAINT FK_sale_channel_revenue_account FOREIGN KEY(revenue_account_id) REFERENCES dbo.chart_accounts(id),
        CONSTRAINT FK_sale_channel_discount_account FOREIGN KEY(discount_account_id) REFERENCES dbo.chart_accounts(id),
        CONSTRAINT FK_sale_channel_fee_account FOREIGN KEY(fee_account_id) REFERENCES dbo.chart_accounts(id)
    );
END;
GO

MERGE dbo.sale_channels AS tgt
USING (
    SELECT v.channel_code, v.channel_name, v.channel_type, v.external_source, c.id AS default_customer_id, w.id AS default_warehouse_id, a.id AS revenue_account_id, v.default_tax_rate
    FROM (VALUES
        (N'RETAIL', N'Bán lẻ tại cửa hàng', N'RETAIL', N'Manual/POS', N'CASH', N'STORE01', N'511', CAST(10 AS DECIMAL(9,4))),
        (N'POS', N'Phần mềm POS', N'POS', N'CSV/API', N'CASH', N'STORE01', N'511', CAST(10 AS DECIMAL(9,4))),
        (N'ONLINE', N'Bán hàng online', N'ONLINE', N'Online Store', N'CASH', N'STORE01', N'511', CAST(10 AS DECIMAL(9,4))),
        (N'DELIVERY', N'Ứng dụng giao hàng', N'DELIVERY', N'GrabFood/ShopeeFood/BeFood', N'CASH', N'STORE01', N'511', CAST(10 AS DECIMAL(9,4))),
        (N'WHOLESALE', N'Bán sỉ/đại lý', N'WHOLESALE', N'Manual', N'CUST001', N'MAIN', N'511', CAST(10 AS DECIMAL(9,4)))
    ) v(channel_code, channel_name, channel_type, external_source, customer_code, warehouse_code, revenue_account_code, default_tax_rate)
    LEFT JOIN dbo.business_partners c ON c.bp_code = v.customer_code
    LEFT JOIN dbo.warehouses w ON w.warehouse_code = v.warehouse_code
    LEFT JOIN dbo.chart_accounts a ON a.account_code = v.revenue_account_code
) src
ON tgt.channel_code = src.channel_code
WHEN NOT MATCHED THEN
    INSERT(channel_code, channel_name, channel_type, external_source, default_customer_id, default_warehouse_id, revenue_account_id, default_tax_rate, is_active)
    VALUES(src.channel_code, src.channel_name, src.channel_type, src.external_source, src.default_customer_id, src.default_warehouse_id, src.revenue_account_id, src.default_tax_rate, 1)
WHEN MATCHED THEN
    UPDATE SET channel_name = src.channel_name,
               channel_type = src.channel_type,
               external_source = src.external_source,
               default_customer_id = COALESCE(tgt.default_customer_id, src.default_customer_id),
               default_warehouse_id = COALESCE(tgt.default_warehouse_id, src.default_warehouse_id),
               revenue_account_id = COALESCE(tgt.revenue_account_id, src.revenue_account_id),
               default_tax_rate = COALESCE(tgt.default_tax_rate, src.default_tax_rate);
GO

/* 4) Numbering objects for new master data */
MERGE dbo.number_ranges AS tgt
USING (VALUES
    (N'COA', N'', N'COA-{00001}', 1, 5, 0, 1, 1),
    (N'COA', N'BALANCE_SHEET', N'BS-{00001}', 1, 4, 0, 1, 1),
    (N'COA', N'P_AND_L', N'PL-{00001}', 1, 4, 0, 1, 1),
    (N'GL', N'', N'GL-{00001}', 1, 5, 0, 1, 1),
    (N'SALE_CHANNEL', N'', N'CH-{00001}', 1, 4, 0, 1, 1)
) src(object_code, subkey, prefix_template, next_no, width, year_mode, allow_manual, is_active)
ON tgt.object_code = src.object_code AND tgt.subkey = src.subkey
WHEN NOT MATCHED THEN
    INSERT(object_code, subkey, prefix_template, next_no, width, year_mode, allow_manual, is_active)
    VALUES(src.object_code, src.subkey, src.prefix_template, src.next_no, src.width, src.year_mode, src.allow_manual, src.is_active);
GO
