USE MiniERPFNB;
GO

/* =========================================================
   v21 - Purchasing multi-line PR/PO + Goods-in-transit 1519
   Safe migration: adds/ensures account 1519 and keeps old 151/159 data.
   ========================================================= */

IF NOT EXISTS (SELECT 1 FROM dbo.chart_accounts WHERE account_code = N'1519')
BEGIN
    INSERT INTO dbo.chart_accounts(account_code, account_name, account_type, account_group, normal_balance, coa_node_id, is_open_item, open_item_type, posting_allowed, is_active)
    SELECT N'1519', N'Hàng mua đang đi đường / GR clearing', N'ASSET', N'INVENTORY_IN_TRANSIT', N'DEBIT',
           (SELECT TOP 1 id FROM dbo.coa_nodes WHERE node_code = N'BS-ASSET'),
           0, N'NONE', 1, 1;
END
GO

UPDATE dbo.chart_accounts
SET account_name = N'Hàng mua đang đi đường / GR clearing',
    account_type = COALESCE(account_type, N'ASSET'),
    account_group = COALESCE(account_group, N'INVENTORY_IN_TRANSIT'),
    normal_balance = COALESCE(normal_balance, N'DEBIT'),
    posting_allowed = 1,
    is_active = 1
WHERE account_code = N'1519';
GO

IF OBJECT_ID(N'dbo.purchase_requisition_lines', N'U') IS NOT NULL
BEGIN
    IF COL_LENGTH(N'dbo.purchase_requisition_lines', N'line_no') IS NULL
        ALTER TABLE dbo.purchase_requisition_lines ADD line_no INT NULL;
END
GO

IF OBJECT_ID(N'dbo.purchase_order_lines', N'U') IS NOT NULL
BEGIN
    IF COL_LENGTH(N'dbo.purchase_order_lines', N'line_no') IS NULL
        ALTER TABLE dbo.purchase_order_lines ADD line_no INT NULL;
    IF COL_LENGTH(N'dbo.purchase_order_lines', N'received_qty') IS NULL
        ALTER TABLE dbo.purchase_order_lines ADD received_qty DECIMAL(19,4) NOT NULL CONSTRAINT DF_purchase_order_lines_received_qty_v21 DEFAULT 0;
END
GO

PRINT 'v21 purchasing multi-line / GIT 1519 migration completed.';
GO
