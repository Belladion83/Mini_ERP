
USE MiniERPFNB;
GO

/* =========================================================
   v16.1 - Purchasing PR/PO + Goods-in-Transit + FIFO Costing
   FIXED / IDEMPOTENT MIGRATION

   Purpose:
   - Safe to run after a partially failed v16 migration.
   - Creates missing PR/PO/GR tables if they were accidentally dropped.
   - Adds missing v16 columns only when needed.
   - Uses long unique constraint names to avoid duplicate names such as FK_prl_item.
   - Does NOT drop existing business data.
   ========================================================= */

/* ---------------------------------------------------------
   0) Ensure base G/L / number ranges
--------------------------------------------------------- */
IF NOT EXISTS (SELECT 1 FROM dbo.chart_accounts WHERE account_code = N'151')
BEGIN
    INSERT INTO dbo.chart_accounts(account_code, account_name, account_type, account_group, normal_balance, coa_node_id, is_open_item, open_item_type, posting_allowed, is_active)
    SELECT N'151', N'Hàng mua đang đi đường', N'ASSET', N'INVENTORY_IN_TRANSIT', N'DEBIT',
           (SELECT TOP 1 id FROM dbo.coa_nodes WHERE node_code = N'BS-ASSET'),
           0, N'NONE', 1, 1;
END
GO

IF NOT EXISTS (SELECT 1 FROM dbo.number_ranges WHERE object_code = N'PRQ' AND subkey = N'')
BEGIN
    INSERT INTO dbo.number_ranges(object_code, subkey, prefix_template, next_no, width, year_mode, allow_manual, is_active)
    VALUES (N'PRQ', N'', N'PR-{YYYY}-{MM}-{00001}', 1, 5, 1, 1, 1);
END
GO

