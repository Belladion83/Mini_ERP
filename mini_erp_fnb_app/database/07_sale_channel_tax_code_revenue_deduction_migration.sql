USE MiniERPFNB;
GO

/* =========================================================
   v11 Migration - Sale Channel Tax Code + VAS Revenue Deduction G/L
   Safe to run on existing database. Do not rerun 01_schema.sql
   if you already have transaction/master data.
   ========================================================= */

/* 1) Add COA report node for VAS revenue deductions */
IF NOT EXISTS (SELECT 1 FROM dbo.coa_nodes WHERE node_code = N'PL-REV-DED')
BEGIN
    INSERT INTO dbo.coa_nodes(node_code, node_name, report_section, node_type, parent_node_id, normal_balance, sequence_no, is_active)
    VALUES(
        N'PL-REV-DED',
        N'Revenue Deductions',
        N'P_AND_L',
        N'POSTING_GROUP',
        (SELECT TOP 1 id FROM dbo.coa_nodes WHERE node_code = N'PL-REV'),
        N'DEBIT',
        65,
        1
    );
END;
GO

UPDATE child
SET parent_node_id = parent.id,
    normal_balance = N'DEBIT',
    report_section = N'P_AND_L',
    node_type = N'POSTING_GROUP',
    sequence_no = 65,
    is_active = 1
FROM dbo.coa_nodes child
JOIN dbo.coa_nodes parent ON parent.node_code = N'PL-REV'
WHERE child.node_code = N'PL-REV-DED';
GO

/* 2) Add VAS account 521 - Các khoản giảm trừ doanh thu */
IF NOT EXISTS (SELECT 1 FROM dbo.chart_accounts WHERE account_code = N'521')
BEGIN
    INSERT INTO dbo.chart_accounts(
        account_code,
        account_name,
        account_type,
        account_group,
        normal_balance,
        coa_node_id,
        is_open_item,
        open_item_type,
        posting_allowed,
        is_active
    )
    VALUES(
        N'521',
        N'Các khoản giảm trừ doanh thu',
        N'REVENUE_DEDUCTION',
        N'REVENUE_DEDUCTION',
        N'DEBIT',
        (SELECT TOP 1 id FROM dbo.coa_nodes WHERE node_code = N'PL-REV-DED'),
        0,
        N'NONE',
        1,
        1
    );
END;
GO

UPDATE dbo.chart_accounts
SET account_name = N'Các khoản giảm trừ doanh thu',
    account_type = N'REVENUE_DEDUCTION',
    account_group = N'REVENUE_DEDUCTION',
    normal_balance = N'DEBIT',
    coa_node_id = COALESCE(coa_node_id, (SELECT TOP 1 id FROM dbo.coa_nodes WHERE node_code = N'PL-REV-DED')),
    is_open_item = 0,
    open_item_type = N'NONE',
    posting_allowed = 1,
    is_active = 1
WHERE account_code = N'521';
GO

/* 3) Replace Sale Channel Tax % UI logic with Tax Code master data */
IF COL_LENGTH('dbo.sale_channels', 'default_tax_code_id') IS NULL
BEGIN
    ALTER TABLE dbo.sale_channels ADD default_tax_code_id BIGINT NULL;
END;
GO

IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = N'FK_sale_channel_tax_code')
BEGIN
    ALTER TABLE dbo.sale_channels WITH CHECK
    ADD CONSTRAINT FK_sale_channel_tax_code FOREIGN KEY(default_tax_code_id) REFERENCES dbo.tax_codes(id);
END;
GO

/* Map existing sale channel tax rate to OUTPUT tax code when possible; fallback to VAT10_OUT/VAT10. */
UPDATE sc
SET default_tax_code_id = COALESCE(
        CASE WHEN current_tax.tax_type = N'OUTPUT' THEN sc.default_tax_code_id END,
        matched_tax.id,
        vat10.id
    ),
    discount_account_id = COALESCE(sc.discount_account_id, account_521.id)
FROM dbo.sale_channels sc
LEFT JOIN dbo.tax_codes current_tax ON current_tax.id = sc.default_tax_code_id
OUTER APPLY (
    SELECT TOP 1 id
    FROM dbo.tax_codes t
    WHERE t.is_active = 1
      AND ISNULL(t.tax_type, N'OUTPUT') = N'OUTPUT'
      AND ABS(CAST(t.rate AS DECIMAL(18,4)) - CAST(ISNULL(sc.default_tax_rate, 10) AS DECIMAL(18,4))) < 0.0001
    ORDER BY CASE WHEN t.tax_code IN (N'VAT10_OUT', N'VAT10') THEN 0 ELSE 1 END, t.tax_code
) matched_tax
OUTER APPLY (SELECT TOP 1 id FROM dbo.tax_codes WHERE tax_code IN (N'VAT10_OUT', N'VAT10') AND ISNULL(tax_type, N'OUTPUT') = N'OUTPUT' ORDER BY CASE WHEN tax_code = N'VAT10_OUT' THEN 0 ELSE 1 END) vat10
OUTER APPLY (SELECT TOP 1 id FROM dbo.chart_accounts WHERE account_code = N'521') account_521;
GO

/* 4) Optional: improve default channel master values */
UPDATE dbo.sale_channels
SET default_tax_rate = COALESCE((SELECT TOP 1 rate FROM dbo.tax_codes WHERE id = default_tax_code_id), default_tax_rate)
WHERE default_tax_code_id IS NOT NULL;
GO

PRINT N'v11 migration completed: Sale Channel now uses Tax Code; G/L 521 revenue deduction account added.';
GO
