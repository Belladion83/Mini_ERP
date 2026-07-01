/* =========================================================
   Migration 13 - Tax Code Single VAT Account - SAFE VERSION
   - SQL Server compiles a batch before running ALTER TABLE.
   - Therefore all statements that reference newly-added columns
     are executed via dynamic SQL.
   - Tax Type only supports: INPUT / OUTPUT.
   - Tax Code has one VAT Account field: vat_account_id.
   ========================================================= */

SET NOCOUNT ON;

IF OBJECT_ID(N'dbo.tax_codes', N'U') IS NULL
BEGIN
    RAISERROR('Table dbo.tax_codes does not exist. Please run previous schema/migrations first.', 16, 1);
    RETURN;
END;

IF OBJECT_ID(N'dbo.chart_accounts', N'U') IS NULL
BEGIN
    RAISERROR('Table dbo.chart_accounts does not exist. Please run previous schema/migrations first.', 16, 1);
    RETURN;
END;

DECLARE @InputVAT BIGINT = (SELECT TOP 1 id FROM dbo.chart_accounts WHERE account_code = N'1331' ORDER BY id);
DECLARE @OutputVAT BIGINT = (SELECT TOP 1 id FROM dbo.chart_accounts WHERE account_code = N'3331' ORDER BY id);

IF @InputVAT IS NULL
BEGIN
    RAISERROR('G/L account 1331 is required before running migration 13.', 16, 1);
    RETURN;
END;

IF @OutputVAT IS NULL
BEGIN
    RAISERROR('G/L account 3331 is required before running migration 13.', 16, 1);
    RETURN;
END;

/* 1. Add missing columns. Keep legacy columns for compatibility. */
IF COL_LENGTH(N'dbo.tax_codes', N'vat_account_id') IS NULL
BEGIN
    ALTER TABLE dbo.tax_codes ADD vat_account_id BIGINT NULL;
END;

IF COL_LENGTH(N'dbo.tax_codes', N'input_account_id') IS NULL
BEGIN
    ALTER TABLE dbo.tax_codes ADD input_account_id BIGINT NULL;
END;

IF COL_LENGTH(N'dbo.tax_codes', N'output_account_id') IS NULL
BEGIN
    ALTER TABLE dbo.tax_codes ADD output_account_id BIGINT NULL;
END;

/* 2. Create INPUT/OUTPUT tax codes and migrate data using dynamic SQL.
      Dynamic SQL is required because vat_account_id may have just been added. */
DECLARE @dyn NVARCHAR(MAX);

SET @dyn = N'
IF NOT EXISTS (SELECT 1 FROM dbo.tax_codes WHERE tax_code = N''VAT10_IN'')
BEGIN
    INSERT INTO dbo.tax_codes(tax_code, tax_name, tax_type, rate, vat_account_id, input_account_id, output_account_id, is_active)
    VALUES (N''VAT10_IN'', N''Input VAT 10%'', N''INPUT'', 10.0000, @InputVAT, @InputVAT, NULL, 1);
END;

IF NOT EXISTS (SELECT 1 FROM dbo.tax_codes WHERE tax_code = N''VAT0_IN'')
BEGIN
    INSERT INTO dbo.tax_codes(tax_code, tax_name, tax_type, rate, vat_account_id, input_account_id, output_account_id, is_active)
    VALUES (N''VAT0_IN'', N''Input VAT 0%'', N''INPUT'', 0.0000, @InputVAT, @InputVAT, NULL, 1);
END;

IF NOT EXISTS (SELECT 1 FROM dbo.tax_codes WHERE tax_code IN (N''VAT10'', N''VAT10_OUT'') AND tax_type = N''OUTPUT'')
   AND NOT EXISTS (SELECT 1 FROM dbo.tax_codes WHERE tax_code = N''VAT10_OUT'')
BEGIN
    INSERT INTO dbo.tax_codes(tax_code, tax_name, tax_type, rate, vat_account_id, input_account_id, output_account_id, is_active)
    VALUES (N''VAT10_OUT'', N''Output VAT 10%'', N''OUTPUT'', 10.0000, @OutputVAT, NULL, @OutputVAT, 1);
END;

IF NOT EXISTS (SELECT 1 FROM dbo.tax_codes WHERE tax_code IN (N''VAT0'', N''VAT0_OUT'') AND tax_type = N''OUTPUT'')
   AND NOT EXISTS (SELECT 1 FROM dbo.tax_codes WHERE tax_code = N''VAT0_OUT'')
BEGIN
    INSERT INTO dbo.tax_codes(tax_code, tax_name, tax_type, rate, vat_account_id, input_account_id, output_account_id, is_active)
    VALUES (N''VAT0_OUT'', N''Output VAT 0%'', N''OUTPUT'', 0.0000, @OutputVAT, NULL, @OutputVAT, 1);