/* ---------------------------------------------------------
   1) Purchase Requisition Header
--------------------------------------------------------- */
IF OBJECT_ID(N'dbo.purchase_requisitions', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.purchase_requisitions (
        id BIGINT IDENTITY(1,1) NOT NULL,
        pr_no NVARCHAR(50) NOT NULL,
        pr_date DATE NOT NULL,
        vendor_id BIGINT NULL,
        requested_by_name NVARCHAR(200) NULL,
        status NVARCHAR(30) NOT NULL CONSTRAINT DF_purchase_requisitions_status_v16 DEFAULT N'DRAFT',
        notes NVARCHAR(1000) NULL,
        total_amount DECIMAL(19,4) NOT NULL CONSTRAINT DF_purchase_requisitions_total_v16 DEFAULT 0,
        created_by BIGINT NULL,
        released_by BIGINT NULL,
        created_at DATETIME2 NOT NULL CONSTRAINT DF_purchase_requisitions_created_v16 DEFAULT SYSUTCDATETIME(),
        released_at DATETIME2 NULL,
        CONSTRAINT PK_purchase_requisitions PRIMARY KEY(id),
        CONSTRAINT UQ_purchase_requisitions_pr_no UNIQUE(pr_no)
    );
END
GO

IF COL_LENGTH(N'dbo.purchase_requisitions', N'pr_no') IS NULL ALTER TABLE dbo.purchase_requisitions ADD pr_no NVARCHAR(50) NULL;
GO
IF COL_LENGTH(N'dbo.purchase_requisitions', N'pr_date') IS NULL ALTER TABLE dbo.purchase_requisitions ADD pr_date DATE NULL;
GO
IF COL_LENGTH(N'dbo.purchase_requisitions', N'vendor_id') IS NULL ALTER TABLE dbo.purchase_requisitions ADD vendor_id BIGINT NULL;
GO
IF COL_LENGTH(N'dbo.purchase_requisitions', N'requested_by_name') IS NULL ALTER TABLE dbo.purchase_requisitions ADD requested_by_name NVARCHAR(200) NULL;
GO
IF COL_LENGTH(N'dbo.purchase_requisitions', N'status') IS NULL ALTER TABLE dbo.purchase_requisitions ADD status NVARCHAR(30) NOT NULL CONSTRAINT DF_purchase_requisitions_status_v16b DEFAULT N'DRAFT';
GO
IF COL_LENGTH(N'dbo.purchase_requisitions', N'notes') IS NULL ALTER TABLE dbo.purchase_requisitions ADD notes NVARCHAR(1000) NULL;
GO
IF COL_LENGTH(N'dbo.purchase_requisitions', N'total_amount') IS NULL ALTER TABLE dbo.purchase_requisitions ADD total_amount DECIMAL(19,4) NOT NULL CONSTRAINT DF_purchase_requisitions_total_v16b DEFAULT 0;
GO
IF COL_LENGTH(N'dbo.purchase_requisitions', N'created_by') IS NULL ALTER TABLE dbo.purchase_requisitions ADD created_by BIGINT NULL;
GO
IF COL_LENGTH(N'dbo.purchase_requisitions', N'released_by') IS NULL ALTER TABLE dbo.purchase_requisitions ADD released_by BIGINT NULL;
GO
IF COL_LENGTH(N'dbo.purchase_requisitions', N'created_at') IS NULL ALTER TABLE dbo.purchase_requisitions ADD created_at DATETIME2 NOT NULL CONSTRAINT DF_purchase_requisitions_created_v16b DEFAULT SYSUTCDATETIME();
GO
IF COL_LENGTH(N'dbo.purchase_requisitions', N'released_at') IS NULL ALTER TABLE dbo.purchase_requisitions ADD released_at DATETIME2 NULL;
GO

/* ---------------------------------------------------------
   2) Purchase Requisition Lines
--------------------------------------------------------- */
IF OBJECT_ID(N'dbo.purchase_requisition_lines', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.purchase_requisition_lines (
        id BIGINT IDENTITY(1,1) NOT NULL,
        pr_id BIGINT NOT NULL,
        line_no INT NOT NULL,
        item_id BIGINT NOT NULL,
        warehouse_id BIGINT NOT NULL,
        quantity DECIMAL(19,4) NOT NULL,
        suggested_vendor_id BIGINT NULL,
        expected_unit_price DECIMAL(19,4) NOT NULL CONSTRAINT DF_purchase_requisition_lines_price_v16 DEFAULT 0,
        tax_code_id BIGINT NULL,
        required_date DATE NULL,
        line_amount DECIMAL(19,4) NOT NULL CONSTRAINT DF_purchase_requisition_lines_amount_v16 DEFAULT 0,
        po_line_id BIGINT NULL,
        CONSTRAINT PK_purchase_requisition_lines PRIMARY KEY(id)
    );
END
GO

IF COL_LENGTH(N'dbo.purchase_requisition_lines', N'pr_id') IS NULL ALTER TABLE dbo.purchase_requisition_lines ADD pr_id BIGINT NULL;
GO
IF COL_LENGTH(N'dbo.purchase_requisition_lines', N'line_no') IS NULL ALTER TABLE dbo.purchase_requisition_lines ADD line_no INT NULL;
GO
IF COL_LENGTH(N'dbo.purchase_requisition_lines', N'item_id') IS NULL ALTER TABLE dbo.purchase_requisition_lines ADD item_id BIGINT NULL;
GO
IF COL_LENGTH(N'dbo.purchase_requisition_lines', N'warehouse_id') IS NULL ALTER TABLE dbo.purchase_requisition_lines ADD warehouse_id BIGINT NULL;
GO
IF COL_LENGTH(N'dbo.purchase_requisition_lines', N'quantity') IS NULL ALTER TABLE dbo.purchase_requisition_lines ADD quantity DECIMAL(19,4) NULL;
GO
IF COL_LENGTH(N'dbo.purchase_requisition_lines', N'suggested_vendor_id') IS NULL ALTER TABLE dbo.purchase_requisition_lines ADD suggested_vendor_id BIGINT NULL;
GO
IF COL_LENGTH(N'dbo.purchase_requisition_lines', N'expected_unit_price') IS NULL ALTER TABLE dbo.purchase_requisition_lines ADD expected_unit_price DECIMAL(19,4) NOT NULL CONSTRAINT DF_purchase_requisition_lines_price_v16b DEFAULT 0;
GO
IF COL_LENGTH(N'dbo.purchase_requisition_lines', N'tax_code_id') IS NULL ALTER TABLE dbo.purchase_requisition_lines ADD tax_code_id BIGINT NULL;
GO
IF COL_LENGTH(N'dbo.purchase_requisition_lines', N'required_date') IS NULL ALTER TABLE dbo.purchase_requisition_lines ADD required_date DATE NULL;
GO
IF COL_LENGTH(N'dbo.purchase_requisition_lines', N'line_amount') IS NULL ALTER TABLE dbo.purchase_requisition_lines ADD line_amount DECIMAL(19,4) NOT NULL CONSTRAINT DF_purchase_requisition_lines_amount_v16b DEFAULT 0;
GO
IF COL_LENGTH(N'dbo.purchase_requisition_lines', N'po_line_id') IS NULL ALTER TABLE dbo.purchase_requisition_lines ADD po_line_id BIGINT NULL;
GO

/* ---------------------------------------------------------
   3) Base PO/GR tables - recreate if cleanup accidentally removed them
--------------------------------------------------------- */
IF OBJECT_ID(N'dbo.purchase_orders', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.purchase_orders (
        id BIGINT IDENTITY(1,1) NOT NULL,
        po_no NVARCHAR(50) NOT NULL,
        po_date DATE NOT NULL,
        vendor_id BIGINT NOT NULL,
        status NVARCHAR(30) NOT NULL CONSTRAINT DF_purchase_orders_status_v16 DEFAULT N'DRAFT',
        currency_code NVARCHAR(10) NOT NULL CONSTRAINT DF_purchase_orders_currency_v16 DEFAULT N'VND',
        total_amount DECIMAL(19,4) NOT NULL CONSTRAINT DF_purchase_orders_total_v16 DEFAULT 0,
        tax_amount DECIMAL(19,4) NOT NULL CONSTRAINT DF_purchase_orders_tax_v16 DEFAULT 0,
        grand_total DECIMAL(19,4) NOT NULL CONSTRAINT DF_purchase_orders_grand_v16 DEFAULT 0,
        created_by BIGINT NULL,
        created_at DATETIME2 NOT NULL CONSTRAINT DF_purchase_orders_created_v16 DEFAULT SYSUTCDATETIME(),
        pr_id BIGINT NULL,
        notes NVARCHAR(1000) NULL,
        released_by BIGINT NULL,
        released_at DATETIME2 NULL,
        in_transit_posted BIT NOT NULL CONSTRAINT DF_purchase_orders_in_transit_posted_v16 DEFAULT 0,
        in_transit_journal_entry_id BIGINT NULL,
        CONSTRAINT PK_purchase_orders PRIMARY KEY(id),
        CONSTRAINT UQ_purchase_orders_po_no UNIQUE(po_no)
    );
END
GO

IF OBJECT_ID(N'dbo.purchase_order_lines', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.purchase_order_lines (
        id BIGINT IDENTITY(1,1) NOT NULL,
        po_id BIGINT NOT NULL,
        line_no INT NOT NULL,
        item_id BIGINT NOT NULL,
        warehouse_id BIGINT NOT NULL,
        quantity DECIMAL(19,4) NOT NULL,
        unit_price DECIMAL(19,4) NOT NULL,
        tax_code_id BIGINT NULL,
        line_amount DECIMAL(19,4) NOT NULL,
        tax_amount DECIMAL(19,4) NOT NULL CONSTRAINT DF_purchase_order_lines_tax_v16 DEFAULT 0,
        pr_line_id BIGINT NULL,
        received_qty DECIMAL(19,4) NOT NULL CONSTRAINT DF_purchase_order_lines_received_qty_v16 DEFAULT 0,
        CONSTRAINT PK_purchase_order_lines PRIMARY KEY(id)
    );
END
GO

IF OBJECT_ID(N'dbo.goods_receipts', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.goods_receipts (
        id BIGINT IDENTITY(1,1) NOT NULL,
        gr_no NVARCHAR(50) NOT NULL,
        gr_date DATE NOT NULL,
        po_id BIGINT NULL,
        vendor_id BIGINT NOT NULL,
        status NVARCHAR(30) NOT NULL CONSTRAINT DF_goods_receipts_status_v16 DEFAULT N'POSTED',
        created_by BIGINT NULL,
        created_at DATETIME2 NOT NULL CONSTRAINT DF_goods_receipts_created_v16 DEFAULT SYSUTCDATETIME(),
        journal_entry_id BIGINT NULL,
        notes NVARCHAR(1000) NULL,
        CONSTRAINT PK_goods_receipts PRIMARY KEY(id),
        CONSTRAINT UQ_goods_receipts_gr_no UNIQUE(gr_no)
    );
END
GO

IF OBJECT_ID(N'dbo.goods_receipt_lines', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.goods_receipt_lines (
        id BIGINT IDENTITY(1,1) NOT NULL,
        gr_id BIGINT NOT NULL,
        po_line_id BIGINT NULL,
        item_id BIGINT NOT NULL,
        warehouse_id BIGINT NOT NULL,
        quantity DECIMAL(19,4) NOT NULL,
        unit_cost DECIMAL(19,4) NOT NULL,
        lot_no NVARCHAR(100) NULL,
        expiry_date DATE NULL,
        line_amount DECIMAL(19,4) NOT NULL CONSTRAINT DF_goods_receipt_lines_amount_v16 DEFAULT 0,
        CONSTRAINT PK_goods_receipt_lines PRIMARY KEY(id)
    );
END
GO

/* ---------------------------------------------------------
   4) Add missing v16 columns to existing PO/GR tables
--------------------------------------------------------- */
IF COL_LENGTH(N'dbo.purchase_orders', N'pr_id') IS NULL ALTER TABLE dbo.purchase_orders ADD pr_id BIGINT NULL;
GO
IF COL_LENGTH(N'dbo.purchase_orders', N'notes') IS NULL ALTER TABLE dbo.purchase_orders ADD notes NVARCHAR(1000) NULL;
GO
IF COL_LENGTH(N'dbo.purchase_orders', N'released_by') IS NULL ALTER TABLE dbo.purchase_orders ADD released_by BIGINT NULL;
GO
IF COL_LENGTH(N'dbo.purchase_orders', N'released_at') IS NULL ALTER TABLE dbo.purchase_orders ADD released_at DATETIME2 NULL;
GO
IF COL_LENGTH(N'dbo.purchase_orders', N'in_transit_posted') IS NULL ALTER TABLE dbo.purchase_orders ADD in_transit_posted BIT NOT NULL CONSTRAINT DF_purchase_orders_in_transit_posted_v16b DEFAULT 0;
GO
IF COL_LENGTH(N'dbo.purchase_orders', N'in_transit_journal_entry_id') IS NULL ALTER TABLE dbo.purchase_orders ADD in_transit_journal_entry_id BIGINT NULL;
GO
IF COL_LENGTH(N'dbo.purchase_order_lines', N'pr_line_id') IS NULL ALTER TABLE dbo.purchase_order_lines ADD pr_line_id BIGINT NULL;
GO
IF COL_LENGTH(N'dbo.purchase_order_lines', N'received_qty') IS NULL ALTER TABLE dbo.purchase_order_lines ADD received_qty DECIMAL(19,4) NOT NULL CONSTRAINT DF_purchase_order_lines_received_qty_v16b DEFAULT 0;
GO
IF COL_LENGTH(N'dbo.goods_receipts', N'journal_entry_id') IS NULL ALTER TABLE dbo.goods_receipts ADD journal_entry_id BIGINT NULL;
GO
IF COL_LENGTH(N'dbo.goods_receipts', N'notes') IS NULL ALTER TABLE dbo.goods_receipts ADD notes NVARCHAR(1000) NULL;
GO
IF COL_LENGTH(N'dbo.goods_receipt_lines', N'line_amount') IS NULL ALTER TABLE dbo.goods_receipt_lines ADD line_amount DECIMAL(19,4) NOT NULL CONSTRAINT DF_goods_receipt_lines_amount_v16b DEFAULT 0;
GO

/* ---------------------------------------------------------
   5) Add foreign keys only if equivalent relation does not already exist
--------------------------------------------------------- */
DECLARE @sql NVARCHAR(MAX);

-- Helper pattern: check parent table + column + referenced table.
IF NOT EXISTS (
    SELECT 1 FROM sys.foreign_keys fk
    JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
    WHERE fk.parent_object_id = OBJECT_ID(N'dbo.purchase_requisitions')
      AND COL_NAME(fkc.parent_object_id, fkc.parent_column_id) = N'vendor_id'
      AND fk.referenced_object_id = OBJECT_ID(N'dbo.business_partners')
)
    ALTER TABLE dbo.purchase_requisitions ADD CONSTRAINT FK_purchase_requisitions_vendor_v16 FOREIGN KEY(vendor_id) REFERENCES dbo.business_partners(id);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.foreign_keys fk JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
    WHERE fk.parent_object_id = OBJECT_ID(N'dbo.purchase_requisitions') AND COL_NAME(fkc.parent_object_id, fkc.parent_column_id) = N'created_by' AND fk.referenced_object_id = OBJECT_ID(N'dbo.users')
)
    ALTER TABLE dbo.purchase_requisitions ADD CONSTRAINT FK_purchase_requisitions_created_by_v16 FOREIGN KEY(created_by) REFERENCES dbo.users(id);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.foreign_keys fk JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
    WHERE fk.parent_object_id = OBJECT_ID(N'dbo.purchase_requisitions') AND COL_NAME(fkc.parent_object_id, fkc.parent_column_id) = N'released_by' AND fk.referenced_object_id = OBJECT_ID(N'dbo.users')
)
    ALTER TABLE dbo.purchase_requisitions ADD CONSTRAINT FK_purchase_requisitions_released_by_v16 FOREIGN KEY(released_by) REFERENCES dbo.users(id);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.foreign_keys fk JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
    WHERE fk.parent_object_id = OBJECT_ID(N'dbo.purchase_requisition_lines') AND COL_NAME(fkc.parent_object_id, fkc.parent_column_id) = N'pr_id' AND fk.referenced_object_id = OBJECT_ID(N'dbo.purchase_requisitions')
)
    ALTER TABLE dbo.purchase_requisition_lines ADD CONSTRAINT FK_purchase_requisition_lines_pr_v16 FOREIGN KEY(pr_id) REFERENCES dbo.purchase_requisitions(id);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.foreign_keys fk JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
    WHERE fk.parent_object_id = OBJECT_ID(N'dbo.purchase_requisition_lines') AND COL_NAME(fkc.parent_object_id, fkc.parent_column_id) = N'item_id' AND fk.referenced_object_id = OBJECT_ID(N'dbo.items')
)
    ALTER TABLE dbo.purchase_requisition_lines ADD CONSTRAINT FK_purchase_requisition_lines_item_v16 FOREIGN KEY(item_id) REFERENCES dbo.items(id);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.foreign_keys fk JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
    WHERE fk.parent_object_id = OBJECT_ID(N'dbo.purchase_requisition_lines') AND COL_NAME(fkc.parent_object_id, fkc.parent_column_id) = N'warehouse_id' AND fk.referenced_object_id = OBJECT_ID(N'dbo.warehouses')
)
    ALTER TABLE dbo.purchase_requisition_lines ADD CONSTRAINT FK_purchase_requisition_lines_warehouse_v16 FOREIGN KEY(warehouse_id) REFERENCES dbo.warehouses(id);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.foreign_keys fk JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
    WHERE fk.parent_object_id = OBJECT_ID(N'dbo.purchase_requisition_lines') AND COL_NAME(fkc.parent_object_id, fkc.parent_column_id) = N'suggested_vendor_id' AND fk.referenced_object_id = OBJECT_ID(N'dbo.business_partners')
)
    ALTER TABLE dbo.purchase_requisition_lines ADD CONSTRAINT FK_purchase_requisition_lines_vendor_v16 FOREIGN KEY(suggested_vendor_id) REFERENCES dbo.business_partners(id);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.foreign_keys fk JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
    WHERE fk.parent_object_id = OBJECT_ID(N'dbo.purchase_requisition_lines') AND COL_NAME(fkc.parent_object_id, fkc.parent_column_id) = N'tax_code_id' AND fk.referenced_object_id = OBJECT_ID(N'dbo.tax_codes')
)
    ALTER TABLE dbo.purchase_requisition_lines ADD CONSTRAINT FK_purchase_requisition_lines_tax_v16 FOREIGN KEY(tax_code_id) REFERENCES dbo.tax_codes(id);
