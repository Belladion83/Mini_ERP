USE MiniERPFNB;
GO

/* =========================================================
   CLEAN SETUP - DROP OBJECTS IN SAFE ORDER
   ========================================================= */

IF OBJECT_ID('dbo.sp_GenerateDocumentNo', 'P') IS NOT NULL DROP PROCEDURE dbo.sp_GenerateDocumentNo;
GO

DECLARE @sql NVARCHAR(MAX) = N'';
SELECT @sql += 'ALTER TABLE ' + QUOTENAME(OBJECT_SCHEMA_NAME(parent_object_id)) + '.' + QUOTENAME(OBJECT_NAME(parent_object_id)) +
               ' DROP CONSTRAINT ' + QUOTENAME(name) + ';' + CHAR(13)
FROM sys.foreign_keys;
EXEC sp_executesql @sql;
GO

DROP TABLE IF EXISTS dbo.audit_logs;
DROP TABLE IF EXISTS dbo.group_permissions;
DROP TABLE IF EXISTS dbo.user_group_members;
DROP TABLE IF EXISTS dbo.permissions;
DROP TABLE IF EXISTS dbo.user_groups;
DROP TABLE IF EXISTS dbo.users;
DROP TABLE IF EXISTS dbo.integration_sync_logs;
DROP TABLE IF EXISTS dbo.integration_connections;
DROP TABLE IF EXISTS dbo.journal_entry_lines;
DROP TABLE IF EXISTS dbo.journal_entries;
DROP TABLE IF EXISTS dbo.customer_receipts;
DROP TABLE IF EXISTS dbo.vendor_payments;
DROP TABLE IF EXISTS dbo.ar_invoice_lines;
DROP TABLE IF EXISTS dbo.ar_invoices;
DROP TABLE IF EXISTS dbo.delivery_lines;
DROP TABLE IF EXISTS dbo.deliveries;
DROP TABLE IF EXISTS dbo.sales_order_lines;
DROP TABLE IF EXISTS dbo.sales_orders;
DROP TABLE IF EXISTS dbo.ap_invoice_lines;
DROP TABLE IF EXISTS dbo.ap_invoices;
DROP TABLE IF EXISTS dbo.goods_receipt_lines;
DROP TABLE IF EXISTS dbo.goods_receipts;
DROP TABLE IF EXISTS dbo.purchase_order_lines;
DROP TABLE IF EXISTS dbo.purchase_orders;
DROP TABLE IF EXISTS dbo.production_receipt_lines;
DROP TABLE IF EXISTS dbo.production_receipts;
DROP TABLE IF EXISTS dbo.material_issue_lines;
DROP TABLE IF EXISTS dbo.material_issues;
DROP TABLE IF EXISTS dbo.production_order_lines;
DROP TABLE IF EXISTS dbo.production_orders;
DROP TABLE IF EXISTS dbo.inventory_movements;
DROP TABLE IF EXISTS dbo.bom_components;
DROP TABLE IF EXISTS dbo.boms;
DROP TABLE IF EXISTS dbo.items;
DROP TABLE IF EXISTS dbo.business_partners;
DROP TABLE IF EXISTS dbo.sale_channels;
DROP TABLE IF EXISTS dbo.warehouses;
DROP TABLE IF EXISTS dbo.tax_codes;
DROP TABLE IF EXISTS dbo.chart_accounts;
DROP TABLE IF EXISTS dbo.coa_nodes;
DROP TABLE IF EXISTS dbo.number_ranges;
GO

/* =========================================================
   SECURITY
   ========================================================= */

CREATE TABLE dbo.users (
    id BIGINT IDENTITY(1,1) CONSTRAINT PK_users PRIMARY KEY,
    username NVARCHAR(80) NOT NULL CONSTRAINT UQ_users_username UNIQUE,
    password_hash NVARCHAR(255) NOT NULL,
    full_name NVARCHAR(200) NULL,
    email NVARCHAR(200) NULL,
    is_active BIT NOT NULL CONSTRAINT DF_users_is_active DEFAULT 1,
    created_at DATETIME2 NOT NULL CONSTRAINT DF_users_created_at DEFAULT SYSUTCDATETIME(),
    updated_at DATETIME2 NULL
);
GO

CREATE TABLE dbo.user_groups (
    id BIGINT IDENTITY(1,1) CONSTRAINT PK_user_groups PRIMARY KEY,
    group_code NVARCHAR(80) NOT NULL CONSTRAINT UQ_user_groups_code UNIQUE,
    group_name NVARCHAR(200) NOT NULL,
    description NVARCHAR(500) NULL,
    is_active BIT NOT NULL CONSTRAINT DF_user_groups_active DEFAULT 1
);
GO

CREATE TABLE dbo.user_group_members (
    id BIGINT IDENTITY(1,1) CONSTRAINT PK_user_group_members PRIMARY KEY,
    user_id BIGINT NOT NULL,
    group_id BIGINT NOT NULL,
    CONSTRAINT FK_ugm_user FOREIGN KEY(user_id) REFERENCES dbo.users(id),
    CONSTRAINT FK_ugm_group FOREIGN KEY(group_id) REFERENCES dbo.user_groups(id),
    CONSTRAINT UQ_ugm UNIQUE(user_id, group_id)
);
GO

CREATE TABLE dbo.permissions (
    id BIGINT IDENTITY(1,1) CONSTRAINT PK_permissions PRIMARY KEY,
    permission_code NVARCHAR(120) NOT NULL CONSTRAINT UQ_permissions_code UNIQUE,
    permission_name NVARCHAR(200) NOT NULL,
    module_code NVARCHAR(50) NOT NULL
);
GO

CREATE TABLE dbo.group_permissions (
    id BIGINT IDENTITY(1,1) CONSTRAINT PK_group_permissions PRIMARY KEY,
    group_id BIGINT NOT NULL,
    permission_id BIGINT NOT NULL,
    CONSTRAINT FK_gp_group FOREIGN KEY(group_id) REFERENCES dbo.user_groups(id),
    CONSTRAINT FK_gp_permission FOREIGN KEY(permission_id) REFERENCES dbo.permissions(id),
    CONSTRAINT UQ_gp UNIQUE(group_id, permission_id)
);
GO

