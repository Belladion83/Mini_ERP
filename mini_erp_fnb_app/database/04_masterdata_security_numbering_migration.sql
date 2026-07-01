USE MiniERPFNB;
GO

/* =========================================================
   v4 NUMBERING BEHAVIOR
   - Preview does NOT increase next_no.
   - Save consumes/increases next_no exactly once.
   ========================================================= */

CREATE OR ALTER PROCEDURE dbo.sp_PreviewDocumentNo
    @ObjectCode NVARCHAR(50),
    @Subkey NVARCHAR(50) = N'',
    @DocDate DATE,
    @DocumentNo NVARCHAR(80) OUTPUT
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE
        @PrefixTemplate NVARCHAR(120),
        @NextNo BIGINT,
        @Width INT,
        @YearMode BIT,
        @LastYear INT,
        @CurrentYear INT = YEAR(@DocDate),
        @CurrentMonth NVARCHAR(2) = RIGHT(N'0' + CAST(MONTH(@DocDate) AS NVARCHAR(2)), 2),
        @FormattedNo NVARCHAR(50),
        @EffectiveNextNo BIGINT;

    SELECT TOP 1
        @PrefixTemplate = prefix_template,
        @NextNo = next_no,
        @Width = width,
        @YearMode = year_mode,
        @LastYear = last_year
    FROM dbo.number_ranges
    WHERE object_code = @ObjectCode
      AND subkey = ISNULL(@Subkey, N'')
      AND is_active = 1;

    IF @PrefixTemplate IS NULL
        THROW 51000, 'Number range is not configured.', 1;

    SET @EffectiveNextNo = CASE
        WHEN @YearMode = 1 AND ISNULL(@LastYear, 0) <> @CurrentYear THEN 1
        ELSE @NextNo
    END;

    SET @FormattedNo = RIGHT(REPLICATE('0', @Width) + CAST(@EffectiveNextNo AS NVARCHAR(50)), @Width);

    SET @DocumentNo = @PrefixTemplate;
    SET @DocumentNo = REPLACE(@DocumentNo, N'{YYYY}', CAST(@CurrentYear AS NVARCHAR(4)));
    SET @DocumentNo = REPLACE(@DocumentNo, N'{YY}', RIGHT(CAST(@CurrentYear AS NVARCHAR(4)), 2));
    SET @DocumentNo = REPLACE(@DocumentNo, N'{MM}', @CurrentMonth);
    SET @DocumentNo = REPLACE(@DocumentNo, N'{SUBKEY}', ISNULL(@Subkey, N''));
    SET @DocumentNo = REPLACE(@DocumentNo, N'{00001}', @FormattedNo);
END
GO

CREATE OR ALTER PROCEDURE dbo.sp_ConsumeDocumentNoIfMatch
    @ObjectCode NVARCHAR(50),
    @Subkey NVARCHAR(50) = N'',
    @DocDate DATE,
    @DocumentNo NVARCHAR(80),
    @Consumed BIT OUTPUT
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE
        @PrefixTemplate NVARCHAR(120),
        @NextNo BIGINT,
        @Width INT,
        @YearMode BIT,
        @LastYear INT,
        @CurrentYear INT = YEAR(@DocDate),
        @CurrentMonth NVARCHAR(2) = RIGHT(N'0' + CAST(MONTH(@DocDate) AS NVARCHAR(2)), 2),
        @FormattedNo NVARCHAR(50),
        @EffectiveNextNo BIGINT,
        @PreviewNo NVARCHAR(80);

    SET @Consumed = 0;

    BEGIN TRAN;

    SELECT TOP 1
        @PrefixTemplate = prefix_template,
        @NextNo = next_no,
        @Width = width,
        @YearMode = year_mode,
        @LastYear = last_year
    FROM dbo.number_ranges WITH (UPDLOCK, HOLDLOCK)
    WHERE object_code = @ObjectCode
      AND subkey = ISNULL(@Subkey, N'')
      AND is_active = 1;

    IF @PrefixTemplate IS NULL
    BEGIN
        ROLLBACK TRAN;
        THROW 51000, 'Number range is not configured.', 1;
    END;

    SET @EffectiveNextNo = CASE
        WHEN @YearMode = 1 AND ISNULL(@LastYear, 0) <> @CurrentYear THEN 1
        ELSE @NextNo
    END;

    SET @FormattedNo = RIGHT(REPLICATE('0', @Width) + CAST(@EffectiveNextNo AS NVARCHAR(50)), @Width);

    SET @PreviewNo = @PrefixTemplate;
    SET @PreviewNo = REPLACE(@PreviewNo, N'{YYYY}', CAST(@CurrentYear AS NVARCHAR(4)));
    SET @PreviewNo = REPLACE(@PreviewNo, N'{YY}', RIGHT(CAST(@CurrentYear AS NVARCHAR(4)), 2));
    SET @PreviewNo = REPLACE(@PreviewNo, N'{MM}', @CurrentMonth);
    SET @PreviewNo = REPLACE(@PreviewNo, N'{SUBKEY}', ISNULL(@Subkey, N''));
    SET @PreviewNo = REPLACE(@PreviewNo, N'{00001}', @FormattedNo);

    IF @PreviewNo = @DocumentNo
    BEGIN
        UPDATE dbo.number_ranges
        SET next_no = @EffectiveNextNo + 1,
            last_year = CASE WHEN @YearMode = 1 THEN @CurrentYear ELSE last_year END
        WHERE object_code = @ObjectCode
          AND subkey = ISNULL(@Subkey, N'');
        SET @Consumed = 1;
    END;

    COMMIT TRAN;