GO

IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys fk JOIN sys.foreign_key_columns fkc ON fk.object_id=fkc.constraint_object_id WHERE fk.parent_object_id=OBJECT_ID(N'dbo.purchase_orders') AND COL_NAME(fkc.parent_object_id,fkc.parent_column_id)=N'vendor_id' AND fk.referenced_object_id=OBJECT_ID(N'dbo.business_partners'))
    ALTER TABLE dbo.purchase_orders ADD CONSTRAINT FK_purchase_orders_vendor_v16 FOREIGN KEY(vendor_id) REFERENCES dbo.business_partners(id);
GO
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys fk JOIN sys.foreign_key_columns fkc ON fk.object_id=fkc.constraint_object_id WHERE fk.parent_object_id=OBJECT_ID(N'dbo.purchase_orders') AND COL_NAME(fkc.parent_object_id,fkc.parent_column_id)=N'created_by' AND fk.referenced_object_id=OBJECT_ID(N'dbo.users'))
    ALTER TABLE dbo.purchase_orders ADD CONSTRAINT FK_purchase_orders_created_by_v16 FOREIGN KEY(created_by) REFERENCES dbo.users(id);
GO
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys fk JOIN sys.foreign_key_columns fkc ON fk.object_id=fkc.constraint_object_id WHERE fk.parent_object_id=OBJECT_ID(N'dbo.purchase_orders') AND COL_NAME(fkc.parent_object_id,fkc.parent_column_id)=N'pr_id' AND fk.referenced_object_id=OBJECT_ID(N'dbo.purchase_requisitions'))
    ALTER TABLE dbo.purchase_orders ADD CONSTRAINT FK_purchase_orders_pr_v16 FOREIGN KEY(pr_id) REFERENCES dbo.purchase_requisitions(id);
