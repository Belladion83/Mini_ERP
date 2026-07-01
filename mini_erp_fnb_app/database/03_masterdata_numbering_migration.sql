USE MiniERPFNB;
GO

/* =========================================================
   MASTER DATA v3 MIGRATION
   Purpose:
   - Add number ranges for master data auto-generation
   - Safe to run on an existing database. It does not drop data.
   ========================================================= */

DECLARE @ranges TABLE(
    object_code NVARCHAR(50),
    subkey NVARCHAR(50),
    prefix_template NVARCHAR(120),
    next_no BIGINT,
    width INT,
    year_mode BIT,
    allow_manual BIT
);

INSERT INTO @ranges(object_code, subkey, prefix_template, next_no, width, year_mode, allow_manual) VALUES
(N'CUSTOMER', N'', N'CUST-{YYYY}-{00001}', 1, 5, 1, 1),
(N'VENDOR', N'', N'VEND-{YYYY}-{00001}', 1, 5, 1, 1),
(N'BP', N'', N'BP-{YYYY}-{00001}', 1, 5, 1, 1),
(N'ITEM', N'', N'ITM-{00001}', 1, 5, 0, 1),
(N'ITEM', N'RAW', N'RM-{00001}', 1, 5, 0, 1),
(N'ITEM', N'PACKAGING', N'PK-{00001}', 1, 5, 0, 1),
(N'ITEM', N'FINISHED', N'FG-{00001}', 1, 5, 0, 1),
(N'ITEM', N'RESALE', N'RS-{00001}', 1, 5, 0, 1),
(N'ITEM', N'SERVICE', N'SVC-{00001}', 1, 5, 0, 1),
(N'WAREHOUSE', N'', N'WH-{00001}', 1, 4, 0, 1),
(N'WAREHOUSE', N'MAIN', N'MAIN-{00001}', 1, 3, 0, 1),
(N'WAREHOUSE', N'STORE', N'STORE-{00001}', 1, 3, 0, 1),
(N'WAREHOUSE', N'PRODUCTION', N'PROD-WH-{00001}', 1, 3, 0, 1),
(N'TAX', N'', N'TAX-{00001}', 1, 3, 0, 1),
(N'COA', N'', N'ACC-{00001}', 1, 5, 0, 1),
(N'BOM', N'', N'BOM-{YYYY}-{00001}', 1, 5, 1, 1);

INSERT INTO dbo.number_ranges(object_code, subkey, prefix_template, next_no, width, year_mode, allow_manual, is_active)
SELECT r.object_code, r.subkey, r.prefix_template, r.next_no, r.width, r.year_mode, r.allow_manual, 1
FROM @ranges r
WHERE NOT EXISTS (
    SELECT 1
    FROM dbo.number_ranges nr
    WHERE nr.object_code = r.object_code
      AND nr.subkey = r.subkey
);
GO

PRINT 'Master Data v3 migration completed.';
GO