CREATE TABLE dbo.audit_logs (
    id BIGINT IDENTITY(1,1) CONSTRAINT PK_audit_logs PRIMARY KEY,
    user_id BIGINT NULL,
    action_code NVARCHAR(120) NOT NULL,
    entity_name NVARCHAR(120) NULL,
    entity_id BIGINT NULL,
    detail NVARCHAR(MAX) NULL,
    created_at DATETIME2 NOT NULL CONSTRAINT DF_audit_created DEFAULT SYSUTCDATETIME(),
    CONSTRAINT FK_audit_user FOREIGN KEY(user_id) REFERENCES dbo.users(id)
);
GO

/* =========================================================
   MASTER DATA
   ========================================================= */

CREATE TABLE dbo.number_ranges (
    id BIGINT IDENTITY(1,1) CONSTRAINT PK_number_ranges PRIMARY KEY,
    object_code NVARCHAR(50) NOT NULL,
    subkey NVARCHAR(50) NOT NULL CONSTRAINT DF_nr_subkey DEFAULT N'',
    prefix_template NVARCHAR(120) NOT NULL,
    next_no BIGINT NOT NULL CONSTRAINT DF_nr_next DEFAULT 1,
    width INT NOT NULL CONSTRAINT DF_nr_width DEFAULT 5,
    year_mode BIT NOT NULL CONSTRAINT DF_nr_year DEFAULT 1,
    last_year INT NULL,
    allow_manual BIT NOT NULL CONSTRAINT DF_nr_manual DEFAULT 1,
    is_active BIT NOT NULL CONSTRAINT DF_nr_active DEFAULT 1,
    CONSTRAINT UQ_number_ranges UNIQUE(object_code, subkey)
);
GO

CREATE TABLE dbo.coa_nodes (
    id BIGINT IDENTITY(1,1) CONSTRAINT PK_coa_nodes PRIMARY KEY,
    node_code NVARCHAR(50) NOT NULL CONSTRAINT UQ_coa_node_code UNIQUE,
    node_name NVARCHAR(200) NOT NULL,
    report_section NVARCHAR(50) NOT NULL, -- BALANCE_SHEET / P_AND_L / CASH_FLOW / OTHER
    node_type NVARCHAR(50) NOT NULL CONSTRAINT DF_coa_node_type DEFAULT N'HEADER', -- HEADER / TOTAL / POSTING_GROUP
    parent_node_id BIGINT NULL,
    normal_balance NVARCHAR(20) NULL, -- DEBIT / CREDIT
    sequence_no INT NOT NULL CONSTRAINT DF_coa_node_seq DEFAULT 10,
    is_active BIT NOT NULL CONSTRAINT DF_coa_node_active DEFAULT 1,
    CONSTRAINT FK_coa_node_parent FOREIGN KEY(parent_node_id) REFERENCES dbo.coa_nodes(id)
);
GO

CREATE TABLE dbo.chart_accounts (
    id BIGINT IDENTITY(1,1) CONSTRAINT PK_chart_accounts PRIMARY KEY,
    account_code NVARCHAR(30) NOT NULL CONSTRAINT UQ_coa_code UNIQUE,
    account_name NVARCHAR(200) NOT NULL,
    account_type NVARCHAR(50) NOT NULL,
    account_group NVARCHAR(50) NULL,
    normal_balance NVARCHAR(20) NULL,
    coa_node_id BIGINT NULL,
    is_open_item BIT NOT NULL CONSTRAINT DF_gl_open_item DEFAULT 0,
    open_item_type NVARCHAR(30) NOT NULL CONSTRAINT DF_gl_open_type DEFAULT N'NONE', -- NONE / CUSTOMER / VENDOR / EMPLOYEE / OTHER
    posting_allowed BIT NOT NULL CONSTRAINT DF_gl_posting_allowed DEFAULT 1,
    is_active BIT NOT NULL CONSTRAINT DF_coa_active DEFAULT 1,
    CONSTRAINT FK_gl_coa_node FOREIGN KEY(coa_node_id) REFERENCES dbo.coa_nodes(id)
);
GO

CREATE TABLE dbo.tax_codes (
    id BIGINT IDENTITY(1,1) CONSTRAINT PK_tax_codes PRIMARY KEY,
    tax_code NVARCHAR(30) NOT NULL CONSTRAINT UQ_tax_code UNIQUE,
    tax_name NVARCHAR(200) NOT NULL,
    tax_type NVARCHAR(20) NOT NULL CONSTRAINT DF_tax_codes_tax_type DEFAULT N'INPUT', -- INPUT / OUTPUT
    rate DECIMAL(9,4) NOT NULL CONSTRAINT DF_tax_rate DEFAULT 0,
    vat_account_id BIGINT NULL,
    -- Legacy columns kept for backward compatibility with older reports/migrations.
    input_account_id BIGINT NULL,
    output_account_id BIGINT NULL,
    is_active BIT NOT NULL CONSTRAINT DF_tax_active DEFAULT 1,
    CONSTRAINT FK_tax_vat_account FOREIGN KEY(vat_account_id) REFERENCES dbo.chart_accounts(id),
    CONSTRAINT FK_tax_input_account FOREIGN KEY(input_account_id) REFERENCES dbo.chart_accounts(id),
    CONSTRAINT FK_tax_output_account FOREIGN KEY(output_account_id) REFERENCES dbo.chart_accounts(id),
    CONSTRAINT CK_tax_codes_tax_type CHECK (tax_type IN (N'INPUT', N'OUTPUT'))
);
GO

CREATE TABLE dbo.warehouses (
    id BIGINT IDENTITY(1,1) CONSTRAINT PK_warehouses PRIMARY KEY,
    warehouse_code NVARCHAR(30) NOT NULL CONSTRAINT UQ_wh_code UNIQUE,
    warehouse_name NVARCHAR(200) NOT NULL,
    warehouse_type NVARCHAR(50) NOT NULL CONSTRAINT DF_wh_type DEFAULT N'MAIN',
    is_active BIT NOT NULL CONSTRAINT DF_wh_active DEFAULT 1
);
GO