GO
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys fk JOIN sys.foreign_key_columns fkc ON fk.object_id=fkc.constraint_object_id WHERE fk.parent_object_id=OBJECT_ID(N'dbo.purchase_orders') AND COL_NAME(fkc.parent_object_id,fkc.parent_column_id)=N'released_by' AND fk.referenced_object_id=OBJECT_ID(N'dbo.users'))
    ALTER TABLE dbo.purchase_orders ADD CONSTRAINT FK_purchase_orders_released_by_v16 FOREIGN KEY(released_by) REFERENCES dbo.users(id);
GO
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys fk JOIN sys.foreign_key_columns fkc ON fk.object_id=fkc.constraint_object_id WHERE fk.parent_object_id=OBJECT_ID(N'dbo.purchase_orders') AND COL_NAME(fkc.parent_object_id,fkc.parent_column_id)=N'in_transit_journal_entry_id' AND fk.referenced_object_id=OBJECT_ID(N'dbo.journal_entries'))
    ALTER TABLE dbo.purchase_orders ADD CONSTRAINT FK_purchase_orders_in_transit_je_v16 FOREIGN KEY(in_transit_journal_entry_id) REFERENCES dbo.journal_entries(id);
GO

IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys fk JOIN sys.foreign_key_columns fkc ON fk.object_id=fkc.constraint_object_id WHERE fk.parent_object_id=OBJECT_ID(N'dbo.purchase_order_lines') AND COL_NAME(fkc.parent_object_id,fkc.parent_column_id)=N'po_id' AND fk.referenced_object_id=OBJECT_ID(N'dbo.purchase_orders'))
    ALTER TABLE dbo.purchase_order_lines ADD CONSTRAINT FK_purchase_order_lines_po_v16 FOREIGN KEY(po_id) REFERENCES dbo.purchase_orders(id);
