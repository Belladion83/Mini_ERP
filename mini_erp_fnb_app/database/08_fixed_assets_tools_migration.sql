/* =========================================================
   v14 - Fixed Assets / Tools
   Adds Asset Class + Fixed Asset/Tools master data and simple accounting depreciation/allocation runs.
   Safe to run on an existing database.
   ========================================================= */

/* COA structure nodes for Balance Sheet assets */
IF NOT EXISTS (SELECT 1 FROM dbo.coa_nodes WHERE node_code = N'BS-FA')
BEGIN
    INSERT INTO dbo.coa_nodes(node_code, node_name, report_section, node_type, parent_node_id, normal_balance, sequence_no, is_active)
    SELECT N'BS-FA', N'Fixed Assets', N'BALANCE_SHEET', N'POSTING_GROUP', id, N'DEBIT', 40, 1
    FROM dbo.coa_nodes WHERE node_code = N'BS-ASSET';
END;
GO

IF NOT EXISTS (SELECT 1 FROM dbo.coa_nodes WHERE node_code = N'BS-PREPAID')
BEGIN
    INSERT INTO dbo.coa_nodes(node_code, node_name, report_section, node_type, parent_node_id, normal_balance, sequence_no, is_active)
    SELECT N'BS-PREPAID', N'Prepaid Expenses / Tools Allocation', N'BALANCE_SHEET', N'POSTING_GROUP', id, N'DEBIT', 45, 1
    FROM dbo.coa_nodes WHERE node_code = N'BS-ASSET';
END;
GO

/* VAS-oriented G/L accounts for fixed assets and tools */
IF NOT EXISTS (SELECT 1 FROM dbo.chart_accounts WHERE account_code = N'153')
    INSERT INTO dbo.chart_accounts(account_code, account_name, account_type, account_group, normal_balance, coa_node_id, is_open_item, open_item_type, posting_allowed, is_active)
    SELECT N'153', N'Công cụ dụng cụ', N'ASSET', N'TOOL', N'DEBIT', (SELECT TOP 1 id FROM dbo.coa_nodes WHERE node_code=N'BS-PREPAID'), 0, N'NONE', 1, 1;
GO

IF NOT EXISTS (SELECT 1 FROM dbo.chart_accounts WHERE account_code = N'211')
    INSERT INTO dbo.chart_accounts(account_code, account_name, account_type, account_group, normal_balance, coa_node_id, is_open_item, open_item_type, posting_allowed, is_active)
    SELECT N'211', N'Tài sản cố định hữu hình', N'ASSET', N'FIXED_ASSET', N'DEBIT', (SELECT TOP 1 id FROM dbo.coa_nodes WHERE node_code=N'BS-FA'), 0, N'NONE', 1, 1;
GO

IF NOT EXISTS (SELECT 1 FROM dbo.chart_accounts WHERE account_code = N'2141')
    INSERT INTO dbo.chart_accounts(account_code, account_name, account_type, account_group, normal_balance, coa_node_id, is_open_item, open_item_type, posting_allowed, is_active)
    SELECT N'2141', N'Hao mòn tài sản cố định hữu hình', N'ASSET', N'ACCUM_DEPRECIATION', N'CREDIT', (SELECT TOP 1 id FROM dbo.coa_nodes WHERE node_code=N'BS-FA'), 0, N'NONE', 1, 1;
GO

IF NOT EXISTS (SELECT 1 FROM dbo.chart_accounts WHERE account_code = N'242')
    INSERT INTO dbo.chart_accounts(account_code, account_name, account_type, account_group, normal_balance, coa_node_id, is_open_item, open_item_type, posting_allowed, is_active)
    SELECT N'242', N'Chi phí trả trước', N'ASSET', N'PREPAID_EXPENSE', N'DEBIT', (SELECT TOP 1 id FROM dbo.coa_nodes WHERE node_code=N'BS-PREPAID'), 0, N'NONE', 1, 1;
GO

IF NOT EXISTS (SELECT 1 FROM dbo.chart_accounts WHERE account_code = N'627')
    INSERT INTO dbo.chart_accounts(account_code, account_name, account_type, account_group, normal_balance, coa_node_id, is_open_item, open_item_type, posting_allowed, is_active)
    SELECT N'627', N'Chi phí sản xuất chung', N'EXPENSE', N'DEPRECIATION_EXPENSE', N'DEBIT', (SELECT TOP 1 id FROM dbo.coa_nodes WHERE node_code=N'PL-EXP'), 0, N'NONE', 1, 1;
