/* =========================================================
   Migration 19 - Item Master Purchasing/Sales Defaults
   v19.1 FIX: avoids SQL Server same-batch "Invalid column name"
   issue by using dynamic SQL after ALTER TABLE ADD COLUMN.

   Adds:
   - items.estimate_receive_days: default Required Date on PR
   - items.delivery_days: default delivery days for FINISHED items
   - items.can_be_sold: standard sale control for FINISHED items
   - dbo.item_sale_channels: one/many allowed sale channels per sellable item

   Safe to run multiple times.
========================================================= */

SET NOCOUNT ON;

/* 1. Add Item Master columns. */
IF COL_LENGTH(N'dbo.items', N'estimate_receive_days') IS NULL
BEGIN
    ALTER TABLE dbo.items ADD estimate_receive_days INT NULL;
END;

IF COL_LENGTH(N'dbo.items', N'delivery_days') IS NULL
BEGIN
    ALTER TABLE dbo.items ADD delivery_days INT NULL;
END;

IF COL_LENGTH(N'dbo.items', N'can_be_sold') IS NULL
BEGIN
    ALTER TABLE dbo.items ADD can_be_sold BIT NULL;
END;

/* 2. Normalize existing data.
      Dynamic SQL is required because SQL Server compiles a whole batch before
      the ALTER TABLE columns are visible to later static statements. */
EXEC(N'
UPDATE dbo.items
SET estimate_receive_days = ISNULL(estimate_receive_days, 0),
    delivery_days = CASE WHEN item_type = N''FINISHED'' THEN ISNULL(delivery_days, 0) ELSE 0 END,
    can_be_sold = CASE WHEN item_type = N''FINISHED'' THEN ISNULL(can_be_sold, 1) ELSE 0 END;
');

/* 3. Default constraints, created only if missing on each column. */
IF NOT EXISTS (
    SELECT 1
    FROM sys.default_constraints dc
    WHERE dc.parent_object_id = OBJECT_ID(N'dbo.items')
      AND dc.parent_column_id = COLUMNPROPERTY(OBJECT_ID(N'dbo.items'), N'estimate_receive_days', 'ColumnId')
)
BEGIN
    EXEC(N'ALTER TABLE dbo.items ADD CONSTRAINT DF_items_estimate_receive_days DEFAULT 0 FOR estimate_receive_days;');
END;

IF NOT EXISTS (
    SELECT 1
    FROM sys.default_constraints dc
    WHERE dc.parent_object_id = OBJECT_ID(N'dbo.items')
      AND dc.parent_column_id = COLUMNPROPERTY(OBJECT_ID(N'dbo.items'), N'delivery_days', 'ColumnId')
)
BEGIN
    EXEC(N'ALTER TABLE dbo.items ADD CONSTRAINT DF_items_delivery_days DEFAULT 0 FOR delivery_days;');
END;

IF NOT EXISTS (
    SELECT 1
    FROM sys.default_constraints dc
    WHERE dc.parent_object_id = OBJECT_ID(N'dbo.items')
      AND dc.parent_column_id = COLUMNPROPERTY(OBJECT_ID(N'dbo.items'), N'can_be_sold', 'ColumnId')
)
BEGIN
    EXEC(N'ALTER TABLE dbo.items ADD CONSTRAINT DF_items_can_be_sold DEFAULT 0 FOR can_be_sold;');
END;

/* 4. Check constraints for non-negative day fields. */
IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = N'CK_items_estimate_receive_days_nonnegative')
BEGIN
    EXEC(N'ALTER TABLE dbo.items ADD CONSTRAINT CK_items_estimate_receive_days_nonnegative CHECK (estimate_receive_days >= 0);');
END;

IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = N'CK_items_delivery_days_nonnegative')
BEGIN
    EXEC(N'ALTER TABLE dbo.items ADD CONSTRAINT CK_items_delivery_days_nonnegative CHECK (delivery_days >= 0);');
END;

/* 5. Mapping table: item -> allowed sale channels. */
IF OBJECT_ID(N'dbo.item_sale_channels', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.item_sale_channels (
        id BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_item_sale_channels PRIMARY KEY,
        item_id BIGINT NOT NULL,
        sale_channel_id BIGINT NOT NULL,
        created_at DATETIME2 NOT NULL CONSTRAINT DF_item_sale_channels_created_at DEFAULT SYSUTCDATETIME(),
        CONSTRAINT UQ_item_sale_channels UNIQUE(item_id, sale_channel_id),
        CONSTRAINT FK_item_sale_channels_item FOREIGN KEY(item_id) REFERENCES dbo.items(id),
        CONSTRAINT FK_item_sale_channels_sale_channel FOREIGN KEY(sale_channel_id) REFERENCES dbo.sale_channels(id)
    );
END;

/* 6. For existing sellable FINISHED items, open all active sale channels when no specific channel exists yet. */
EXEC(N'
INSERT INTO dbo.item_sale_channels(item_id, sale_channel_id)
SELECT i.id, sc.id
FROM dbo.items i
CROSS JOIN dbo.sale_channels sc
WHERE i.item_type = N''FINISHED''
  AND ISNULL(i.can_be_sold, 0) = 1
  AND i.is_active = 1
  AND sc.is_active = 1
  AND NOT EXISTS (
      SELECT 1 FROM dbo.item_sale_channels x
      WHERE x.item_id = i.id
  )
  AND NOT EXISTS (
      SELECT 1 FROM dbo.item_sale_channels x
      WHERE x.item_id = i.id AND x.sale_channel_id = sc.id
  );
');

/* 7. Non-FINISHED items must not remain opened for standard sales. */
EXEC(N'
DELETE isc
FROM dbo.item_sale_channels isc
JOIN dbo.items i ON i.id = isc.item_id
WHERE i.item_type <> N''FINISHED''
   OR ISNULL(i.can_be_sold, 0) = 0;
');

PRINT 'Migration 19 completed: Item Master purchasing/sales defaults and sale channel mapping are ready.';
