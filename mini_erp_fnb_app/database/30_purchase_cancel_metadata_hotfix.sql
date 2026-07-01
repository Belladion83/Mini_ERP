/* =========================================================
   Migration 30 / v70 hotfix
   Purchasing cancel metadata columns

   Purpose:
   - Fix SQL Server error 207: Invalid column name 'cancelled_by' / 'cancelled_at'
     when cancelling PR/PO/GR on databases that did not run migration 26 completely.
   - Safe to run multiple times.
   - Does not delete or reset business data.
   ========================================================= */

PRINT N'Start migration 30 - purchasing cancel metadata hotfix';
GO

/* Purchase Requisition cancel metadata */
IF OBJECT_ID(N'dbo.purchase_requisitions', N'U') IS NOT NULL
   AND COL_LENGTH(N'dbo.purchase_requisitions', N'cancelled_by') IS NULL
BEGIN
    ALTER TABLE dbo.purchase_requisitions ADD cancelled_by BIGINT NULL;
END
GO

IF OBJECT_ID(N'dbo.purchase_requisitions', N'U') IS NOT NULL
   AND COL_LENGTH(N'dbo.purchase_requisitions', N'cancelled_at') IS NULL
BEGIN
    ALTER TABLE dbo.purchase_requisitions ADD cancelled_at DATETIME2 NULL;
END
GO

IF OBJECT_ID(N'dbo.purchase_requisitions', N'U') IS NOT NULL
   AND COL_LENGTH(N'dbo.purchase_requisitions', N'cancel_reason') IS NULL
BEGIN
    ALTER TABLE dbo.purchase_requisitions ADD cancel_reason NVARCHAR(500) NULL;
END
GO

/* Purchase Order cancel metadata */
IF OBJECT_ID(N'dbo.purchase_orders', N'U') IS NOT NULL
   AND COL_LENGTH(N'dbo.purchase_orders', N'cancelled_by') IS NULL
BEGIN
    ALTER TABLE dbo.purchase_orders ADD cancelled_by BIGINT NULL;
END
GO

IF OBJECT_ID(N'dbo.purchase_orders', N'U') IS NOT NULL
   AND COL_LENGTH(N'dbo.purchase_orders', N'cancelled_at') IS NULL
BEGIN
    ALTER TABLE dbo.purchase_orders ADD cancelled_at DATETIME2 NULL;
END
GO

IF OBJECT_ID(N'dbo.purchase_orders', N'U') IS NOT NULL
   AND COL_LENGTH(N'dbo.purchase_orders', N'cancel_reason') IS NULL
BEGIN
    ALTER TABLE dbo.purchase_orders ADD cancel_reason NVARCHAR(500) NULL;
END
GO

/* Goods Receipt cancel metadata */
IF OBJECT_ID(N'dbo.goods_receipts', N'U') IS NOT NULL
   AND COL_LENGTH(N'dbo.goods_receipts', N'cancelled_by') IS NULL
BEGIN
    ALTER TABLE dbo.goods_receipts ADD cancelled_by BIGINT NULL;
END
GO

IF OBJECT_ID(N'dbo.goods_receipts', N'U') IS NOT NULL
   AND COL_LENGTH(N'dbo.goods_receipts', N'cancelled_at') IS NULL
BEGIN
    ALTER TABLE dbo.goods_receipts ADD cancelled_at DATETIME2 NULL;
END
GO

IF OBJECT_ID(N'dbo.goods_receipts', N'U') IS NOT NULL
   AND COL_LENGTH(N'dbo.goods_receipts', N'cancel_reason') IS NULL
BEGIN
    ALTER TABLE dbo.goods_receipts ADD cancel_reason NVARCHAR(500) NULL;
END
GO

/* Optional FK constraints to users(id), guarded by parent column to avoid duplicates */
IF OBJECT_ID(N'dbo.users', N'U') IS NOT NULL
   AND COL_LENGTH(N'dbo.purchase_requisitions', N'cancelled_by') IS NOT NULL
   AND NOT EXISTS (
        SELECT 1
        FROM sys.foreign_keys fk
        JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
        WHERE fk.parent_object_id = OBJECT_ID(N'dbo.purchase_requisitions')
          AND COL_NAME(fkc.parent_object_id, fkc.parent_column_id) = N'cancelled_by'
          AND fk.referenced_object_id = OBJECT_ID(N'dbo.users')
   )
BEGIN
    ALTER TABLE dbo.purchase_requisitions
    ADD CONSTRAINT FK_purchase_requisitions_cancelled_by_v70
    FOREIGN KEY(cancelled_by) REFERENCES dbo.users(id);
END
GO

IF OBJECT_ID(N'dbo.users', N'U') IS NOT NULL
   AND COL_LENGTH(N'dbo.purchase_orders', N'cancelled_by') IS NOT NULL
   AND NOT EXISTS (
        SELECT 1
        FROM sys.foreign_keys fk
        JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
        WHERE fk.parent_object_id = OBJECT_ID(N'dbo.purchase_orders')
          AND COL_NAME(fkc.parent_object_id, fkc.parent_column_id) = N'cancelled_by'
          AND fk.referenced_object_id = OBJECT_ID(N'dbo.users')
   )
BEGIN
    ALTER TABLE dbo.purchase_orders
    ADD CONSTRAINT FK_purchase_orders_cancelled_by_v70
    FOREIGN KEY(cancelled_by) REFERENCES dbo.users(id);
END
GO

IF OBJECT_ID(N'dbo.users', N'U') IS NOT NULL
   AND COL_LENGTH(N'dbo.goods_receipts', N'cancelled_by') IS NOT NULL
   AND NOT EXISTS (
        SELECT 1
        FROM sys.foreign_keys fk
        JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
        WHERE fk.parent_object_id = OBJECT_ID(N'dbo.goods_receipts')
          AND COL_NAME(fkc.parent_object_id, fkc.parent_column_id) = N'cancelled_by'
          AND fk.referenced_object_id = OBJECT_ID(N'dbo.users')
   )
BEGIN
    ALTER TABLE dbo.goods_receipts
    ADD CONSTRAINT FK_goods_receipts_cancelled_by_v70
    FOREIGN KEY(cancelled_by) REFERENCES dbo.users(id);
END
GO

PRINT N'Migration 30 completed successfully.';
GO