CREATE TABLE dbo.business_partners (
    id BIGINT IDENTITY(1,1) CONSTRAINT PK_business_partners PRIMARY KEY,
    bp_code NVARCHAR(50) NOT NULL CONSTRAINT UQ_bp_code UNIQUE,
    bp_name NVARCHAR(250) NOT NULL,
    bp_type NVARCHAR(20) NOT NULL, -- CUSTOMER / VENDOR / BOTH
    bp_category NVARCHAR(30) NOT NULL CONSTRAINT DF_bp_category DEFAULT N'COMPANY', -- COMPANY / INDIVIDUAL / BANK / ONE_TIME
    phone NVARCHAR(50) NULL,
    email NVARCHAR(200) NULL,
    address_line NVARCHAR(500) NULL,
    tax_no NVARCHAR(100) NULL,
    payment_terms NVARCHAR(80) NULL,
    currency_code NVARCHAR(10) NOT NULL CONSTRAINT DF_bp_currency DEFAULT N'VND',
    ar_account_id BIGINT NULL,
    ap_account_id BIGINT NULL,
    is_active BIT NOT NULL CONSTRAINT DF_bp_active DEFAULT 1,
    CONSTRAINT FK_bp_ar FOREIGN KEY(ar_account_id) REFERENCES dbo.chart_accounts(id),
    CONSTRAINT FK_bp_ap FOREIGN KEY(ap_account_id) REFERENCES dbo.chart_accounts(id),
    CONSTRAINT CK_bp_category CHECK (bp_category IN (N'COMPANY', N'INDIVIDUAL', N'BANK', N'ONE_TIME'))
);
GO

CREATE TABLE dbo.sale_channels (
    id BIGINT IDENTITY(1,1) CONSTRAINT PK_sale_channels PRIMARY KEY,
    channel_code NVARCHAR(50) NOT NULL CONSTRAINT UQ_sale_channels_code UNIQUE,
    channel_name NVARCHAR(200) NOT NULL,
    channel_type NVARCHAR(50) NOT NULL CONSTRAINT DF_sale_channel_type DEFAULT N'RETAIL',
    external_source NVARCHAR(100) NULL,
    default_customer_id BIGINT NULL,
    default_warehouse_id BIGINT NULL,
    revenue_account_id BIGINT NULL,
    discount_account_id BIGINT NULL,
    fee_account_id BIGINT NULL,
    default_tax_code_id BIGINT NULL,
    default_tax_rate DECIMAL(9,4) NOT NULL CONSTRAINT DF_sale_channel_tax DEFAULT 10, -- legacy fallback; use default_tax_code_id for new logic
    is_active BIT NOT NULL CONSTRAINT DF_sale_channels_active DEFAULT 1,
    CONSTRAINT FK_sale_channel_customer FOREIGN KEY(default_customer_id) REFERENCES dbo.business_partners(id),
    CONSTRAINT FK_sale_channel_warehouse FOREIGN KEY(default_warehouse_id) REFERENCES dbo.warehouses(id),
    CONSTRAINT FK_sale_channel_revenue_account FOREIGN KEY(revenue_account_id) REFERENCES dbo.chart_accounts(id),
    CONSTRAINT FK_sale_channel_discount_account FOREIGN KEY(discount_account_id) REFERENCES dbo.chart_accounts(id),
    CONSTRAINT FK_sale_channel_fee_account FOREIGN KEY(fee_account_id) REFERENCES dbo.chart_accounts(id),
    CONSTRAINT FK_sale_channel_tax_code FOREIGN KEY(default_tax_code_id) REFERENCES dbo.tax_codes(id)
);
GO

CREATE TABLE dbo.items (
    id BIGINT IDENTITY(1,1) CONSTRAINT PK_items PRIMARY KEY,
    item_code NVARCHAR(50) NOT NULL CONSTRAINT UQ_item_code UNIQUE,
    item_name NVARCHAR(250) NOT NULL,
    item_type NVARCHAR(30) NOT NULL, -- RAW, PACKAGING, FINISHED, RESALE, SERVICE
    base_uom NVARCHAR(30) NOT NULL,
    purchase_uom NVARCHAR(30) NULL,
    sales_uom NVARCHAR(30) NULL,
    standard_cost DECIMAL(19,4) NOT NULL CONSTRAINT DF_item_std_cost DEFAULT 0,
    sales_price DECIMAL(19,4) NULL CONSTRAINT DF_item_sales_price DEFAULT 0,
    input_tax_code_id BIGINT NULL,
    output_tax_code_id BIGINT NULL,
    inventory_account_id BIGINT NULL,
    cogs_account_id BIGINT NULL,
    revenue_account_id BIGINT NULL,
    wip_account_id BIGINT NULL,
    expiry_tracking BIT NOT NULL CONSTRAINT DF_item_expiry DEFAULT 0,
    lot_tracking BIT NOT NULL CONSTRAINT DF_item_lot DEFAULT 0,
    is_active BIT NOT NULL CONSTRAINT DF_item_active DEFAULT 1,
    CONSTRAINT FK_item_inv FOREIGN KEY(inventory_account_id) REFERENCES dbo.chart_accounts(id),
    CONSTRAINT FK_item_cogs FOREIGN KEY(cogs_account_id) REFERENCES dbo.chart_accounts(id),
    CONSTRAINT FK_item_rev FOREIGN KEY(revenue_account_id) REFERENCES dbo.chart_accounts(id),
    CONSTRAINT FK_item_wip FOREIGN KEY(wip_account_id) REFERENCES dbo.chart_accounts(id),
    CONSTRAINT FK_items_input_tax_code FOREIGN KEY(input_tax_code_id) REFERENCES dbo.tax_codes(id),
    CONSTRAINT FK_items_output_tax_code FOREIGN KEY(output_tax_code_id) REFERENCES dbo.tax_codes(id)
);
GO

CREATE TABLE dbo.boms (
    id BIGINT IDENTITY(1,1) CONSTRAINT PK_boms PRIMARY KEY,
    bom_code NVARCHAR(50) NOT NULL CONSTRAINT UQ_bom_code UNIQUE,
    finished_item_id BIGINT NOT NULL,
    version_no NVARCHAR(30) NOT NULL CONSTRAINT DF_bom_version DEFAULT N'V1',
    base_qty DECIMAL(19,4) NOT NULL CONSTRAINT DF_bom_base_qty DEFAULT 1,
    is_active BIT NOT NULL CONSTRAINT DF_bom_active DEFAULT 1,
    CONSTRAINT FK_bom_item FOREIGN KEY(finished_item_id) REFERENCES dbo.items(id)
);
GO

CREATE TABLE dbo.bom_components (
    id BIGINT IDENTITY(1,1) CONSTRAINT PK_bom_components PRIMARY KEY,
    bom_id BIGINT NOT NULL,
    component_item_id BIGINT NOT NULL,
    qty_per DECIMAL(19,6) NOT NULL,
    scrap_percent DECIMAL(9,4) NOT NULL CONSTRAINT DF_bom_comp_scrap DEFAULT 0,
    CONSTRAINT FK_bom_comp_bom FOREIGN KEY(bom_id) REFERENCES dbo.boms(id),
    CONSTRAINT FK_bom_comp_item FOREIGN KEY(component_item_id) REFERENCES dbo.items(id)
);
GO

