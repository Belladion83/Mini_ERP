/* =========================================================
   Migration 28
   Purchasing Base Unit / Order Unit / Unit Conversion
   ========================================================= */

USE [MiniERPFNB];
GO

PRINT N'Start migration 28 - Purchasing unit conversion';
GO

IF OBJECT_ID(N'dbo.items', N'U') IS NULL
    THROW 50028, 'Required table dbo.items does not exist. Please run this migration in the correct database.', 1;
IF OBJECT_ID(N'dbo.purchase_requisition_lines', N'U') IS NULL
    THROW 50028, 'Required table dbo.purchase_requisition_lines does not exist. Please run previous purchasing migrations first.', 1;
IF OBJECT_ID(N'dbo.purchase_order_lines', N'U') IS NULL
    THROW 50028, 'Required table dbo.purchase_order_lines does not exist. Please run previous purchasing migrations first.', 1;
IF OBJECT_ID(N'dbo.goods_receipt_lines', N'U') IS NULL
    THROW 50028, 'Required table dbo.goods_receipt_lines does not exist. Please run previous purchasing migrations first.', 1;
GO

/* Optional item-specific conversion master. 1 order unit = conversion_rate_to_base base units. */
IF OBJECT_ID(N'dbo.item_unit_conversions', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.item_unit_conversions (
        id BIGINT IDENTITY(1,1) CONSTRAINT PK_item_unit_conversions PRIMARY KEY,
        item_id BIGINT NOT NULL,
        base_uom NVARCHAR(30) NOT NULL,
        order_uom NVARCHAR(30) NOT NULL,
        conversion_rate_to_base DECIMAL(19,6) NOT NULL CONSTRAINT DF_iuc_rate DEFAULT 1,
        is_active BIT NOT NULL CONSTRAINT DF_iuc_active DEFAULT 1,
        note NVARCHAR(500) NULL,
        created_at DATETIME2 NOT NULL CONSTRAINT DF_iuc_created DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_iuc_item FOREIGN KEY(item_id) REFERENCES dbo.items(id)
    );
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.item_unit_conversions') AND name = N'IX_iuc_item_order_uom')
    CREATE INDEX IX_iuc_item_order_uom ON dbo.item_unit_conversions(item_id, order_uom, is_active);
GO

/* Purchase Requisition Lines */
IF COL_LENGTH('dbo.purchase_requisition_lines', 'base_uom') IS NULL
    ALTER TABLE dbo.purchase_requisition_lines ADD base_uom NVARCHAR(30) NULL;
GO
IF COL_LENGTH('dbo.purchase_requisition_lines', 'order_uom') IS NULL
    ALTER TABLE dbo.purchase_requisition_lines ADD order_uom NVARCHAR(30) NULL;
GO
IF COL_LENGTH('dbo.purchase_requisition_lines', 'order_to_base_rate') IS NULL
    ALTER TABLE dbo.purchase_requisition_lines ADD order_to_base_rate DECIMAL(19,6) NULL;
GO
IF COL_LENGTH('dbo.purchase_requisition_lines', 'base_quantity') IS NULL
    ALTER TABLE dbo.purchase_requisition_lines ADD base_quantity DECIMAL(19,4) NULL;
GO

UPDATE prl
SET base_uom = COALESCE(prl.base_uom, i.base_uom),
    order_uom = COALESCE(prl.order_uom, prl.base_uom, i.base_uom),
    order_to_base_rate = COALESCE(prl.order_to_base_rate, 1),
    base_quantity = COALESCE(prl.base_quantity, prl.quantity * COALESCE(prl.order_to_base_rate, 1))
FROM dbo.purchase_requisition_lines prl
JOIN dbo.items i ON i.id = prl.item_id;
GO

/* Purchase Order Lines */
IF COL_LENGTH('dbo.purchase_order_lines', 'base_uom') IS NULL
    ALTER TABLE dbo.purchase_order_lines ADD base_uom NVARCHAR(30) NULL;
GO
IF COL_LENGTH('dbo.purchase_order_lines', 'order_uom') IS NULL
    ALTER TABLE dbo.purchase_order_lines ADD order_uom NVARCHAR(30) NULL;
GO
IF COL_LENGTH('dbo.purchase_order_lines', 'order_to_base_rate') IS NULL
    ALTER TABLE dbo.purchase_order_lines ADD order_to_base_rate DECIMAL(19,6) NULL;
GO
IF COL_LENGTH('dbo.purchase_order_lines', 'base_quantity') IS NULL
    ALTER TABLE dbo.purchase_order_lines ADD base_quantity DECIMAL(19,4) NULL;
GO
IF COL_LENGTH('dbo.purchase_order_lines', 'base_received_qty') IS NULL
    ALTER TABLE dbo.purchase_order_lines ADD base_received_qty DECIMAL(19,4) NULL;
GO

UPDATE pol
SET base_uom = COALESCE(pol.base_uom, i.base_uom),
    order_uom = COALESCE(pol.order_uom, pol.base_uom, i.base_uom),
    order_to_base_rate = COALESCE(pol.order_to_base_rate, 1),
    base_quantity = COALESCE(pol.base_quantity, pol.quantity * COALESCE(pol.order_to_base_rate, 1)),
    base_received_qty = COALESCE(pol.base_received_qty, pol.received_qty * COALESCE(pol.order_to_base_rate, 1))
FROM dbo.purchase_order_lines pol
JOIN dbo.items i ON i.id = pol.item_id;
GO

/* Goods Receipt Lines */
IF COL_LENGTH('dbo.goods_receipt_lines', 'base_uom') IS NULL
    ALTER TABLE dbo.goods_receipt_lines ADD base_uom NVARCHAR(30) NULL;
GO
IF COL_LENGTH('dbo.goods_receipt_lines', 'order_uom') IS NULL
    ALTER TABLE dbo.goods_receipt_lines ADD order_uom NVARCHAR(30) NULL;
GO
IF COL_LENGTH('dbo.goods_receipt_lines', 'order_to_base_rate') IS NULL
    ALTER TABLE dbo.goods_receipt_lines ADD order_to_base_rate DECIMAL(19,6) NULL;
GO
IF COL_LENGTH('dbo.goods_receipt_lines', 'order_qty') IS NULL
    ALTER TABLE dbo.goods_receipt_lines ADD order_qty DECIMAL(19,4) NULL;
GO
IF COL_LENGTH('dbo.goods_receipt_lines', 'order_unit_cost') IS NULL
    ALTER TABLE dbo.goods_receipt_lines ADD order_unit_cost DECIMAL(19,4) NULL;
GO

UPDATE grl
SET base_uom = COALESCE(grl.base_uom, i.base_uom),
    order_uom = COALESCE(grl.order_uom, grl.base_uom, i.base_uom),
    order_to_base_rate = COALESCE(grl.order_to_base_rate, 1),
    order_qty = COALESCE(grl.order_qty, grl.quantity),
    order_unit_cost = COALESCE(grl.order_unit_cost, grl.unit_cost)
FROM dbo.goods_receipt_lines grl
JOIN dbo.items i ON i.id = grl.item_id;
GO

/* Seed 1:1 conversions for current items. */
INSERT INTO dbo.item_unit_conversions(item_id, base_uom, order_uom, conversion_rate_to_base, is_active, note)
SELECT i.id, i.base_uom, i.base_uom, 1, 1, N'Default 1:1 conversion'
FROM dbo.items i
WHERE i.base_uom IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM dbo.item_unit_conversions c
      WHERE c.item_id = i.id AND c.order_uom = i.base_uom
  );
GO

PRINT N'Migration 28 completed successfully.';
GO