GO
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys fk JOIN sys.foreign_key_columns fkc ON fk.object_id=fkc.constraint_object_id WHERE fk.parent_object_id=OBJECT_ID(N'dbo.purchase_order_lines') AND COL_NAME(fkc.parent_object_id,fkc.parent_column_id)=N'item_id' AND fk.referenced_object_id=OBJECT_ID(N'dbo.items'))
    ALTER TABLE dbo.purchase_order_lines ADD CONSTRAINT FK_purchase_order_lines_item_v16 FOREIGN KEY(item_id) REFERENCES dbo.items(id);
GO
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys fk JOIN sys.foreign_key_columns fkc ON fk.object_id=fkc.constraint_object_id WHERE fk.parent_object_id=OBJECT_ID(N'dbo.purchase_order_lines') AND COL_NAME(fkc.parent_object_id,fkc.parent_column_id)=N'warehouse_id' AND fk.referenced_object_id=OBJECT_ID(N'dbo.warehouses'))
    ALTER TABLE dbo.purchase_order_lines ADD CONSTRAINT FK_purchase_order_lines_warehouse_v16 FOREIGN KEY(warehouse_id) REFERENCES dbo.warehouses(id);
GO
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys fk JOIN sys.foreign_key_columns fkc ON fk.object_id=fkc.constraint_object_id WHERE fk.parent_object_id=OBJECT_ID(N'dbo.purchase_order_lines') AND COL_NAME(fkc.parent_object_id,fkc.parent_column_id)=N'tax_code_id' AND fk.referenced_object_id=OBJECT_ID(N'dbo.tax_codes'))
    ALTER TABLE dbo.purchase_order_lines ADD CONSTRAINT FK_purchase_order_lines_tax_v16 FOREIGN KEY(tax_code_id) REFERENCES dbo.tax_codes(id);
