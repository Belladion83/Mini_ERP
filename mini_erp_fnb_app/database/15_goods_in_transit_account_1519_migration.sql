USE MiniERPFNB;
GO

/* =========================================================
   v22 - Goods-in-transit account correction to 1519
   Business rule: goods-in-transit / GR clearing uses account 1519.
   Keeps old 151/159 accounts for compatibility but new postings use 1519.
   ========================================================= */

IF NOT EXISTS (SELECT 1 FROM dbo.chart_accounts WHERE account_code = N'1519')
BEGIN
    INSERT INTO dbo.chart_accounts(
        account_code, account_name, account_type, account_group,
        normal_balance, coa_node_id, is_open_item, open_item_type,
        posting_allowed, is_active
    )
    SELECT
        N'1519',
        N'Hàng mua đang đi đường / GR clearing',
        N'ASSET',
        N'INVENTORY_IN_TRANSIT',
        N'DEBIT',
        (SELECT TOP 1 id FROM dbo.coa_nodes WHERE node_code = N'BS-ASSET'),
        0,
        N'NONE',
        1,
        1;
END
GO

UPDATE dbo.chart_accounts
SET account_name = N'Hàng mua đang đi đường / GR clearing',
    account_type = COALESCE(account_type, N'ASSET'),
    account_group = COALESCE(account_group, N'INVENTORY_IN_TRANSIT'),
    normal_balance = COALESCE(normal_balance, N'DEBIT'),
    posting_allowed = 1,
    is_active = 1
WHERE account_code = N'1519';
GO

-- Keep old test accounts inactive for new manual selection if they exist.
-- Do not delete them because historical journal entries may reference them.
IF EXISTS (SELECT 1 FROM dbo.chart_accounts WHERE account_code = N'159')
BEGIN
    UPDATE dbo.chart_accounts
    SET account_name = COALESCE(NULLIF(account_name, N''), N'Goods-in-transit legacy account'),
        is_active = 0
    WHERE account_code = N'159'
      AND NOT EXISTS (
          SELECT 1 FROM dbo.journal_entry_lines jel
          WHERE jel.account_id = dbo.chart_accounts.id
      );
END
GO

PRINT 'v22 goods-in-transit account 1519 migration completed.';
GO
