/*
V99 - Robust hotfix for optional Item Master Sales Price.

Reason:
- V98 allowed Sales Price to be blank in the application.
- Some existing SQL Server databases still have dbo.items.sales_price as NOT NULL.
- Some databases also have a default constraint bound to sales_price, so the column
  must be altered carefully.

Safe to run multiple times.
*/

IF OBJECT_ID(N'dbo.items', N'U') IS NOT NULL
   AND COL_LENGTH(N'dbo.items', N'sales_price') IS NOT NULL
BEGIN
    DECLARE @constraint_name sysname;

    SELECT @constraint_name = dc.name
    FROM sys.default_constraints dc
    INNER JOIN sys.columns c ON c.default_object_id = dc.object_id
    INNER JOIN sys.tables t ON t.object_id = c.object_id
    INNER JOIN sys.schemas s ON s.schema_id = t.schema_id
    WHERE s.name = N'dbo'
      AND t.name = N'items'
      AND c.name = N'sales_price';

    IF @constraint_name IS NOT NULL
    BEGIN
        DECLARE @drop_sql nvarchar(max);
        SET @drop_sql = N'ALTER TABLE dbo.items DROP CONSTRAINT ' + QUOTENAME(@constraint_name);
        EXEC sp_executesql @drop_sql;
    END;

    ALTER TABLE dbo.items ALTER COLUMN sales_price DECIMAL(19,4) NULL;

    IF NOT EXISTS (
        SELECT 1
        FROM sys.default_constraints dc
        INNER JOIN sys.columns c ON c.default_object_id = dc.object_id
        INNER JOIN sys.tables t ON t.object_id = c.object_id
        INNER JOIN sys.schemas s ON s.schema_id = t.schema_id
        WHERE s.name = N'dbo'
          AND t.name = N'items'
          AND c.name = N'sales_price'
    )
    BEGIN
        ALTER TABLE dbo.items ADD CONSTRAINT DF_item_sales_price DEFAULT 0 FOR sales_price;
    END;
END;
GO