GO
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys fk JOIN sys.foreign_key_columns fkc ON fk.object_id=fkc.constraint_object_id WHERE fk.parent_object_id=OBJECT_ID(N'dbo.purchase_order_lines') AND COL_NAME(fkc.parent_object_id,fkc.parent_column_id)=N'pr_line_id' AND fk.referenced_object_id=OBJECT_ID(N'dbo.purchase_requisition_lines'))
    ALTER TABLE dbo.purchase_order_lines ADD CONSTRAINT FK_purchase_order_lines_pr_line_v16 FOREIGN KEY(pr_line_id) REFERENCES dbo.purchase_requisition_lines(id);
GO

IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys fk JOIN sys.foreign_key_columns fkc ON fk.object_id=fkc.constraint_object_id WHERE fk.parent_object_id=OBJECT_ID(N'dbo.goods_receipts') AND COL_NAME(fkc.parent_object_id,fkc.parent_column_id)=N'po_id' AND fk.referenced_object_id=OBJECT_ID(N'dbo.purchase_orders'))
    ALTER TABLE dbo.goods_receipts ADD CONSTRAINT FK_goods_receipts_po_v16 FOREIGN KEY(po_id) REFERENCES dbo.purchase_orders(id);
GO
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys fk JOIN sys.foreign_key_columns fkc ON fk.object_id=fkc.constraint_object_id WHERE fk.parent_object_id=OBJECT_ID(N'dbo.goods_receipts') AND COL_NAME(fkc.parent_object_id,fkc.parent_column_id)=N'vendor_id' AND fk.referenced_object_id=OBJECT_ID(N'dbo.business_partners'))
    ALTER TABLE dbo.goods_receipts ADD CONSTRAINT FK_goods_receipts_vendor_v16 FOREIGN KEY(vendor_id) REFERENCES dbo.business_partners(id);
GO
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys fk JOIN sys.foreign_key_columns fkc ON fk.object_id=fkc.constraint_object_id WHERE fk.parent_object_id=OBJECT_ID(N'dbo.goods_receipts') AND COL_NAME(fkc.parent_object_id,fkc.parent_column_id)=N'created_by' AND fk.referenced_object_id=OBJECT_ID(N'dbo.users'))
    ALTER TABLE dbo.goods_receipts ADD CONSTRAINT FK_goods_receipts_created_by_v16 FOREIGN KEY(created_by) REFERENCES dbo.users(id);
GO
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys fk JOIN sys.foreign_key_columns fkc ON fk.object_id=fkc.constraint_object_id WHERE fk.parent_object_id=OBJECT_ID(N'dbo.goods_receipts') AND COL_NAME(fkc.parent_object_id,fkc.parent_column_id)=N'journal_entry_id' AND fk.referenced_object_id=OBJECT_ID(N'dbo.journal_entries'))
    ALTER TABLE dbo.goods_receipts ADD CONSTRAINT FK_goods_receipts_je_v16 FOREIGN KEY(journal_entry_id) REFERENCES dbo.journal_entries(id);
GO

IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys fk JOIN sys.foreign_key_columns fkc ON fk.object_id=fkc.constraint_object_id WHERE fk.parent_object_id=OBJECT_ID(N'dbo.goods_receipt_lines') AND COL_NAME(fkc.parent_object_id,fkc.parent_column_id)=N'gr_id' AND fk.referenced_object_id=OBJECT_ID(N'dbo.goods_receipts'))
    ALTER TABLE dbo.goods_receipt_lines ADD CONSTRAINT FK_goods_receipt_lines_gr_v16 FOREIGN KEY(gr_id) REFERENCES dbo.goods_receipts(id);
GO
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys fk JOIN sys.foreign_key_columns fkc ON fk.object_id=fkc.constraint_object_id WHERE fk.parent_object_id=OBJECT_ID(N'dbo.goods_receipt_lines') AND COL_NAME(fkc.parent_object_id,fkc.parent_column_id)=N'po_line_id' AND fk.referenced_object_id=OBJECT_ID(N'dbo.purchase_order_lines'))
    ALTER TABLE dbo.goods_receipt_lines ADD CONSTRAINT FK_goods_receipt_lines_po_line_v16 FOREIGN KEY(po_line_id) REFERENCES dbo.purchase_order_lines(id);
