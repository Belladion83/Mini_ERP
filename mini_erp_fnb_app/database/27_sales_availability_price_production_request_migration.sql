/* =========================================================
   Migration 27.1
   Sales availability, price calculation, production request,
   and delivery layer allocation traceability

   Important: this migration must run in MiniERPFNB, not master.
   ========================================================= */

IF DB_ID(N'MiniERPFNB') IS NULL
BEGIN
    THROW 50001, 'Database MiniERPFNB does not exist. Please create/select the correct database before running migration 27.', 1;
END
GO

USE [MiniERPFNB];
GO

PRINT N'Start migration 27.1 - Sales availability/pricing and production requests';
PRINT N'Current database: ' + DB_NAME();
GO

/* Stop early if the script is being run in the wrong database or previous core migrations were not applied. */
IF OBJECT_ID(N'dbo.items', N'U') IS NULL
    THROW 50002, 'Missing dbo.items. You are likely running this script in the wrong database. Select MiniERPFNB and run again.', 1;
IF OBJECT_ID(N'dbo.users', N'U') IS NULL
    THROW 50003, 'Missing dbo.users. Run core schema/security migrations first, or select the correct database.', 1;
IF OBJECT_ID(N'dbo.warehouses', N'U') IS NULL
    THROW 50004, 'Missing dbo.warehouses. Run core schema migrations first.', 1;
IF OBJECT_ID(N'dbo.sales_orders', N'U') IS NULL
    THROW 50005, 'Missing dbo.sales_orders. Run core schema migrations first.', 1;
IF OBJECT_ID(N'dbo.production_orders', N'U') IS NULL
    THROW 50006, 'Missing dbo.production_orders. Run core schema migrations first.', 1;
IF OBJECT_ID(N'dbo.deliveries', N'U') IS NULL
    THROW 50007, 'Missing dbo.deliveries. Run core schema migrations first.', 1;
IF OBJECT_ID(N'dbo.delivery_lines', N'U') IS NULL
    THROW 50008, 'Missing dbo.delivery_lines. Run core schema migrations first.', 1;
IF OBJECT_ID(N'dbo.inventory_movements', N'U') IS NULL
    THROW 50009, 'Missing dbo.inventory_movements. Run core schema migrations first.', 1;
IF OBJECT_ID(N'dbo.inventory_layers', N'U') IS NULL
    THROW 50010, 'Missing dbo.inventory_layers. Run purchasing/FIFO migration 10 before migration 27.', 1;
GO

/* 1) Item Master - Sales target profit percent */
IF COL_LENGTH('dbo.items', 'profit_percent') IS NULL
BEGIN
    ALTER TABLE dbo.items ADD profit_percent DECIMAL(9,4) NOT NULL CONSTRAINT DF_items_profit_percent DEFAULT 20;
END
GO