END;

/* Fill single VAT account. Existing BOTH rows are treated as OUTPUT by default. */
UPDATE dbo.tax_codes
SET vat_account_id = COALESCE(
        vat_account_id,
        CASE WHEN tax_type = N''INPUT'' THEN input_account_id END,
        CASE WHEN tax_type = N''OUTPUT'' THEN output_account_id END,
        CASE WHEN tax_type = N''BOTH'' THEN output_account_id END,
        CASE WHEN tax_type = N''BOTH'' THEN input_account_id END,
        CASE WHEN tax_type = N''INPUT'' THEN @InputVAT ELSE @OutputVAT END
    );

/* Convert BOTH/invalid values to OUTPUT; only INPUT remains input. */
UPDATE dbo.tax_codes
SET tax_type = CASE WHEN tax_type = N''INPUT'' THEN N''INPUT'' ELSE N''OUTPUT'' END
WHERE tax_type IS NULL OR tax_type NOT IN (N''INPUT'', N''OUTPUT'');

/* Synchronize legacy columns. */
UPDATE dbo.tax_codes
SET input_account_id = CASE WHEN tax_type = N''INPUT'' THEN vat_account_id ELSE NULL END,
    output_account_id = CASE WHEN tax_type = N''OUTPUT'' THEN vat_account_id ELSE NULL END;
';

EXEC sp_executesql @dyn, N'@InputVAT BIGINT, @OutputVAT BIGINT', @InputVAT=@InputVAT, @OutputVAT=@OutputVAT;

/* 3. Repoint purchasing defaults/lines to INPUT tax codes. */
IF COL_LENGTH(N'dbo.items', N'input_tax_code_id') IS NOT NULL
BEGIN
    EXEC sp_executesql N'
        UPDATE i
        SET input_tax_code_id = inp.id
        FROM dbo.items i
        JOIN dbo.tax_codes cur ON cur.id = i.input_tax_code_id
        OUTER APPLY (
            SELECT TOP 1 t.id
            FROM dbo.tax_codes t
            WHERE t.tax_type = N''INPUT''
              AND ABS(CAST(t.rate AS DECIMAL(18,4)) - CAST(cur.rate AS DECIMAL(18,4))) < 0.0001
              AND t.is_active = 1
            ORDER BY CASE WHEN t.tax_code LIKE N''%_IN'' THEN 0 ELSE 1 END, t.tax_code
        ) inp
        WHERE cur.tax_type <> N''INPUT''
          AND inp.id IS NOT NULL;';
END;

IF OBJECT_ID(N'dbo.purchase_requisition_lines', N'U') IS NOT NULL
   AND COL_LENGTH(N'dbo.purchase_requisition_lines', N'tax_code_id') IS NOT NULL
BEGIN
    EXEC sp_executesql N'
        UPDATE prl
        SET tax_code_id = inp.id
        FROM dbo.purchase_requisition_lines prl
        JOIN dbo.tax_codes cur ON cur.id = prl.tax_code_id
        OUTER APPLY (
            SELECT TOP 1 t.id
            FROM dbo.tax_codes t
            WHERE t.tax_type = N''INPUT''
              AND ABS(CAST(t.rate AS DECIMAL(18,4)) - CAST(cur.rate AS DECIMAL(18,4))) < 0.0001
              AND t.is_active = 1
            ORDER BY CASE WHEN t.tax_code LIKE N''%_IN'' THEN 0 ELSE 1 END, t.tax_code
        ) inp
        WHERE cur.tax_type <> N''INPUT''
          AND inp.id IS NOT NULL;';
END;

IF OBJECT_ID(N'dbo.purchase_order_lines', N'U') IS NOT NULL
   AND COL_LENGTH(N'dbo.purchase_order_lines', N'tax_code_id') IS NOT NULL
BEGIN
    EXEC sp_executesql N'
        UPDATE pol
        SET tax_code_id = inp.id
        FROM dbo.purchase_order_lines pol
        JOIN dbo.tax_codes cur ON cur.id = pol.tax_code_id
        OUTER APPLY (
            SELECT TOP 1 t.id
            FROM dbo.tax_codes t
            WHERE t.tax_type = N''INPUT''
              AND ABS(CAST(t.rate AS DECIMAL(18,4)) - CAST(cur.rate AS DECIMAL(18,4))) < 0.0001
              AND t.is_active = 1
            ORDER BY CASE WHEN t.tax_code LIKE N''%_IN'' THEN 0 ELSE 1 END, t.tax_code
        ) inp
        WHERE cur.tax_type <> N''INPUT''
          AND inp.id IS NOT NULL;';
END;