GO
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys fk JOIN sys.foreign_key_columns fkc ON fk.object_id=fkc.constraint_object_id WHERE fk.parent_object_id=OBJECT_ID(N'dbo.goods_receipt_lines') AND COL_NAME(fkc.parent_object_id,fkc.parent_column_id)=N'item_id' AND fk.referenced_object_id=OBJECT_ID(N'dbo.items'))
    ALTER TABLE dbo.goods_receipt_lines ADD CONSTRAINT FK_goods_receipt_lines_item_v16 FOREIGN KEY(item_id) REFERENCES dbo.items(id);
GO
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys fk JOIN sys.foreign_key_columns fkc ON fk.object_id=fkc.constraint_object_id WHERE fk.parent_object_id=OBJECT_ID(N'dbo.goods_receipt_lines') AND COL_NAME(fkc.parent_object_id,fkc.parent_column_id)=N'warehouse_id' AND fk.referenced_object_id=OBJECT_ID(N'dbo.warehouses'))
    ALTER TABLE dbo.goods_receipt_lines ADD CONSTRAINT FK_goods_receipt_lines_warehouse_v16 FOREIGN KEY(warehouse_id) REFERENCES dbo.warehouses(id);
GO

-- Re-add AP invoice to GR FK if cleanup removed it.
IF OBJECT_ID(N'dbo.ap_invoices', N'U') IS NOT NULL
AND COL_LENGTH(N'dbo.ap_invoices', N'gr_id') IS NOT NULL
AND NOT EXISTS (SELECT 1 FROM sys.foreign_keys fk JOIN sys.foreign_key_columns fkc ON fk.object_id=fkc.constraint_object_id WHERE fk.parent_object_id=OBJECT_ID(N'dbo.ap_invoices') AND COL_NAME(fkc.parent_object_id,fkc.parent_column_id)=N'gr_id' AND fk.referenced_object_id=OBJECT_ID(N'dbo.goods_receipts'))
    ALTER TABLE dbo.ap_invoices ADD CONSTRAINT FK_ap_invoices_gr_v16_repair FOREIGN KEY(gr_id) REFERENCES dbo.goods_receipts(id);
GO

/* ---------------------------------------------------------
   6) Vendor price history
--------------------------------------------------------- */
IF OBJECT_ID(N'dbo.vendor_price_history', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.vendor_price_history (
        id BIGINT IDENTITY(1,1) NOT NULL,
        vendor_id BIGINT NOT NULL,
        item_id BIGINT NOT NULL,
        source_doc_type NVARCHAR(50) NOT NULL,
        source_doc_id BIGINT NULL,
        doc_date DATE NOT NULL,
        unit_price DECIMAL(19,4) NOT NULL,
        currency_code NVARCHAR(10) NOT NULL CONSTRAINT DF_vendor_price_history_currency_v16 DEFAULT N'VND',
        created_at DATETIME2 NOT NULL CONSTRAINT DF_vendor_price_history_created_v16 DEFAULT SYSUTCDATETIME(),
        CONSTRAINT PK_vendor_price_history PRIMARY KEY(id)
    );
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys fk JOIN sys.foreign_key_columns fkc ON fk.object_id=fkc.constraint_object_id WHERE fk.parent_object_id=OBJECT_ID(N'dbo.vendor_price_history') AND COL_NAME(fkc.parent_object_id,fkc.parent_column_id)=N'vendor_id' AND fk.referenced_object_id=OBJECT_ID(N'dbo.business_partners'))
    ALTER TABLE dbo.vendor_price_history ADD CONSTRAINT FK_vendor_price_history_vendor_v16 FOREIGN KEY(vendor_id) REFERENCES dbo.business_partners(id);
GO
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys fk JOIN sys.foreign_key_columns fkc ON fk.object_id=fkc.constraint_object_id WHERE fk.parent_object_id=OBJECT_ID(N'dbo.vendor_price_history') AND COL_NAME(fkc.parent_object_id,fkc.parent_column_id)=N'item_id' AND fk.referenced_object_id=OBJECT_ID(N'dbo.items'))
    ALTER TABLE dbo.vendor_price_history ADD CONSTRAINT FK_vendor_price_history_item_v16 FOREIGN KEY(item_id) REFERENCES dbo.items(id);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.vendor_price_history') AND name = N'IX_vph_vendor_item_date')
    CREATE INDEX IX_vph_vendor_item_date ON dbo.vendor_price_history(vendor_id, item_id, doc_date DESC, id DESC);
GO