END
GO

/* Optional: keep old consume procedure for transaction save/posting services. */
CREATE OR ALTER PROCEDURE dbo.sp_GenerateDocumentNo
    @ObjectCode NVARCHAR(50),
    @Subkey NVARCHAR(50) = N'',
    @DocDate DATE,
    @DocumentNo NVARCHAR(80) OUTPUT
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE
        @PrefixTemplate NVARCHAR(120),
        @NextNo BIGINT,
        @Width INT,
        @YearMode BIT,
        @LastYear INT,
        @CurrentYear INT = YEAR(@DocDate),
        @CurrentMonth NVARCHAR(2) = RIGHT(N'0' + CAST(MONTH(@DocDate) AS NVARCHAR(2)), 2),
        @FormattedNo NVARCHAR(50),
        @EffectiveNextNo BIGINT;

    BEGIN TRAN;

    SELECT TOP 1
        @PrefixTemplate = prefix_template,
        @NextNo = next_no,
        @Width = width,
        @YearMode = year_mode,
        @LastYear = last_year
    FROM dbo.number_ranges WITH (UPDLOCK, HOLDLOCK)
    WHERE object_code = @ObjectCode
      AND subkey = ISNULL(@Subkey, N'')
      AND is_active = 1;

    IF @PrefixTemplate IS NULL
    BEGIN
        ROLLBACK TRAN;
        THROW 51000, 'Number range is not configured.', 1;
    END;

    SET @EffectiveNextNo = CASE
        WHEN @YearMode = 1 AND ISNULL(@LastYear, 0) <> @CurrentYear THEN 1
        ELSE @NextNo
    END;

    SET @FormattedNo = RIGHT(REPLICATE('0', @Width) + CAST(@EffectiveNextNo AS NVARCHAR(50)), @Width);

    SET @DocumentNo = @PrefixTemplate;
    SET @DocumentNo = REPLACE(@DocumentNo, N'{YYYY}', CAST(@CurrentYear AS NVARCHAR(4)));
    SET @DocumentNo = REPLACE(@DocumentNo, N'{YY}', RIGHT(CAST(@CurrentYear AS NVARCHAR(4)), 2));
    SET @DocumentNo = REPLACE(@DocumentNo, N'{MM}', @CurrentMonth);
    SET @DocumentNo = REPLACE(@DocumentNo, N'{SUBKEY}', ISNULL(@Subkey, N''));
    SET @DocumentNo = REPLACE(@DocumentNo, N'{00001}', @FormattedNo);

    UPDATE dbo.number_ranges
    SET next_no = @EffectiveNextNo + 1,
        last_year = CASE WHEN @YearMode = 1 THEN @CurrentYear ELSE last_year END
    WHERE object_code = @ObjectCode
      AND subkey = ISNULL(@Subkey, N'');

    COMMIT TRAN;
END
GO

/* =========================================================
   v4 SECURITY MASTER DATA + DEMO USERS
   Password for all demo users below: Test@123
   ========================================================= */

IF NOT EXISTS (SELECT 1 FROM dbo.user_groups WHERE group_code = N'MASTER_DATA')
    INSERT INTO dbo.user_groups(group_code, group_name, description)
    VALUES (N'MASTER_DATA', N'Master Data Users', N'Master data maintenance access');

IF NOT EXISTS (SELECT 1 FROM dbo.user_groups WHERE group_code = N'DASHBOARD_ONLY')
    INSERT INTO dbo.user_groups(group_code, group_name, description)
    VALUES (N'DASHBOARD_ONLY', N'Dashboard Users', N'Dashboard only access');
GO

