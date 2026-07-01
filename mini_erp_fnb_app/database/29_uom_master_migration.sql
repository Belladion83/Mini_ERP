/* =========================================================
   Migration 29
   Unit of Measure Master
   ========================================================= */

USE [MiniERPFNB];
GO

PRINT N'Start migration 29 - Unit of Measure Master';
GO

IF OBJECT_ID(N'dbo.items', N'U') IS NULL
BEGIN
    THROW 51029, 'Missing prerequisite table dbo.items. Please run this migration in the MiniERPFNB database.', 1;
END
GO

IF OBJECT_ID(N'dbo.unit_of_measures', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.unit_of_measures (
        id BIGINT IDENTITY(1,1) CONSTRAINT PK_unit_of_measures PRIMARY KEY,
        unit_code NVARCHAR(30) NOT NULL,
        unit_name NVARCHAR(100) NOT NULL,
        unit_group NVARCHAR(30) NOT NULL CONSTRAINT DF_uom_group DEFAULT N'COUNT',
        decimal_places INT NOT NULL CONSTRAINT DF_uom_decimals DEFAULT 4,
        description NVARCHAR(500) NULL,
        is_active BIT NOT NULL CONSTRAINT DF_uom_active DEFAULT 1,
        created_at DATETIME2 NOT NULL CONSTRAINT DF_uom_created DEFAULT SYSUTCDATETIME()
    );
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.unit_of_measures') AND name = N'UQ_unit_of_measures_code')
BEGIN
    CREATE UNIQUE INDEX UQ_unit_of_measures_code ON dbo.unit_of_measures(unit_code);
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = N'CK_uom_group')
BEGIN
    ALTER TABLE dbo.unit_of_measures
    ADD CONSTRAINT CK_uom_group CHECK (unit_group IN (N'COUNT', N'MASS', N'VOLUME', N'LENGTH', N'AREA', N'TIME', N'SERVICE', N'OTHER'));
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = N'CK_uom_decimal_places')
BEGIN
    ALTER TABLE dbo.unit_of_measures
    ADD CONSTRAINT CK_uom_decimal_places CHECK (decimal_places BETWEEN 0 AND 6);
END
GO

/* Seed common F&B units. */
DECLARE @seed TABLE(unit_code NVARCHAR(30), unit_name NVARCHAR(100), unit_group NVARCHAR(30), decimal_places INT, description NVARCHAR(500));
INSERT INTO @seed(unit_code, unit_name, unit_group, decimal_places, description)
VALUES
(N'piece', N'Piece', N'COUNT', 0, N'Đơn vị đếm'),
(N'box', N'Box', N'COUNT', 0, N'Hộp'),
(N'carton', N'Carton', N'COUNT', 0, N'Thùng carton'),
(N'bottle', N'Bottle', N'COUNT', 0, N'Chai'),
(N'can', N'Can', N'COUNT', 0, N'Lon'),
(N'pack', N'Pack', N'COUNT', 0, N'Gói'),
(N'bag', N'Bag', N'COUNT', 0, N'Bao/túi'),
(N'gram', N'Gram', N'MASS', 4, N'Gram'),
(N'kg', N'Kilogram', N'MASS', 4, N'Kilogram'),
(N'ml', N'Milliliter', N'VOLUME', 4, N'Milliliter'),
(N'liter', N'Liter', N'VOLUME', 4, N'Liter'),
(N'hour', N'Hour', N'TIME', 2, N'Giờ'),
(N'service', N'Service', N'SERVICE', 0, N'Dịch vụ');

INSERT INTO dbo.unit_of_measures(unit_code, unit_name, unit_group, decimal_places, description, is_active)
SELECT s.unit_code, s.unit_name, s.unit_group, s.decimal_places, s.description, 1
FROM @seed s
WHERE NOT EXISTS (SELECT 1 FROM dbo.unit_of_measures u WHERE LOWER(u.unit_code) = LOWER(s.unit_code));
GO

/* Seed from existing Item Master data so current data remains selectable. */
INSERT INTO dbo.unit_of_measures(unit_code, unit_name, unit_group, decimal_places, description, is_active)
SELECT DISTINCT src.unit_code, src.unit_code, N'OTHER', 4, N'Seeded from existing Item Master data', 1
FROM (
    SELECT LTRIM(RTRIM(base_uom)) AS unit_code FROM dbo.items WHERE ISNULL(base_uom, N'') <> N''
    UNION
    SELECT LTRIM(RTRIM(purchase_uom)) AS unit_code FROM dbo.items WHERE ISNULL(purchase_uom, N'') <> N''
    UNION
    SELECT LTRIM(RTRIM(sales_uom)) AS unit_code FROM dbo.items WHERE ISNULL(sales_uom, N'') <> N''
) src
WHERE src.unit_code IS NOT NULL
  AND src.unit_code <> N''
  AND NOT EXISTS (SELECT 1 FROM dbo.unit_of_measures u WHERE LOWER(u.unit_code) = LOWER(src.unit_code));
GO

/* Seed from existing item_unit_conversions only if migration 28 table exists. */
IF OBJECT_ID(N'dbo.item_unit_conversions', N'U') IS NOT NULL
BEGIN
    INSERT INTO dbo.unit_of_measures(unit_code, unit_name, unit_group, decimal_places, description, is_active)
    SELECT DISTINCT LTRIM(RTRIM(c.order_uom)), LTRIM(RTRIM(c.order_uom)), N'OTHER', 4, N'Seeded from Item Unit Conversion data', 1
    FROM dbo.item_unit_conversions c
    WHERE ISNULL(c.order_uom, N'') <> N''
      AND NOT EXISTS (SELECT 1 FROM dbo.unit_of_measures u WHERE LOWER(u.unit_code) = LOWER(LTRIM(RTRIM(c.order_uom))));
END
GO

PRINT N'Migration 29 completed successfully.';
GO
