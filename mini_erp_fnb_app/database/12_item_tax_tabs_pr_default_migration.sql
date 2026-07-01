/* =========================================================
   v18 - Item Master SAP-style tabs + Tax Code Type + PR default Input Tax
   Safe/idempotent migration. Run this once after updating source files.

   Adds:
   - dbo.tax_codes.tax_type: INPUT / OUTPUT
   - dbo.items.input_tax_code_id, dbo.items.output_tax_code_id
   - FK from items to tax_codes
   - Default existing demo items to VAT10 where appropriate
========================================================= */

/* 1. Tax Code classification */
IF COL_LENGTH('dbo.tax_codes', 'tax_type') IS NULL
BEGIN
    ALTER TABLE dbo.tax_codes
    ADD tax_type NVARCHAR(20) NOT NULL CONSTRAINT DF_tax_codes_tax_type DEFAULT N'INPUT';
END;
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.check_constraints
    WHERE name = N'CK_tax_codes_tax_type'
      AND parent_object_id = OBJECT_ID(N'dbo.tax_codes')
)
BEGIN
    ALTER TABLE dbo.tax_codes
    ADD CONSTRAINT CK_tax_codes_tax_type CHECK (tax_type IN (N'INPUT', N'OUTPUT'));
END;
GO

UPDATE dbo.tax_codes
SET tax_type = CASE WHEN tax_type = N'OUTPUT' THEN N'OUTPUT' ELSE N'INPUT' END
WHERE tax_type IS NULL OR tax_type NOT IN (N'INPUT', N'OUTPUT');
GO

/* 2. Item Master default tax code fields */
IF COL_LENGTH('dbo.items', 'input_tax_code_id') IS NULL
BEGIN
    ALTER TABLE dbo.items ADD input_tax_code_id BIGINT NULL;
END;
GO

IF COL_LENGTH('dbo.items', 'output_tax_code_id') IS NULL
BEGIN
    ALTER TABLE dbo.items ADD output_tax_code_id BIGINT NULL;
END;
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.foreign_keys
    WHERE name = N'FK_items_input_tax_code'
      AND parent_object_id = OBJECT_ID(N'dbo.items')
)
BEGIN
    ALTER TABLE dbo.items
    ADD CONSTRAINT FK_items_input_tax_code FOREIGN KEY(input_tax_code_id) REFERENCES dbo.tax_codes(id);
END;
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.foreign_keys
    WHERE name = N'FK_items_output_tax_code'
      AND parent_object_id = OBJECT_ID(N'dbo.items')
)
BEGIN
    ALTER TABLE dbo.items
    ADD CONSTRAINT FK_items_output_tax_code FOREIGN KEY(output_tax_code_id) REFERENCES dbo.tax_codes(id);
END;
GO

/* 3. Backfill existing demo/master items with VAT10 where available.
      RAW/PACKAGING/RESALE/SERVICE are purchasable => INPUT tax default.
      FINISHED/RESALE/SERVICE are sellable => OUTPUT tax default. */
DECLARE @VAT10_IN BIGINT = (SELECT TOP 1 id FROM dbo.tax_codes WHERE tax_type = N'INPUT' AND rate = 10 ORDER BY CASE WHEN tax_code = N'VAT10_IN' THEN 0 ELSE 1 END, id);
DECLARE @VAT10_OUT BIGINT = (SELECT TOP 1 id FROM dbo.tax_codes WHERE tax_type = N'OUTPUT' AND rate = 10 ORDER BY CASE WHEN tax_code IN (N'VAT10_OUT', N'VAT10') THEN 0 ELSE 1 END, id);

IF @VAT10_IN IS NOT NULL
BEGIN
    UPDATE dbo.items
    SET input_tax_code_id = COALESCE(input_tax_code_id, @VAT10_IN)
    WHERE item_type IN (N'RAW', N'PACKAGING', N'RESALE', N'SERVICE');
END;

IF @VAT10_OUT IS NOT NULL
BEGIN
    UPDATE dbo.items
    SET output_tax_code_id = COALESCE(output_tax_code_id, @VAT10_OUT)
    WHERE item_type IN (N'FINISHED', N'RESALE', N'SERVICE');
END;
GO

PRINT 'v18 migration completed: Item default tax fields, Tax Code Type, PR default tax support.';
GO
