/* =========================================================
   Migration 26
   Inventory valuation policy + cancel/reversal framework
   ========================================================= */

PRINT N'Start migration 26 - inventory valuation & cancel/reversal framework';
GO

/* 1) Inventory valuation policy per fiscal year */
IF OBJECT_ID(N'dbo.inventory_valuation_policies', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.inventory_valuation_policies (
        id BIGINT IDENTITY(1,1) CONSTRAINT PK_inventory_valuation_policies PRIMARY KEY,
        fiscal_year INT NOT NULL,
        valuation_method NVARCHAR(30) NOT NULL,
        effective_from DATE NOT NULL,
        note NVARCHAR(500) NULL,
        is_active BIT NOT NULL CONSTRAINT DF_inventory_valuation_policy_active DEFAULT 1,
        created_by BIGINT NULL,
        created_at DATETIME2 NOT NULL CONSTRAINT DF_inventory_valuation_policy_created DEFAULT SYSUTCDATETIME()
    );
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = N'FK_inventory_valuation_policy_user')
AND EXISTS (SELECT 1 FROM sys.tables WHERE name = 'users' AND schema_id = SCHEMA_ID('dbo'))
BEGIN
    ALTER TABLE dbo.inventory_valuation_policies
    ADD CONSTRAINT FK_inventory_valuation_policy_user FOREIGN KEY(created_by) REFERENCES dbo.users(id);
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = N'CK_inventory_valuation_method')
BEGIN
    ALTER TABLE dbo.inventory_valuation_policies
    ADD CONSTRAINT CK_inventory_valuation_method CHECK (valuation_method IN (N'FIFO', N'LIFO', N'WEIGHTED_AVG'));
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.inventory_valuation_policies') AND name = N'IX_inventory_valuation_policy_year')
BEGIN
    CREATE INDEX IX_inventory_valuation_policy_year ON dbo.inventory_valuation_policies(fiscal_year DESC, effective_from DESC);
END
GO

IF NOT EXISTS (SELECT 1 FROM dbo.inventory_valuation_policies)
BEGIN
    INSERT INTO dbo.inventory_valuation_policies(fiscal_year, valuation_method, effective_from, note, is_active)
    VALUES (YEAR(GETDATE()), N'FIFO', DATEFROMPARTS(YEAR(GETDATE()), 1, 1), N'Default seeded policy', 1);
END
GO

/* 2) Cancel metadata on purchasing documents */
IF COL_LENGTH('dbo.purchase_requisitions', 'cancelled_by') IS NULL
    ALTER TABLE dbo.purchase_requisitions ADD cancelled_by BIGINT NULL;
GO
IF COL_LENGTH('dbo.purchase_requisitions', 'cancelled_at') IS NULL
    ALTER TABLE dbo.purchase_requisitions ADD cancelled_at DATETIME2 NULL;
GO
IF COL_LENGTH('dbo.purchase_requisitions', 'cancel_reason') IS NULL
    ALTER TABLE dbo.purchase_requisitions ADD cancel_reason NVARCHAR(500) NULL;
GO
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = N'FK_pr_cancelled_by_user')
BEGIN
    ALTER TABLE dbo.purchase_requisitions ADD CONSTRAINT FK_pr_cancelled_by_user FOREIGN KEY(cancelled_by) REFERENCES dbo.users(id);
END
GO

IF COL_LENGTH('dbo.purchase_orders', 'cancelled_by') IS NULL
    ALTER TABLE dbo.purchase_orders ADD cancelled_by BIGINT NULL;
GO
IF COL_LENGTH('dbo.purchase_orders', 'cancelled_at') IS NULL
    ALTER TABLE dbo.purchase_orders ADD cancelled_at DATETIME2 NULL;
GO
IF COL_LENGTH('dbo.purchase_orders', 'cancel_reason') IS NULL
    ALTER TABLE dbo.purchase_orders ADD cancel_reason NVARCHAR(500) NULL;
GO
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = N'FK_po_cancelled_by_user')
BEGIN
    ALTER TABLE dbo.purchase_orders ADD CONSTRAINT FK_po_cancelled_by_user FOREIGN KEY(cancelled_by) REFERENCES dbo.users(id);
END
GO

IF COL_LENGTH('dbo.goods_receipts', 'cancelled_by') IS NULL
    ALTER TABLE dbo.goods_receipts ADD cancelled_by BIGINT NULL;
GO
IF COL_LENGTH('dbo.goods_receipts', 'cancelled_at') IS NULL
    ALTER TABLE dbo.goods_receipts ADD cancelled_at DATETIME2 NULL;
GO
IF COL_LENGTH('dbo.goods_receipts', 'cancel_reason') IS NULL
    ALTER TABLE dbo.goods_receipts ADD cancel_reason NVARCHAR(500) NULL;
GO
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = N'FK_gr_cancelled_by_user')
BEGIN
    ALTER TABLE dbo.goods_receipts ADD CONSTRAINT FK_gr_cancelled_by_user FOREIGN KEY(cancelled_by) REFERENCES dbo.users(id);
END
GO

/* 3) Reversal metadata on journal entries */
IF COL_LENGTH('dbo.journal_entries', 'reversal_of_journal_entry_id') IS NULL
    ALTER TABLE dbo.journal_entries ADD reversal_of_journal_entry_id BIGINT NULL;
GO
IF COL_LENGTH('dbo.journal_entries', 'reversed_at') IS NULL
    ALTER TABLE dbo.journal_entries ADD reversed_at DATETIME2 NULL;
GO
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = N'FK_je_reversal_of_je')
BEGIN
    ALTER TABLE dbo.journal_entries ADD CONSTRAINT FK_je_reversal_of_je FOREIGN KEY(reversal_of_journal_entry_id) REFERENCES dbo.journal_entries(id);
END
GO

PRINT N'Migration 26 completed successfully.';
GO