/* =========================================================
   INVENTORY
   ========================================================= */

CREATE TABLE dbo.inventory_movements (
    id BIGINT IDENTITY(1,1) CONSTRAINT PK_inventory_movements PRIMARY KEY,
    movement_no NVARCHAR(50) NOT NULL CONSTRAINT UQ_inv_movement_no UNIQUE,
    movement_date DATE NOT NULL,
    movement_type NVARCHAR(50) NOT NULL, -- PURCHASE_RECEIPT, SALE_ISSUE, PRODUCTION_ISSUE, PRODUCTION_RECEIPT, ADJUSTMENT, TRANSFER
    source_doc_type NVARCHAR(50) NULL,
    source_doc_id BIGINT NULL,
    item_id BIGINT NOT NULL,
    warehouse_id BIGINT NOT NULL,
    lot_no NVARCHAR(100) NULL,
    expiry_date DATE NULL,
    qty_in DECIMAL(19,4) NOT NULL CONSTRAINT DF_inv_qty_in DEFAULT 0,
    qty_out DECIMAL(19,4) NOT NULL CONSTRAINT DF_inv_qty_out DEFAULT 0,
    unit_cost DECIMAL(19,4) NOT NULL CONSTRAINT DF_inv_unit_cost DEFAULT 0,
    amount DECIMAL(19,4) NOT NULL CONSTRAINT DF_inv_amount DEFAULT 0,
    notes NVARCHAR(500) NULL,
    created_at DATETIME2 NOT NULL CONSTRAINT DF_inv_created DEFAULT SYSUTCDATETIME(),
    CONSTRAINT FK_inv_item FOREIGN KEY(item_id) REFERENCES dbo.items(id),
    CONSTRAINT FK_inv_wh FOREIGN KEY(warehouse_id) REFERENCES dbo.warehouses(id)
);
GO

CREATE INDEX IX_inventory_movements_item_wh_date ON dbo.inventory_movements(item_id, warehouse_id, movement_date);
GO

/* =========================================================
   PURCHASING
   ========================================================= */

CREATE TABLE dbo.purchase_orders (
    id BIGINT IDENTITY(1,1) CONSTRAINT PK_purchase_orders PRIMARY KEY,
    po_no NVARCHAR(50) NOT NULL CONSTRAINT UQ_po_no UNIQUE,
    po_date DATE NOT NULL,
    vendor_id BIGINT NOT NULL,
    status NVARCHAR(30) NOT NULL CONSTRAINT DF_po_status DEFAULT N'DRAFT',
    currency_code NVARCHAR(10) NOT NULL CONSTRAINT DF_po_currency DEFAULT N'VND',
    total_amount DECIMAL(19,4) NOT NULL CONSTRAINT DF_po_total DEFAULT 0,
    tax_amount DECIMAL(19,4) NOT NULL CONSTRAINT DF_po_tax DEFAULT 0,
    grand_total DECIMAL(19,4) NOT NULL CONSTRAINT DF_po_grand DEFAULT 0,
    created_by BIGINT NULL,
    created_at DATETIME2 NOT NULL CONSTRAINT DF_po_created DEFAULT SYSUTCDATETIME(),
    CONSTRAINT FK_po_vendor FOREIGN KEY(vendor_id) REFERENCES dbo.business_partners(id),
    CONSTRAINT FK_po_created_by FOREIGN KEY(created_by) REFERENCES dbo.users(id)
);
GO

CREATE TABLE dbo.purchase_order_lines (
    id BIGINT IDENTITY(1,1) CONSTRAINT PK_purchase_order_lines PRIMARY KEY,
    po_id BIGINT NOT NULL,
    line_no INT NOT NULL,
    item_id BIGINT NOT NULL,
    warehouse_id BIGINT NOT NULL,
    quantity DECIMAL(19,4) NOT NULL,
    unit_price DECIMAL(19,4) NOT NULL,
    tax_code_id BIGINT NULL,
    line_amount DECIMAL(19,4) NOT NULL,
    tax_amount DECIMAL(19,4) NOT NULL CONSTRAINT DF_pol_tax DEFAULT 0,
    CONSTRAINT FK_pol_po FOREIGN KEY(po_id) REFERENCES dbo.purchase_orders(id),
    CONSTRAINT FK_pol_item FOREIGN KEY(item_id) REFERENCES dbo.items(id),
    CONSTRAINT FK_pol_wh FOREIGN KEY(warehouse_id) REFERENCES dbo.warehouses(id),
    CONSTRAINT FK_pol_tax FOREIGN KEY(tax_code_id) REFERENCES dbo.tax_codes(id)
);
GO

CREATE TABLE dbo.goods_receipts (
    id BIGINT IDENTITY(1,1) CONSTRAINT PK_goods_receipts PRIMARY KEY,
    gr_no NVARCHAR(50) NOT NULL CONSTRAINT UQ_gr_no UNIQUE,
    gr_date DATE NOT NULL,
    po_id BIGINT NULL,
    vendor_id BIGINT NOT NULL,
    status NVARCHAR(30) NOT NULL CONSTRAINT DF_gr_status DEFAULT N'POSTED',
    created_by BIGINT NULL,
    created_at DATETIME2 NOT NULL CONSTRAINT DF_gr_created DEFAULT SYSUTCDATETIME(),
    CONSTRAINT FK_gr_po FOREIGN KEY(po_id) REFERENCES dbo.purchase_orders(id),
    CONSTRAINT FK_gr_vendor FOREIGN KEY(vendor_id) REFERENCES dbo.business_partners(id),
    CONSTRAINT FK_gr_created_by FOREIGN KEY(created_by) REFERENCES dbo.users(id)
);
GO

CREATE TABLE dbo.goods_receipt_lines (
    id BIGINT IDENTITY(1,1) CONSTRAINT PK_goods_receipt_lines PRIMARY KEY,
    gr_id BIGINT NOT NULL,
    po_line_id BIGINT NULL,
    item_id BIGINT NOT NULL,
    warehouse_id BIGINT NOT NULL,
    quantity DECIMAL(19,4) NOT NULL,
    unit_cost DECIMAL(19,4) NOT NULL,
    lot_no NVARCHAR(100) NULL,
    expiry_date DATE NULL,
    CONSTRAINT FK_grl_gr FOREIGN KEY(gr_id) REFERENCES dbo.goods_receipts(id),
    CONSTRAINT FK_grl_po_line FOREIGN KEY(po_line_id) REFERENCES dbo.purchase_order_lines(id),
    CONSTRAINT FK_grl_item FOREIGN KEY(item_id) REFERENCES dbo.items(id),
    CONSTRAINT FK_grl_wh FOREIGN KEY(warehouse_id) REFERENCES dbo.warehouses(id)
);
GO