/* 2) Sales shortage request sent to Production users */
IF OBJECT_ID(N'dbo.sales_production_requests', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.sales_production_requests (
        id BIGINT IDENTITY(1,1) CONSTRAINT PK_sales_production_requests PRIMARY KEY,
        request_date DATE NOT NULL CONSTRAINT DF_sales_prod_req_date DEFAULT CAST(GETDATE() AS DATE),
        requested_by BIGINT NULL,
        item_id BIGINT NOT NULL,
        warehouse_id BIGINT NOT NULL,
        requested_qty DECIMAL(19,4) NOT NULL,
        channel_code NVARCHAR(50) NULL,
        source_so_id BIGINT NULL,
        production_order_id BIGINT NULL,
        status NVARCHAR(30) NOT NULL CONSTRAINT DF_sales_prod_req_status DEFAULT N'OPEN',
        note NVARCHAR(500) NULL,
        created_at DATETIME2 NOT NULL CONSTRAINT DF_sales_prod_req_created DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_sales_prod_req_user FOREIGN KEY(requested_by) REFERENCES dbo.users(id),
        CONSTRAINT FK_sales_prod_req_item FOREIGN KEY(item_id) REFERENCES dbo.items(id),
        CONSTRAINT FK_sales_prod_req_wh FOREIGN KEY(warehouse_id) REFERENCES dbo.warehouses(id),
        CONSTRAINT FK_sales_prod_req_so FOREIGN KEY(source_so_id) REFERENCES dbo.sales_orders(id)
    );
END
GO

IF COL_LENGTH('dbo.sales_production_requests', 'production_order_id') IS NULL
    ALTER TABLE dbo.sales_production_requests ADD production_order_id BIGINT NULL;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.sales_production_requests') AND name = N'IX_sales_prod_req_status')
BEGIN
    CREATE INDEX IX_sales_prod_req_status ON dbo.sales_production_requests(status, request_date DESC, id DESC);
END
GO

/* 3) Link production order to Sales production request */
IF COL_LENGTH('dbo.production_orders', 'sales_request_id') IS NULL
BEGIN
    ALTER TABLE dbo.production_orders ADD sales_request_id BIGINT NULL;
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = N'FK_production_orders_sales_request')
BEGIN
    ALTER TABLE dbo.production_orders
    ADD CONSTRAINT FK_production_orders_sales_request FOREIGN KEY(sales_request_id) REFERENCES dbo.sales_production_requests(id);
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = N'FK_sales_prod_req_prod_order')
BEGIN
    ALTER TABLE dbo.sales_production_requests
    ADD CONSTRAINT FK_sales_prod_req_prod_order FOREIGN KEY(production_order_id) REFERENCES dbo.production_orders(id);
END
GO

/* 4) Sales delivery allocation to inventory/production layers.
      This lets one Sales Order consume stock from multiple production orders/layers. */
IF OBJECT_ID(N'dbo.sales_delivery_layer_allocations', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.sales_delivery_layer_allocations (
        id BIGINT IDENTITY(1,1) CONSTRAINT PK_sales_delivery_layer_allocations PRIMARY KEY,
        so_id BIGINT NOT NULL,
        delivery_id BIGINT NOT NULL,
        delivery_line_id BIGINT NOT NULL,
        issue_movement_id BIGINT NOT NULL,
        layer_id BIGINT NOT NULL,
        source_doc_type NVARCHAR(50) NULL,
        source_doc_id BIGINT NULL,
        production_order_id BIGINT NULL,
        quantity DECIMAL(19,4) NOT NULL,
        unit_cost DECIMAL(19,4) NOT NULL,
        amount DECIMAL(19,4) NOT NULL,
        created_at DATETIME2 NOT NULL CONSTRAINT DF_sales_alloc_created DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_sales_alloc_so FOREIGN KEY(so_id) REFERENCES dbo.sales_orders(id),
        CONSTRAINT FK_sales_alloc_delivery FOREIGN KEY(delivery_id) REFERENCES dbo.deliveries(id),
        CONSTRAINT FK_sales_alloc_delivery_line FOREIGN KEY(delivery_line_id) REFERENCES dbo.delivery_lines(id),
        CONSTRAINT FK_sales_alloc_issue_movement FOREIGN KEY(issue_movement_id) REFERENCES dbo.inventory_movements(id),
        CONSTRAINT FK_sales_alloc_layer FOREIGN KEY(layer_id) REFERENCES dbo.inventory_layers(id),
        CONSTRAINT FK_sales_alloc_prod_order FOREIGN KEY(production_order_id) REFERENCES dbo.production_orders(id)
    );
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.sales_delivery_layer_allocations') AND name = N'IX_sales_alloc_so')
BEGIN
    CREATE INDEX IX_sales_alloc_so ON dbo.sales_delivery_layer_allocations(so_id, delivery_id, delivery_line_id);
END
GO

PRINT N'Migration 27.1 completed successfully.';
GO