/* ---------------------------------------------------------
   7) FIFO inventory layers
--------------------------------------------------------- */
IF OBJECT_ID(N'dbo.inventory_layers', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.inventory_layers (
        id BIGINT IDENTITY(1,1) NOT NULL,
        item_id BIGINT NOT NULL,
        warehouse_id BIGINT NOT NULL,
        source_movement_id BIGINT NOT NULL,
        source_doc_type NVARCHAR(50) NULL,
        source_doc_id BIGINT NULL,
        layer_date DATE NOT NULL,
        quantity DECIMAL(19,4) NOT NULL,
        remaining_qty DECIMAL(19,4) NOT NULL,
        unit_cost DECIMAL(19,4) NOT NULL,
        amount DECIMAL(19,4) NOT NULL,
        created_at DATETIME2 NOT NULL CONSTRAINT DF_inventory_layers_created_v16 DEFAULT SYSUTCDATETIME(),
        CONSTRAINT PK_inventory_layers PRIMARY KEY(id)
    );
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys fk JOIN sys.foreign_key_columns fkc ON fk.object_id=fkc.constraint_object_id WHERE fk.parent_object_id=OBJECT_ID(N'dbo.inventory_layers') AND COL_NAME(fkc.parent_object_id,fkc.parent_column_id)=N'item_id' AND fk.referenced_object_id=OBJECT_ID(N'dbo.items'))
    ALTER TABLE dbo.inventory_layers ADD CONSTRAINT FK_inventory_layers_item_v16 FOREIGN KEY(item_id) REFERENCES dbo.items(id);
GO
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys fk JOIN sys.foreign_key_columns fkc ON fk.object_id=fkc.constraint_object_id WHERE fk.parent_object_id=OBJECT_ID(N'dbo.inventory_layers') AND COL_NAME(fkc.parent_object_id,fkc.parent_column_id)=N'warehouse_id' AND fk.referenced_object_id=OBJECT_ID(N'dbo.warehouses'))
    ALTER TABLE dbo.inventory_layers ADD CONSTRAINT FK_inventory_layers_warehouse_v16 FOREIGN KEY(warehouse_id) REFERENCES dbo.warehouses(id);
GO
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys fk JOIN sys.foreign_key_columns fkc ON fk.object_id=fkc.constraint_object_id WHERE fk.parent_object_id=OBJECT_ID(N'dbo.inventory_layers') AND COL_NAME(fkc.parent_object_id,fkc.parent_column_id)=N'source_movement_id' AND fk.referenced_object_id=OBJECT_ID(N'dbo.inventory_movements'))
    ALTER TABLE dbo.inventory_layers ADD CONSTRAINT FK_inventory_layers_movement_v16 FOREIGN KEY(source_movement_id) REFERENCES dbo.inventory_movements(id);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.inventory_layers') AND name = N'IX_layers_fifo')
    CREATE INDEX IX_layers_fifo ON dbo.inventory_layers(item_id, warehouse_id, remaining_qty, layer_date, id);
GO

IF OBJECT_ID(N'dbo.inventory_layer_consumptions', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.inventory_layer_consumptions (
        id BIGINT IDENTITY(1,1) NOT NULL,
        issue_movement_id BIGINT NOT NULL,
        layer_id BIGINT NOT NULL,
        quantity DECIMAL(19,4) NOT NULL,
        unit_cost DECIMAL(19,4) NOT NULL,
        amount DECIMAL(19,4) NOT NULL,
        created_at DATETIME2 NOT NULL CONSTRAINT DF_inventory_layer_consumptions_created_v16 DEFAULT SYSUTCDATETIME(),
        CONSTRAINT PK_inventory_layer_consumptions PRIMARY KEY(id)
    );
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys fk JOIN sys.foreign_key_columns fkc ON fk.object_id=fkc.constraint_object_id WHERE fk.parent_object_id=OBJECT_ID(N'dbo.inventory_layer_consumptions') AND COL_NAME(fkc.parent_object_id,fkc.parent_column_id)=N'issue_movement_id' AND fk.referenced_object_id=OBJECT_ID(N'dbo.inventory_movements'))
    ALTER TABLE dbo.inventory_layer_consumptions ADD CONSTRAINT FK_inventory_layer_consumptions_issue_movement_v16 FOREIGN KEY(issue_movement_id) REFERENCES dbo.inventory_movements(id);
GO
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys fk JOIN sys.foreign_key_columns fkc ON fk.object_id=fkc.constraint_object_id WHERE fk.parent_object_id=OBJECT_ID(N'dbo.inventory_layer_consumptions') AND COL_NAME(fkc.parent_object_id,fkc.parent_column_id)=N'layer_id' AND fk.referenced_object_id=OBJECT_ID(N'dbo.inventory_layers'))
    ALTER TABLE dbo.inventory_layer_consumptions ADD CONSTRAINT FK_inventory_layer_consumptions_layer_v16 FOREIGN KEY(layer_id) REFERENCES dbo.inventory_layers(id);
GO

/* Seed FIFO layers from existing inbound movements if no layers exist yet. */
IF OBJECT_ID(N'dbo.inventory_layers', N'U') IS NOT NULL
AND NOT EXISTS (SELECT 1 FROM dbo.inventory_layers)
BEGIN
    INSERT INTO dbo.inventory_layers(item_id, warehouse_id, source_movement_id, source_doc_type, source_doc_id, layer_date, quantity, remaining_qty, unit_cost, amount)
    SELECT item_id, warehouse_id, id, source_doc_type, source_doc_id, movement_date, qty_in, qty_in, unit_cost, qty_in * unit_cost
    FROM dbo.inventory_movements
    WHERE qty_in > 0;
END
GO

PRINT N'v16.1 purchasing migration completed successfully.';
GO