CREATE TABLE dbo.ap_invoices (
    id BIGINT IDENTITY(1,1) CONSTRAINT PK_ap_invoices PRIMARY KEY,
    ap_no NVARCHAR(50) NOT NULL CONSTRAINT UQ_ap_no UNIQUE,
    ap_date DATE NOT NULL,
    vendor_id BIGINT NOT NULL,
    gr_id BIGINT NULL,
    status NVARCHAR(30) NOT NULL CONSTRAINT DF_ap_status DEFAULT N'POSTED',
    total_amount DECIMAL(19,4) NOT NULL CONSTRAINT DF_ap_total DEFAULT 0,
    tax_amount DECIMAL(19,4) NOT NULL CONSTRAINT DF_ap_tax DEFAULT 0,
    grand_total DECIMAL(19,4) NOT NULL CONSTRAINT DF_ap_grand DEFAULT 0,
    journal_entry_id BIGINT NULL,
    CONSTRAINT FK_ap_vendor FOREIGN KEY(vendor_id) REFERENCES dbo.business_partners(id),
    CONSTRAINT FK_ap_gr FOREIGN KEY(gr_id) REFERENCES dbo.goods_receipts(id)
);
GO

CREATE TABLE dbo.ap_invoice_lines (
    id BIGINT IDENTITY(1,1) CONSTRAINT PK_ap_invoice_lines PRIMARY KEY,
    ap_id BIGINT NOT NULL,
    item_id BIGINT NULL,
    account_id BIGINT NULL,
    quantity DECIMAL(19,4) NOT NULL CONSTRAINT DF_apl_qty DEFAULT 0,
    unit_price DECIMAL(19,4) NOT NULL CONSTRAINT DF_apl_unit DEFAULT 0,
    line_amount DECIMAL(19,4) NOT NULL,
    tax_code_id BIGINT NULL,
    tax_amount DECIMAL(19,4) NOT NULL CONSTRAINT DF_apl_tax DEFAULT 0,
    CONSTRAINT FK_apl_ap FOREIGN KEY(ap_id) REFERENCES dbo.ap_invoices(id),
    CONSTRAINT FK_apl_item FOREIGN KEY(item_id) REFERENCES dbo.items(id),
    CONSTRAINT FK_apl_account FOREIGN KEY(account_id) REFERENCES dbo.chart_accounts(id),
    CONSTRAINT FK_apl_tax FOREIGN KEY(tax_code_id) REFERENCES dbo.tax_codes(id)
);
GO

CREATE TABLE dbo.vendor_payments (
    id BIGINT IDENTITY(1,1) CONSTRAINT PK_vendor_payments PRIMARY KEY,
    payment_no NVARCHAR(50) NOT NULL CONSTRAINT UQ_vendor_payment_no UNIQUE,
    payment_date DATE NOT NULL,
    vendor_id BIGINT NOT NULL,
    ap_invoice_id BIGINT NULL,
    cash_bank_account_id BIGINT NOT NULL,
    amount DECIMAL(19,4) NOT NULL,
    journal_entry_id BIGINT NULL,
    CONSTRAINT FK_vp_vendor FOREIGN KEY(vendor_id) REFERENCES dbo.business_partners(id),
    CONSTRAINT FK_vp_ap FOREIGN KEY(ap_invoice_id) REFERENCES dbo.ap_invoices(id),
    CONSTRAINT FK_vp_account FOREIGN KEY(cash_bank_account_id) REFERENCES dbo.chart_accounts(id)
);
GO

/* =========================================================
   SALES
   ========================================================= */

CREATE TABLE dbo.sales_orders (
    id BIGINT IDENTITY(1,1) CONSTRAINT PK_sales_orders PRIMARY KEY,
    so_no NVARCHAR(50) NOT NULL CONSTRAINT UQ_so_no UNIQUE,
    so_date DATE NOT NULL,
    customer_id BIGINT NOT NULL,
    status NVARCHAR(30) NOT NULL CONSTRAINT DF_so_status DEFAULT N'DRAFT',
    channel_code NVARCHAR(50) NULL, -- RETAIL / ONLINE / POS / WHOLESALE
    total_amount DECIMAL(19,4) NOT NULL CONSTRAINT DF_so_total DEFAULT 0,
    tax_amount DECIMAL(19,4) NOT NULL CONSTRAINT DF_so_tax DEFAULT 0,
    grand_total DECIMAL(19,4) NOT NULL CONSTRAINT DF_so_grand DEFAULT 0,
    external_ref NVARCHAR(100) NULL,
    created_by BIGINT NULL,
    created_at DATETIME2 NOT NULL CONSTRAINT DF_so_created DEFAULT SYSUTCDATETIME(),
    CONSTRAINT FK_so_customer FOREIGN KEY(customer_id) REFERENCES dbo.business_partners(id),
    CONSTRAINT FK_so_created_by FOREIGN KEY(created_by) REFERENCES dbo.users(id)
);
GO

CREATE TABLE dbo.sales_order_lines (
    id BIGINT IDENTITY(1,1) CONSTRAINT PK_sales_order_lines PRIMARY KEY,
    so_id BIGINT NOT NULL,
    line_no INT NOT NULL,
    item_id BIGINT NOT NULL,
    warehouse_id BIGINT NOT NULL,
    quantity DECIMAL(19,4) NOT NULL,
    unit_price DECIMAL(19,4) NOT NULL,
    discount_amount DECIMAL(19,4) NOT NULL CONSTRAINT DF_sol_discount DEFAULT 0,
    tax_code_id BIGINT NULL,
    line_amount DECIMAL(19,4) NOT NULL,
    tax_amount DECIMAL(19,4) NOT NULL CONSTRAINT DF_sol_tax DEFAULT 0,
    CONSTRAINT FK_sol_so FOREIGN KEY(so_id) REFERENCES dbo.sales_orders(id),
    CONSTRAINT FK_sol_item FOREIGN KEY(item_id) REFERENCES dbo.items(id),
    CONSTRAINT FK_sol_wh FOREIGN KEY(warehouse_id) REFERENCES dbo.warehouses(id),
    CONSTRAINT FK_sol_tax FOREIGN KEY(tax_code_id) REFERENCES dbo.tax_codes(id)
);
GO