GO

/* Asset Class master */
IF OBJECT_ID(N'dbo.asset_classes', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.asset_classes (
        id BIGINT IDENTITY(1,1) CONSTRAINT PK_asset_classes PRIMARY KEY,
        class_code NVARCHAR(50) NOT NULL CONSTRAINT UQ_asset_class_code UNIQUE,
        class_name NVARCHAR(200) NOT NULL,
        asset_type NVARCHAR(30) NOT NULL CONSTRAINT DF_asset_class_type DEFAULT N'FIXED_ASSET', -- FIXED_ASSET / TOOL
        useful_life_months INT NOT NULL CONSTRAINT DF_asset_class_life DEFAULT 12,
        depreciation_method NVARCHAR(30) NOT NULL CONSTRAINT DF_asset_class_method DEFAULT N'STRAIGHT_LINE',
        asset_account_id BIGINT NULL,
        accumulated_dep_account_id BIGINT NULL,
        dep_expense_account_id BIGINT NULL,
        is_active BIT NOT NULL CONSTRAINT DF_asset_class_active DEFAULT 1,
        CONSTRAINT FK_asset_class_asset_account FOREIGN KEY(asset_account_id) REFERENCES dbo.chart_accounts(id),
        CONSTRAINT FK_asset_class_acc_dep_account FOREIGN KEY(accumulated_dep_account_id) REFERENCES dbo.chart_accounts(id),
        CONSTRAINT FK_asset_class_dep_exp_account FOREIGN KEY(dep_expense_account_id) REFERENCES dbo.chart_accounts(id)
    );
END;
GO

/* Asset / Tools master */
IF OBJECT_ID(N'dbo.fixed_assets', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.fixed_assets (
        id BIGINT IDENTITY(1,1) CONSTRAINT PK_fixed_assets PRIMARY KEY,
        asset_code NVARCHAR(50) NOT NULL CONSTRAINT UQ_fixed_assets_code UNIQUE,
        asset_name NVARCHAR(250) NOT NULL,
        asset_type NVARCHAR(30) NOT NULL CONSTRAINT DF_fixed_asset_type DEFAULT N'FIXED_ASSET', -- FIXED_ASSET / TOOL
        asset_class_id BIGINT NOT NULL,
        acquisition_date DATE NOT NULL,
        capitalization_date DATE NULL,
        depreciation_start_date DATE NULL,
        acquisition_cost DECIMAL(19,4) NOT NULL CONSTRAINT DF_fixed_asset_cost DEFAULT 0,
        residual_value DECIMAL(19,4) NOT NULL CONSTRAINT DF_fixed_asset_residual DEFAULT 0,
        useful_life_months INT NOT NULL CONSTRAINT DF_fixed_asset_life DEFAULT 12,
        asset_status NVARCHAR(30) NOT NULL CONSTRAINT DF_fixed_asset_status DEFAULT N'ACTIVE', -- PLANNED / ACTIVE / FULLY_DEPRECIATED / RETIRED
        location_name NVARCHAR(200) NULL,
        responsible_person NVARCHAR(200) NULL,
        serial_no NVARCHAR(120) NULL,
        is_depreciable BIT NOT NULL CONSTRAINT DF_fixed_asset_depreciable DEFAULT 1,
        is_active BIT NOT NULL CONSTRAINT DF_fixed_asset_active DEFAULT 1,
        created_at DATETIME2 NOT NULL CONSTRAINT DF_fixed_asset_created DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_fixed_asset_class FOREIGN KEY(asset_class_id) REFERENCES dbo.asset_classes(id)
    );
END;
GO

IF OBJECT_ID(N'dbo.asset_depreciation_runs', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.asset_depreciation_runs (
        id BIGINT IDENTITY(1,1) CONSTRAINT PK_asset_depreciation_runs PRIMARY KEY,
        run_no NVARCHAR(50) NOT NULL CONSTRAINT UQ_asset_depr_run_no UNIQUE,
        period_year INT NOT NULL,
        period_month INT NOT NULL,
        run_type NVARCHAR(50) NOT NULL CONSTRAINT DF_asset_depr_run_type DEFAULT N'MONTHLY_DEPRECIATION',
        posting_date DATE NOT NULL,
        memo NVARCHAR(500) NULL,
        total_amount DECIMAL(19,4) NOT NULL CONSTRAINT DF_asset_depr_total DEFAULT 0,
        journal_entry_id BIGINT NULL,
        status NVARCHAR(30) NOT NULL CONSTRAINT DF_asset_depr_status DEFAULT N'DRAFT',
        created_by BIGINT NULL,
        created_at DATETIME2 NOT NULL CONSTRAINT DF_asset_depr_created DEFAULT SYSUTCDATETIME(),
        CONSTRAINT UQ_asset_depr_period UNIQUE(period_year, period_month, run_type),
        CONSTRAINT FK_asset_depr_je FOREIGN KEY(journal_entry_id) REFERENCES dbo.journal_entries(id),
        CONSTRAINT FK_asset_depr_user FOREIGN KEY(created_by) REFERENCES dbo.users(id)
    );
END;
GO

IF OBJECT_ID(N'dbo.asset_depreciation_run_lines', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.asset_depreciation_run_lines (
        id BIGINT IDENTITY(1,1) CONSTRAINT PK_asset_depr_run_lines PRIMARY KEY,
        run_id BIGINT NOT NULL,
        asset_id BIGINT NOT NULL,
        debit_account_id BIGINT NOT NULL,
        credit_account_id BIGINT NOT NULL,
        amount DECIMAL(19,4) NOT NULL CONSTRAINT DF_asset_depr_line_amount DEFAULT 0,
        nbv_before DECIMAL(19,4) NOT NULL CONSTRAINT DF_asset_depr_nbv_before DEFAULT 0,
        nbv_after DECIMAL(19,4) NOT NULL CONSTRAINT DF_asset_depr_nbv_after DEFAULT 0,
        CONSTRAINT FK_asset_depr_line_run FOREIGN KEY(run_id) REFERENCES dbo.asset_depreciation_runs(id),
        CONSTRAINT FK_asset_depr_line_asset FOREIGN KEY(asset_id) REFERENCES dbo.fixed_assets(id),
        CONSTRAINT FK_asset_depr_line_dr FOREIGN KEY(debit_account_id) REFERENCES dbo.chart_accounts(id),
        CONSTRAINT FK_asset_depr_line_cr FOREIGN KEY(credit_account_id) REFERENCES dbo.chart_accounts(id)
    );
END;
GO

/* Optional asset reference on journal entry lines */
IF COL_LENGTH('dbo.journal_entry_lines', 'asset_id') IS NULL
BEGIN
    ALTER TABLE dbo.journal_entry_lines ADD asset_id BIGINT NULL;
END;
GO

IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = N'FK_jel_asset')
BEGIN
    ALTER TABLE dbo.journal_entry_lines ADD CONSTRAINT FK_jel_asset FOREIGN KEY(asset_id) REFERENCES dbo.fixed_assets(id);
END;
GO

/* View: acquisition cost, accumulated depreciation/allocation and NBV */
CREATE OR ALTER VIEW dbo.v_asset_nbv AS
SELECT
    fa.id,
    fa.asset_code,
    fa.asset_name,
    fa.asset_type,
    ac.class_code + N' - ' + ac.class_name AS asset_class,
    fa.acquisition_date,
    fa.capitalization_date,
    fa.depreciation_start_date,
    fa.acquisition_cost,
    fa.residual_value,
    fa.useful_life_months,
    ISNULL(SUM(CASE WHEN r.status = N'POSTED' THEN l.amount ELSE 0 END), 0) AS accumulated_depreciation,
    fa.acquisition_cost - ISNULL(SUM(CASE WHEN r.status = N'POSTED' THEN l.amount ELSE 0 END), 0) AS net_book_value,
    fa.asset_status,
    fa.location_name,
    fa.responsible_person,
    fa.serial_no,
    fa.is_depreciable,
    fa.is_active
FROM dbo.fixed_assets fa
JOIN dbo.asset_classes ac ON ac.id = fa.asset_class_id
LEFT JOIN dbo.asset_depreciation_run_lines l ON l.asset_id = fa.id
LEFT JOIN dbo.asset_depreciation_runs r ON r.id = l.run_id
GROUP BY fa.id, fa.asset_code, fa.asset_name, fa.asset_type, ac.class_code, ac.class_name,
         fa.acquisition_date, fa.capitalization_date, fa.depreciation_start_date,
         fa.acquisition_cost, fa.residual_value, fa.useful_life_months, fa.asset_status,
         fa.location_name, fa.responsible_person, fa.serial_no, fa.is_depreciable, fa.is_active;
GO

/* Number ranges */
IF NOT EXISTS (SELECT 1 FROM dbo.number_ranges WHERE object_code=N'ASSET_CLASS' AND subkey=N'FIXED_ASSET')
    INSERT INTO dbo.number_ranges(object_code, subkey, prefix_template, next_no, width, year_mode, allow_manual, is_active)
    VALUES(N'ASSET_CLASS', N'FIXED_ASSET', N'FAC-{00001}', 1, 5, 0, 1, 1);
GO

IF NOT EXISTS (SELECT 1 FROM dbo.number_ranges WHERE object_code=N'ASSET_CLASS' AND subkey=N'TOOL')
    INSERT INTO dbo.number_ranges(object_code, subkey, prefix_template, next_no, width, year_mode, allow_manual, is_active)
    VALUES(N'ASSET_CLASS', N'TOOL', N'TC-{00001}', 1, 5, 0, 1, 1);
GO

IF NOT EXISTS (SELECT 1 FROM dbo.number_ranges WHERE object_code=N'FIXED_ASSET' AND subkey=N'FIXED_ASSET')
    INSERT INTO dbo.number_ranges(object_code, subkey, prefix_template, next_no, width, year_mode, allow_manual, is_active)
    VALUES(N'FIXED_ASSET', N'FIXED_ASSET', N'FA-{YYYY}-{00001}', 1, 5, 1, 1, 1);
GO

IF NOT EXISTS (SELECT 1 FROM dbo.number_ranges WHERE object_code=N'FIXED_ASSET' AND subkey=N'TOOL')
    INSERT INTO dbo.number_ranges(object_code, subkey, prefix_template, next_no, width, year_mode, allow_manual, is_active)
    VALUES(N'FIXED_ASSET', N'TOOL', N'TOOL-{YYYY}-{00001}', 1, 5, 1, 1, 1);
GO

IF NOT EXISTS (SELECT 1 FROM dbo.number_ranges WHERE object_code=N'ASSET_RUN' AND subkey=N'')
    INSERT INTO dbo.number_ranges(object_code, subkey, prefix_template, next_no, width, year_mode, allow_manual, is_active)
    VALUES(N'ASSET_RUN', N'', N'ADR-{YYYY}-{MM}-{00001}', 1, 5, 1, 0, 1);
GO

/* Demo asset classes */
IF NOT EXISTS (SELECT 1 FROM dbo.asset_classes WHERE class_code = N'FA-EQUIP')
BEGIN
    INSERT INTO dbo.asset_classes(class_code, class_name, asset_type, useful_life_months, depreciation_method, asset_account_id, accumulated_dep_account_id, dep_expense_account_id, is_active)
    SELECT N'FA-EQUIP', N'Máy móc thiết bị F&B', N'FIXED_ASSET', 36, N'STRAIGHT_LINE',
           (SELECT id FROM dbo.chart_accounts WHERE account_code=N'211'),
           (SELECT id FROM dbo.chart_accounts WHERE account_code=N'2141'),
           (SELECT id FROM dbo.chart_accounts WHERE account_code=N'642'),
           1;
END;
GO

IF NOT EXISTS (SELECT 1 FROM dbo.asset_classes WHERE class_code = N'TOOL-KITCHEN')
BEGIN
    INSERT INTO dbo.asset_classes(class_code, class_name, asset_type, useful_life_months, depreciation_method, asset_account_id, accumulated_dep_account_id, dep_expense_account_id, is_active)
    SELECT N'TOOL-KITCHEN', N'Công cụ dụng cụ bếp/cửa hàng', N'TOOL', 12, N'STRAIGHT_LINE',
           (SELECT id FROM dbo.chart_accounts WHERE account_code=N'153'),
           (SELECT id FROM dbo.chart_accounts WHERE account_code=N'242'),
           (SELECT id FROM dbo.chart_accounts WHERE account_code=N'642'),
           1;
END;
GO

PRINT 'v14 fixed assets/tools migration completed.';
GO
