/* =========================================================
   Migration 33 - Purchase Requisition PO Created Status
   Purpose:
   - Introduce PR status PO_CREATED to clearly separate PRs that already have PO references.
   - Existing PRs with one or more linked PO lines are updated from RELEASED to PO_CREATED.
   - PRs without linked PO lines remain RELEASED so they can still be used for PO creation.
   ========================================================= */

USE [MiniERPFNB];
GO

PRINT N'Start migration 33 - PR PO_CREATED status';
GO

IF OBJECT_ID(N'dbo.purchase_requisitions', N'U') IS NULL
    THROW 50033, 'Required table dbo.purchase_requisitions does not exist.', 1;
IF OBJECT_ID(N'dbo.purchase_requisition_lines', N'U') IS NULL
    THROW 50033, 'Required table dbo.purchase_requisition_lines does not exist.', 1;
GO

/* Existing data alignment: if a released PR already has any PO reference, mark it as PO_CREATED. */
UPDATE pr
SET pr.status = N'PO_CREATED'
FROM dbo.purchase_requisitions pr
WHERE pr.status = N'RELEASED'
  AND EXISTS (
      SELECT 1
      FROM dbo.purchase_requisition_lines prl
      WHERE prl.pr_id = pr.id
        AND prl.po_line_id IS NOT NULL
  );
GO

/* Defensive cleanup: if an old PO_CREATED PR has no PO link anymore, reopen it to RELEASED. */
UPDATE pr
SET pr.status = N'RELEASED'
FROM dbo.purchase_requisitions pr
WHERE pr.status = N'PO_CREATED'
  AND NOT EXISTS (
      SELECT 1
      FROM dbo.purchase_requisition_lines prl
      WHERE prl.pr_id = pr.id
        AND prl.po_line_id IS NOT NULL
  );
GO

PRINT N'Completed migration 33 - PR PO_CREATED status';
GO