CREATE TABLE dbo.deliveries (
    id BIGINT IDENTITY(1,1) CONSTRAINT PK_deliveries PRIMARY KEY,
    delivery_no NVARCHAR(50) NOT NULL CONSTRAINT UQ_delivery_no UNIQUE,
    delivery_date DATE NOT NULL,
    so_id BIGINT NULL,
    customer_id BIGINT NOT NULL,
    status NVARCHAR(30) NOT NULL CONSTRAINT DF_delivery_status DEFAULT N'POSTED',
    journal_entry_id BIGINT NULL,
    CONSTRAINT FK_delivery_so FOREIGN KEY(so_id) REFERENCES dbo.sales_orders(id),
    CONSTRAINT FK_delivery_customer FOREIGN KEY(customer_id) REFERENCES dbo.business_partners(id)
);
GO

CREATE TABLE dbo.delivery_lines (
    id BIGINT IDENTITY(1,1) CONSTRAINT PK_delivery_lines PRIMARY KEY,
    delivery_id BIGINT NOT NULL,
    so_line_id BIGINT NULL,
    item_id BIGINT NOT NULL,
    warehouse_id BIGINT NOT NULL,
    quantity DECIMAL(19,4) NOT NULL,
    unit_cost DECIMAL(19,4) NOT NULL,
    lot_no NVARCHAR(100) NULL,
    CONSTRAINT FK_dlv_line_delivery FOREIGN KEY(delivery_id) REFERENCES dbo.deliveries(id),
    CONSTRAINT FK_dlv_line_so FOREIGN KEY(so_line_id) REFERENCES dbo.sales_order_lines(id),
    CONSTRAINT FK_dlv_line_item FOREIGN KEY(item_id) REFERENCES dbo.items(id),
    CONSTRAINT FK_dlv_line_wh FOREIGN KEY(warehouse_id) REFERENCES dbo.warehouses(id)
);
GO

CREATE TABLE dbo.ar_invoices (
    id BIGINT IDENTITY(1,1) CONSTRAINT PK_ar_invoices PRIMARY KEY,
    ar_no NVARCHAR(50) NOT NULL CONSTRAINT UQ_ar_no UNIQUE,
    ar_date DATE NOT NULL,
    customer_id BIGINT NOT NULL,
    delivery_id BIGINT NULL,
    status NVARCHAR(30) NOT NULL CONSTRAINT DF_ar_status DEFAULT N'POSTED',
    total_amount DECIMAL(19,4) NOT NULL CONSTRAINT DF_ar_total DEFAULT 0,
    tax_amount DECIMAL(19,4) NOT NULL CONSTRAINT DF_ar_tax DEFAULT 0,
    grand_total DECIMAL(19,4) NOT NULL CONSTRAINT DF_ar_grand DEFAULT 0,
    journal_entry_id BIGINT NULL,
    external_ref NVARCHAR(100) NULL,
    CONSTRAINT FK_ar_customer FOREIGN KEY(customer_id) REFERENCES dbo.business_partners(id),
    CONSTRAINT FK_ar_delivery FOREIGN KEY(delivery_id) REFERENCES dbo.deliveries(id)
);
GO

CREATE TABLE dbo.ar_invoice_lines (
    id BIGINT IDENTITY(1,1) CONSTRAINT PK_ar_invoice_lines PRIMARY KEY,
    ar_id BIGINT NOT NULL,
    item_id BIGINT NOT NULL,
    quantity DECIMAL(19,4) NOT NULL,
    unit_price DECIMAL(19,4) NOT NULL,
    discount_amount DECIMAL(19,4) NOT NULL CONSTRAINT DF_arl_discount DEFAULT 0,
    line_amount DECIMAL(19,4) NOT NULL,
    tax_code_id BIGINT NULL,
    tax_amount DECIMAL(19,4) NOT NULL CONSTRAINT DF_arl_tax DEFAULT 0,
    CONSTRAINT FK_arl_ar FOREIGN KEY(ar_id) REFERENCES dbo.ar_invoices(id),
    CONSTRAINT FK_arl_item FOREIGN KEY(item_id) REFERENCES dbo.items(id),
    CONSTRAINT FK_arl_tax FOREIGN KEY(tax_code_id) REFERENCES dbo.tax_codes(id)
);
GO

CREATE TABLE dbo.customer_receipts (
    id BIGINT IDENTITY(1,1) CONSTRAINT PK_customer_receipts PRIMARY KEY,
    receipt_no NVARCHAR(50) NOT NULL CONSTRAINT UQ_customer_receipt_no UNIQUE,
    receipt_date DATE NOT NULL,
    customer_id BIGINT NOT NULL,
    ar_invoice_id BIGINT NULL,
    cash_bank_account_id BIGINT NOT NULL,
    amount DECIMAL(19,4) NOT NULL,
    journal_entry_id BIGINT NULL,
    CONSTRAINT FK_cr_customer FOREIGN KEY(customer_id) REFERENCES dbo.business_partners(id),
    CONSTRAINT FK_cr_ar FOREIGN KEY(ar_invoice_id) REFERENCES dbo.ar_invoices(id),
    CONSTRAINT FK_cr_account FOREIGN KEY(cash_bank_account_id) REFERENCES dbo.chart_accounts(id)
);
GO

/* =========================================================
   PRODUCTION
   ========================================================= */

CREATE TABLE dbo.production_orders (
    id BIGINT IDENTITY(1,1) CONSTRAINT PK_production_orders PRIMARY KEY,
    prod_no NVARCHAR(50) NOT NULL CONSTRAINT UQ_prod_no UNIQUE,
    prod_date DATE NOT NULL,
    finished_item_id BIGINT NOT NULL,
    bom_id BIGINT NULL,
    planned_qty DECIMAL(19,4) NOT NULL,
    completed_qty DECIMAL(19,4) NOT NULL CONSTRAINT DF_prod_completed DEFAULT 0,
    status NVARCHAR(30) NOT NULL CONSTRAINT DF_prod_status DEFAULT N'DRAFT',
    issue_warehouse_id BIGINT NOT NULL,
    receipt_warehouse_id BIGINT NOT NULL,
    created_by BIGINT NULL,
    created_at DATETIME2 NOT NULL CONSTRAINT DF_prod_created DEFAULT SYSUTCDATETIME(),
    CONSTRAINT FK_prod_finished_item FOREIGN KEY(finished_item_id) REFERENCES dbo.items(id),
    CONSTRAINT FK_prod_bom FOREIGN KEY(bom_id) REFERENCES dbo.boms(id),
    CONSTRAINT FK_prod_issue_wh FOREIGN KEY(issue_warehouse_id) REFERENCES dbo.warehouses(id),
    CONSTRAINT FK_prod_receipt_wh FOREIGN KEY(receipt_warehouse_id) REFERENCES dbo.warehouses(id),
    CONSTRAINT FK_prod_created_by FOREIGN KEY(created_by) REFERENCES dbo.users(id)
);
GO

