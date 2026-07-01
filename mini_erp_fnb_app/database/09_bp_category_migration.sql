/* =========================================================
   v15 - Business Partner Category
   Adds BP Category to Customer/Vendor master data.
   Safe to run on an existing database.

   Category values:
   - COMPANY    : Doanh nghiệp
   - INDIVIDUAL : Cá nhân
   - BANK       : Ngân hàng
   - ONE_TIME   : Vãng lai
   ========================================================= */

IF COL_LENGTH(N'dbo.business_partners', N'bp_category') IS NULL
BEGIN
    ALTER TABLE dbo.business_partners
    ADD bp_category NVARCHAR(30) NOT NULL
        CONSTRAINT DF_bp_category DEFAULT N'COMPANY';
END;
GO

/* Make common walk-in customer easier to identify */
UPDATE dbo.business_partners
SET bp_category = N'ONE_TIME'
WHERE bp_code IN (N'CASH', N'WALKIN', N'ONE_TIME')
  AND ISNULL(bp_category, N'') <> N'ONE_TIME';
GO

/* Add check constraint when it does not already exist */
IF NOT EXISTS (
    SELECT 1
    FROM sys.check_constraints
    WHERE name = N'CK_bp_category'
      AND parent_object_id = OBJECT_ID(N'dbo.business_partners')
)
BEGIN
    ALTER TABLE dbo.business_partners WITH CHECK
    ADD CONSTRAINT CK_bp_category
    CHECK (bp_category IN (N'COMPANY', N'INDIVIDUAL', N'BANK', N'ONE_TIME'));
END;
GO