-- Ensure standard permissions exist.
MERGE dbo.permissions AS target
USING (VALUES
    (N'DASHBOARD_VIEW', N'View dashboard', N'CORE'),
    (N'MASTER_VIEW', N'View master data', N'MASTER'),
    (N'MASTER_EDIT', N'Edit master data', N'MASTER'),
    (N'PURCHASE_VIEW', N'View purchasing', N'PURCHASE'),
    (N'PURCHASE_EDIT', N'Create/edit purchasing documents', N'PURCHASE'),
    (N'SALES_VIEW', N'View sales', N'SALES'),
    (N'SALES_EDIT', N'Create/edit sales documents', N'SALES'),
    (N'INVENTORY_VIEW', N'View inventory', N'INVENTORY'),
    (N'INVENTORY_EDIT', N'Create inventory movements', N'INVENTORY'),
    (N'PRODUCTION_VIEW', N'View production', N'PRODUCTION'),
    (N'PRODUCTION_EDIT', N'Create production documents', N'PRODUCTION'),
    (N'ACCOUNTING_VIEW', N'View accounting', N'ACCOUNTING'),
    (N'ACCOUNTING_EDIT', N'Post accounting entries', N'ACCOUNTING'),
    (N'USER_ADMIN', N'Manage users and permissions', N'SECURITY'),
    (N'INTEGRATION_VIEW', N'View integrations', N'INTEGRATION'),
    (N'INTEGRATION_EDIT', N'Edit/run integrations', N'INTEGRATION')
) AS src(permission_code, permission_name, module_code)
ON target.permission_code = src.permission_code
WHEN NOT MATCHED THEN
    INSERT(permission_code, permission_name, module_code)
    VALUES(src.permission_code, src.permission_name, src.module_code);
GO

-- Permission matrix for demo groups.
INSERT INTO dbo.group_permissions(group_id, permission_id)
SELECT g.id, p.id
FROM dbo.user_groups g
JOIN dbo.permissions p ON p.permission_code IN (N'DASHBOARD_VIEW', N'MASTER_VIEW', N'MASTER_EDIT')
WHERE g.group_code = N'MASTER_DATA'
  AND NOT EXISTS (SELECT 1 FROM dbo.group_permissions x WHERE x.group_id = g.id AND x.permission_id = p.id);

INSERT INTO dbo.group_permissions(group_id, permission_id)
SELECT g.id, p.id
FROM dbo.user_groups g
JOIN dbo.permissions p ON p.permission_code IN (N'DASHBOARD_VIEW')
WHERE g.group_code = N'DASHBOARD_ONLY'
  AND NOT EXISTS (SELECT 1 FROM dbo.group_permissions x WHERE x.group_id = g.id AND x.permission_id = p.id);
GO

-- Demo users. Password hash = sha256(Test@123).
DECLARE @TestHash NVARCHAR(255) = N'sha256$8776f108e247ab1e2b323042c049c266407c81fbad41bde1e8dfc1bb66fd267e';

MERGE dbo.users AS target
USING (VALUES
    (N'admin_demo',      N'Admin Demo User',       N'admin.demo@example.com',      N'ADMIN'),
    (N'master_user',     N'Master Data User',      N'master.user@example.com',     N'MASTER_DATA'),
    (N'purchase_user',   N'Purchasing User',       N'purchase.user@example.com',   N'PURCHASING'),
    (N'sales_user',      N'Sales User',            N'sales.user@example.com',      N'SALES'),
    (N'inventory_user',  N'Inventory User',        N'inventory.user@example.com',  N'WAREHOUSE'),
    (N'production_user', N'Production User',       N'production.user@example.com', N'PRODUCTION'),
    (N'accounting_user', N'Accounting User',       N'accounting.user@example.com', N'ACCOUNTING'),
    (N'dashboard_user',  N'Dashboard Only User',   N'dashboard.user@example.com',  N'DASHBOARD_ONLY')
) AS src(username, full_name, email, group_code)
ON target.username = src.username
WHEN NOT MATCHED THEN
    INSERT(username, password_hash, full_name, email, is_active)
    VALUES(src.username, @TestHash, src.full_name, src.email, 1)
WHEN MATCHED THEN
    UPDATE SET full_name = src.full_name, email = src.email, is_active = 1;

INSERT INTO dbo.user_group_members(user_id, group_id)
SELECT u.id, g.id
FROM dbo.users u
JOIN (VALUES
    (N'admin_demo',      N'ADMIN'),
    (N'master_user',     N'MASTER_DATA'),
    (N'purchase_user',   N'PURCHASING'),
    (N'sales_user',      N'SALES'),
    (N'inventory_user',  N'WAREHOUSE'),
    (N'production_user', N'PRODUCTION'),
    (N'accounting_user', N'ACCOUNTING'),
    (N'dashboard_user',  N'DASHBOARD_ONLY')
) AS map(username, group_code) ON map.username = u.username
JOIN dbo.user_groups g ON g.group_code = map.group_code
WHERE NOT EXISTS (
    SELECT 1 FROM dbo.user_group_members x WHERE x.user_id = u.id AND x.group_id = g.id
);
GO