CREATE TABLE dbo.production_order_lines (
    id BIGINT IDENTITY(1,1) CONSTRAINT PK_production_order_lines PRIMARY KEY,
    production_order_id BIGINT NOT NULL,
    component_item_id BIGINT NOT NULL,
    planned_qty DECIMAL(19,4) NOT NULL,
    issued_qty DECIMAL(19,4) NOT NULL CONSTRAINT DF_pol_prod_issued DEFAULT 0,
    CONSTRAINT FK_prod_line_order FOREIGN KEY(production_order_id) REFERENCES dbo.production_orders(id),
    CONSTRAINT FK_prod_line_item FOREIGN KEY(component_item_id) REFERENCES dbo.items(id)
);
GO

CREATE TABLE dbo.material_issues (
    id BIGINT IDENTITY(1,1) CONSTRAINT PK_material_issues PRIMARY KEY,
    issue_no NVARCHAR(50) NOT NULL CONSTRAINT UQ_material_issue_no UNIQUE,
    issue_date DATE NOT NULL,
    production_order_id BIGINT NOT NULL,
    status NVARCHAR(30) NOT NULL CONSTRAINT DF_mi_status DEFAULT N'POSTED',
    journal_entry_id BIGINT NULL,
    CONSTRAINT FK_mi_prod FOREIGN KEY(production_order_id) REFERENCES dbo.production_orders(id)
);
GO

CREATE TABLE dbo.material_issue_lines (
    id BIGINT IDENTITY(1,1) CONSTRAINT PK_material_issue_lines PRIMARY KEY,
    material_issue_id BIGINT NOT NULL,
    item_id BIGINT NOT NULL,
    warehouse_id BIGINT NOT NULL,
    quantity DECIMAL(19,4) NOT NULL,
    unit_cost DECIMAL(19,4) NOT NULL,
    CONSTRAINT FK_mil_issue FOREIGN KEY(material_issue_id) REFERENCES dbo.material_issues(id),
    CONSTRAINT FK_mil_item FOREIGN KEY(item_id) REFERENCES dbo.items(id),
    CONSTRAINT FK_mil_wh FOREIGN KEY(warehouse_id) REFERENCES dbo.warehouses(id)
);
GO

CREATE TABLE dbo.production_receipts (
    id BIGINT IDENTITY(1,1) CONSTRAINT PK_production_receipts PRIMARY KEY,
    receipt_no NVARCHAR(50) NOT NULL CONSTRAINT UQ_production_receipt_no UNIQUE,
    receipt_date DATE NOT NULL,
    production_order_id BIGINT NOT NULL,
    status NVARCHAR(30) NOT NULL CONSTRAINT DF_pr_status DEFAULT N'POSTED',
    journal_entry_id BIGINT NULL,
    CONSTRAINT FK_pr_prod FOREIGN KEY(production_order_id) REFERENCES dbo.production_orders(id)
);
GO

CREATE TABLE dbo.production_receipt_lines (
    id BIGINT IDENTITY(1,1) CONSTRAINT PK_production_receipt_lines PRIMARY KEY,
    production_receipt_id BIGINT NOT NULL,
    item_id BIGINT NOT NULL,
    warehouse_id BIGINT NOT NULL,
    quantity DECIMAL(19,4) NOT NULL,
    unit_cost DECIMAL(19,4) NOT NULL,
    lot_no NVARCHAR(100) NULL,
    expiry_date DATE NULL,
    CONSTRAINT FK_prl_receipt FOREIGN KEY(production_receipt_id) REFERENCES dbo.production_receipts(id),
    CONSTRAINT FK_prl_item FOREIGN KEY(item_id) REFERENCES dbo.items(id),
    CONSTRAINT FK_prl_wh FOREIGN KEY(warehouse_id) REFERENCES dbo.warehouses(id)
);
GO

/* =========================================================
   ACCOUNTING
   ========================================================= */

CREATE TABLE dbo.journal_entries (
    id BIGINT IDENTITY(1,1) CONSTRAINT PK_journal_entries PRIMARY KEY,
    je_no NVARCHAR(50) NOT NULL CONSTRAINT UQ_je_no UNIQUE,
    je_date DATE NOT NULL,
    source_doc_type NVARCHAR(50) NULL,
    source_doc_id BIGINT NULL,
    memo NVARCHAR(500) NULL,
    status NVARCHAR(30) NOT NULL CONSTRAINT DF_je_status DEFAULT N'POSTED',
    created_by BIGINT NULL,
    created_at DATETIME2 NOT NULL CONSTRAINT DF_je_created DEFAULT SYSUTCDATETIME(),
    CONSTRAINT FK_je_created_by FOREIGN KEY(created_by) REFERENCES dbo.users(id)
);
GO

CREATE TABLE dbo.journal_entry_lines (
    id BIGINT IDENTITY(1,1) CONSTRAINT PK_journal_entry_lines PRIMARY KEY,
    journal_entry_id BIGINT NOT NULL,
    line_no INT NOT NULL,
    account_id BIGINT NOT NULL,
    debit DECIMAL(19,4) NOT NULL CONSTRAINT DF_jel_debit DEFAULT 0,
    credit DECIMAL(19,4) NOT NULL CONSTRAINT DF_jel_credit DEFAULT 0,
    bp_id BIGINT NULL,
    item_id BIGINT NULL,
    memo NVARCHAR(500) NULL,
    CONSTRAINT FK_jel_je FOREIGN KEY(journal_entry_id) REFERENCES dbo.journal_entries(id),
    CONSTRAINT FK_jel_account FOREIGN KEY(account_id) REFERENCES dbo.chart_accounts(id),
    CONSTRAINT FK_jel_bp FOREIGN KEY(bp_id) REFERENCES dbo.business_partners(id),
    CONSTRAINT FK_jel_item FOREIGN KEY(item_id) REFERENCES dbo.items(id)
);
GO

