/* =========================================================
   Migration 31
   Standard UoM Conversion Defaults
   =========================================================

   Purpose:
   - Add global/default UoM conversion ratios so common pairs do not need to be
     maintained manually for every item.
   - Item-specific conversions in dbo.item_unit_conversions still have priority.
   - Formula: 1 from_uom = rate_to_base to_uom.
     Example: 1 gram = 0.001 kg, 1 kg = 1000 gram.
   ========================================================= */

USE [MiniERPFNB];
GO

PRINT N'Start migration 31 - Standard UoM conversion defaults';
GO

IF OBJECT_ID(N'dbo.unit_of_measures', N'U') IS NULL
BEGIN
    PRINT N'dbo.unit_of_measures not found. Please run migration 29 first.';
END
GO

IF OBJECT_ID(N'dbo.uom_standard_conversions', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.uom_standard_conversions (
        id BIGINT IDENTITY(1,1) CONSTRAINT PK_uom_standard_conversions PRIMARY KEY,
        from_uom NVARCHAR(30) NOT NULL,
        to_uom NVARCHAR(30) NOT NULL,
        rate_to_base DECIMAL(19,9) NOT NULL,
        unit_group NVARCHAR(30) NULL,
        is_active BIT NOT NULL CONSTRAINT DF_usc_active DEFAULT 1,
        note NVARCHAR(500) NULL,
        created_at DATETIME2 NOT NULL CONSTRAINT DF_usc_created DEFAULT SYSUTCDATETIME()
    );
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.uom_standard_conversions') AND name = N'IX_usc_from_to')
    CREATE INDEX IX_usc_from_to ON dbo.uom_standard_conversions(from_uom, to_uom, is_active);
GO

/* Ensure useful unit codes exist in UoM Master if migration 29 is present. */
IF OBJECT_ID(N'dbo.unit_of_measures', N'U') IS NOT NULL
BEGIN
    DECLARE @uom_seed TABLE(unit_code NVARCHAR(30), unit_name NVARCHAR(100), unit_group NVARCHAR(30), decimal_places INT, description NVARCHAR(500));
    INSERT INTO @uom_seed(unit_code, unit_name, unit_group, decimal_places, description)
    VALUES
    (N'g', N'Gram', N'MASS', 4, N'Alias for gram'),
    (N'gram', N'Gram', N'MASS', 4, N'Gram'),
    (N'kg', N'Kilogram', N'MASS', 4, N'Kilogram'),
    (N'ml', N'Milliliter', N'VOLUME', 4, N'Milliliter'),
    (N'l', N'Liter', N'VOLUME', 4, N'Alias for liter'),
    (N'liter', N'Liter', N'VOLUME', 4, N'Liter'),
    (N'cm', N'Centimeter', N'LENGTH', 4, N'Centimeter'),
    (N'm', N'Meter', N'LENGTH', 4, N'Meter');

    INSERT INTO dbo.unit_of_measures(unit_code, unit_name, unit_group, decimal_places, description, is_active)
    SELECT s.unit_code, s.unit_name, s.unit_group, s.decimal_places, s.description, 1
    FROM @uom_seed s
    WHERE NOT EXISTS (SELECT 1 FROM dbo.unit_of_measures u WHERE LOWER(u.unit_code) = LOWER(s.unit_code));
END
GO

DECLARE @conv TABLE(from_uom NVARCHAR(30), to_uom NVARCHAR(30), rate_to_base DECIMAL(19,9), unit_group NVARCHAR(30), note NVARCHAR(500));
INSERT INTO @conv(from_uom, to_uom, rate_to_base, unit_group, note)
VALUES
/* Mass */
(N'gram', N'kg', 0.001, N'MASS', N'1 gram = 0.001 kg'),
(N'g', N'kg', 0.001, N'MASS', N'1 g = 0.001 kg'),
(N'kg', N'gram', 1000, N'MASS', N'1 kg = 1000 gram'),
(N'kg', N'g', 1000, N'MASS', N'1 kg = 1000 g'),
/* Volume */
(N'ml', N'liter', 0.001, N'VOLUME', N'1 ml = 0.001 liter'),
(N'ml', N'l', 0.001, N'VOLUME', N'1 ml = 0.001 l'),
(N'liter', N'ml', 1000, N'VOLUME', N'1 liter = 1000 ml'),
(N'l', N'ml', 1000, N'VOLUME', N'1 l = 1000 ml'),
/* Length */
(N'cm', N'm', 0.01, N'LENGTH', N'1 cm = 0.01 m'),
(N'm', N'cm', 100, N'LENGTH', N'1 m = 100 cm');

INSERT INTO dbo.uom_standard_conversions(from_uom, to_uom, rate_to_base, unit_group, is_active, note)
SELECT c.from_uom, c.to_uom, c.rate_to_base, c.unit_group, 1, c.note
FROM @conv c
WHERE NOT EXISTS (
    SELECT 1
    FROM dbo.uom_standard_conversions x
    WHERE LOWER(x.from_uom) = LOWER(c.from_uom)
      AND LOWER(x.to_uom) = LOWER(c.to_uom)
);
GO

PRINT N'Migration 31 completed successfully.';
GO
