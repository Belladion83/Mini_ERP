USE MiniERPFNB;
GO

/* =========================================================
   MASTER DATA v9 MIGRATION
   Purpose:
   - Add BOM/Recipe numbering for the new BOM Master Data screen.
   - Safe to run on an existing database. It does not drop data.
   ========================================================= */

IF NOT EXISTS (
    SELECT 1
    FROM dbo.number_ranges
    WHERE object_code = N'BOM'
      AND subkey = N''
)
BEGIN
    INSERT INTO dbo.number_ranges(object_code, subkey, prefix_template, next_no, width, year_mode, allow_manual, is_active)
    VALUES(N'BOM', N'', N'BOM-{YYYY}-{00001}', 1, 5, 1, 1, 1);
END
GO

PRINT 'Master Data v9 BOM migration completed.';
GO