ALTER TABLE dbo.ap_invoices ADD CONSTRAINT FK_ap_je FOREIGN KEY(journal_entry_id) REFERENCES dbo.journal_entries(id);
ALTER TABLE dbo.ar_invoices ADD CONSTRAINT FK_ar_je FOREIGN KEY(journal_entry_id) REFERENCES dbo.journal_entries(id);
ALTER TABLE dbo.deliveries ADD CONSTRAINT FK_delivery_je FOREIGN KEY(journal_entry_id) REFERENCES dbo.journal_entries(id);
ALTER TABLE dbo.vendor_payments ADD CONSTRAINT FK_vp_je FOREIGN KEY(journal_entry_id) REFERENCES dbo.journal_entries(id);
ALTER TABLE dbo.customer_receipts ADD CONSTRAINT FK_cr_je FOREIGN KEY(journal_entry_id) REFERENCES dbo.journal_entries(id);
ALTER TABLE dbo.material_issues ADD CONSTRAINT FK_mi_je FOREIGN KEY(journal_entry_id) REFERENCES dbo.journal_entries(id);
ALTER TABLE dbo.production_receipts ADD CONSTRAINT FK_pr_je FOREIGN KEY(journal_entry_id) REFERENCES dbo.journal_entries(id);
GO

/* =========================================================
   INTEGRATION
   ========================================================= */

CREATE TABLE dbo.integration_connections (
    id BIGINT IDENTITY(1,1) CONSTRAINT PK_integration_connections PRIMARY KEY,
    connection_code NVARCHAR(50) NOT NULL CONSTRAINT UQ_integration_code UNIQUE,
    connection_name NVARCHAR(200) NOT NULL,
    provider NVARCHAR(80) NOT NULL, -- LOYVERSE / CSV_POS / ODOO / CUSTOM
    base_url NVARCHAR(500) NULL,
    api_token_encrypted NVARCHAR(MAX) NULL,
    is_active BIT NOT NULL CONSTRAINT DF_int_active DEFAULT 1,
    created_at DATETIME2 NOT NULL CONSTRAINT DF_int_created DEFAULT SYSUTCDATETIME()
);
GO

CREATE TABLE dbo.integration_sync_logs (
    id BIGINT IDENTITY(1,1) CONSTRAINT PK_integration_sync_logs PRIMARY KEY,
    connection_id BIGINT NOT NULL,
    sync_type NVARCHAR(80) NOT NULL, -- PULL_RECEIPTS / PUSH_STOCK / IMPORT_CSV
    started_at DATETIME2 NOT NULL CONSTRAINT DF_sync_started DEFAULT SYSUTCDATETIME(),
    finished_at DATETIME2 NULL,
    status NVARCHAR(30) NOT NULL CONSTRAINT DF_sync_status DEFAULT N'RUNNING',
    message NVARCHAR(MAX) NULL,
    records_processed INT NOT NULL CONSTRAINT DF_sync_records DEFAULT 0,
    CONSTRAINT FK_sync_connection FOREIGN KEY(connection_id) REFERENCES dbo.integration_connections(id)
);
GO

/* =========================================================
   NUMBER RANGE STORED PROCEDURE
   ========================================================= */

CREATE OR ALTER PROCEDURE dbo.sp_GenerateDocumentNo
    @ObjectCode NVARCHAR(50),
    @Subkey NVARCHAR(50) = N'',
    @DocDate DATE,
    @DocumentNo NVARCHAR(80) OUTPUT
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @CurrentYear INT = YEAR(@DocDate);
    DECLARE @CurrentMonth NVARCHAR(2) = RIGHT('0' + CAST(MONTH(@DocDate) AS NVARCHAR(2)), 2);
    DECLARE @PrefixTemplate NVARCHAR(120);
    DECLARE @NextNo BIGINT;
    DECLARE @Width INT;
    DECLARE @YearMode BIT;
    DECLARE @LastYear INT;
    DECLARE @FormattedNo NVARCHAR(50);

    BEGIN TRAN;

    SELECT
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
    END

    IF @YearMode = 1 AND (ISNULL(@LastYear, 0) <> @CurrentYear)
    BEGIN
        SET @NextNo = 1;
        UPDATE dbo.number_ranges
        SET next_no = 1,
            last_year = @CurrentYear
        WHERE object_code = @ObjectCode AND subkey = ISNULL(@Subkey, N'');
    END

    SET @FormattedNo = RIGHT(REPLICATE('0', @Width) + CAST(@NextNo AS NVARCHAR(50)), @Width);

    SET @DocumentNo = @PrefixTemplate;
    SET @DocumentNo = REPLACE(@DocumentNo, N'{YYYY}', CAST(@CurrentYear AS NVARCHAR(4)));
    SET @DocumentNo = REPLACE(@DocumentNo, N'{YY}', RIGHT(CAST(@CurrentYear AS NVARCHAR(4)), 2));
    SET @DocumentNo = REPLACE(@DocumentNo, N'{MM}', @CurrentMonth);
    SET @DocumentNo = REPLACE(@DocumentNo, N'{SUBKEY}', ISNULL(@Subkey, N''));
    SET @DocumentNo = REPLACE(@DocumentNo, N'{00001}', @FormattedNo);

    UPDATE dbo.number_ranges
    SET next_no = @NextNo + 1,
        last_year = CASE WHEN @YearMode = 1 THEN @CurrentYear ELSE last_year END
    WHERE object_code = @ObjectCode AND subkey = ISNULL(@Subkey, N'');

    COMMIT TRAN;
END
GO

/* =========================================================
   USEFUL VIEWS
   ========================================================= */

CREATE OR ALTER VIEW dbo.v_inventory_balance AS
SELECT
    i.id AS item_id,
    i.item_code,
    i.item_name,
    w.id AS warehouse_id,
    w.warehouse_code,
    SUM(m.qty_in - m.qty_out) AS on_hand_qty,
    SUM(m.amount) AS inventory_value
FROM dbo.inventory_movements m
JOIN dbo.items i ON i.id = m.item_id
JOIN dbo.warehouses w ON w.id = m.warehouse_id
GROUP BY i.id, i.item_code, i.item_name, w.id, w.warehouse_code;
GO

CREATE OR ALTER VIEW dbo.v_trial_balance AS
SELECT
    a.account_code,
    a.account_name,
    SUM(l.debit) AS total_debit,
    SUM(l.credit) AS total_credit,
    SUM(l.debit - l.credit) AS ending_balance
FROM dbo.journal_entry_lines l
JOIN dbo.chart_accounts a ON a.id = l.account_id
JOIN dbo.journal_entries h ON h.id = l.journal_entry_id
WHERE h.status = N'POSTED'
GROUP BY a.account_code, a.account_name;
GO