/* 4. Repoint sales defaults to OUTPUT tax codes. */
IF COL_LENGTH(N'dbo.items', N'output_tax_code_id') IS NOT NULL
BEGIN
    EXEC sp_executesql N'
        UPDATE i
        SET output_tax_code_id = outp.id
        FROM dbo.items i
        JOIN dbo.tax_codes cur ON cur.id = i.output_tax_code_id
        OUTER APPLY (
            SELECT TOP 1 t.id
            FROM dbo.tax_codes t
            WHERE t.tax_type = N''OUTPUT''
              AND ABS(CAST(t.rate AS DECIMAL(18,4)) - CAST(cur.rate AS DECIMAL(18,4))) < 0.0001
              AND t.is_active = 1
            ORDER BY CASE WHEN t.tax_code IN (N''VAT10'', N''VAT0'') THEN 0 WHEN t.tax_code LIKE N''%_OUT'' THEN 1 ELSE 2 END, t.tax_code
        ) outp
        WHERE cur.tax_type <> N''OUTPUT''
          AND outp.id IS NOT NULL;';
END;

IF OBJECT_ID(N'dbo.sale_channels', N'U') IS NOT NULL
   AND COL_LENGTH(N'dbo.sale_channels', N'default_tax_code_id') IS NOT NULL
BEGIN
    EXEC sp_executesql N'
        UPDATE sc
        SET default_tax_code_id = outp.id
        FROM dbo.sale_channels sc
        JOIN dbo.tax_codes cur ON cur.id = sc.default_tax_code_id
        OUTER APPLY (
            SELECT TOP 1 t.id
            FROM dbo.tax_codes t
            WHERE t.tax_type = N''OUTPUT''
              AND ABS(CAST(t.rate AS DECIMAL(18,4)) - CAST(cur.rate AS DECIMAL(18,4))) < 0.0001
              AND t.is_active = 1
            ORDER BY CASE WHEN t.tax_code IN (N''VAT10'', N''VAT0'') THEN 0 WHEN t.tax_code LIKE N''%_OUT'' THEN 1 ELSE 2 END, t.tax_code
        ) outp
        WHERE cur.tax_type <> N''OUTPUT''
          AND outp.id IS NOT NULL;';
END;

/* 5. Drop old tax_type default/check constraints. */
DECLARE @sql NVARCHAR(MAX) = N'';

SELECT @sql += N'ALTER TABLE ' + QUOTENAME(OBJECT_SCHEMA_NAME(parent_object_id)) + N'.' + QUOTENAME(OBJECT_NAME(parent_object_id))
             + N' DROP CONSTRAINT ' + QUOTENAME(name) + N';' + CHAR(13)
FROM sys.default_constraints
WHERE parent_object_id = OBJECT_ID(N'dbo.tax_codes')
  AND parent_column_id = COLUMNPROPERTY(OBJECT_ID(N'dbo.tax_codes'), N'tax_type', 'ColumnId');

IF @sql <> N'' EXEC sp_executesql @sql;

SET @sql = N'';
SELECT @sql += N'ALTER TABLE ' + QUOTENAME(OBJECT_SCHEMA_NAME(parent_object_id)) + N'.' + QUOTENAME(OBJECT_NAME(parent_object_id))
             + N' DROP CONSTRAINT ' + QUOTENAME(name) + N';' + CHAR(13)
FROM sys.check_constraints
WHERE parent_object_id = OBJECT_ID(N'dbo.tax_codes')
  AND (name = N'CK_tax_codes_tax_type' OR definition LIKE N'%tax_type%');

IF @sql <> N'' EXEC sp_executesql @sql;

IF NOT EXISTS (
    SELECT 1
    FROM sys.default_constraints
    WHERE parent_object_id = OBJECT_ID(N'dbo.tax_codes')
      AND parent_column_id = COLUMNPROPERTY(OBJECT_ID(N'dbo.tax_codes'), N'tax_type', 'ColumnId')
)
BEGIN
    ALTER TABLE dbo.tax_codes ADD CONSTRAINT DF_tax_codes_tax_type DEFAULT N'INPUT' FOR tax_type;
END;

IF NOT EXISTS (
    SELECT 1
    FROM sys.check_constraints
    WHERE parent_object_id = OBJECT_ID(N'dbo.tax_codes')
      AND name = N'CK_tax_codes_tax_type'
)
BEGIN
    ALTER TABLE dbo.tax_codes ADD CONSTRAINT CK_tax_codes_tax_type CHECK (tax_type IN (N'INPUT', N'OUTPUT'));
END;

/* 6. Add FK for the new VAT Account column via dynamic SQL. */
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = N'FK_tax_vat_account')
BEGIN
    EXEC sp_executesql N'
        ALTER TABLE dbo.tax_codes
        ADD CONSTRAINT FK_tax_vat_account FOREIGN KEY(vat_account_id) REFERENCES dbo.chart_accounts(id);';
END;

PRINT 'Migration 13 completed: Tax Code now uses INPUT/OUTPUT only and a single VAT Account field.';
