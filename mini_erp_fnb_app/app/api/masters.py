from datetime import date
from decimal import Decimal, InvalidOperation
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.permissions import require_permission
from app.core.number_utils import parse_decimal, parse_decimal_strict
from app.services.numbering_service import NumberingService

router = APIRouter(prefix="/masters", tags=["masters"])
templates = Jinja2Templates(directory="app/templates")


# ---------------------------------------------------------------------------
# Master Data metadata
# ---------------------------------------------------------------------------
# The router below is metadata-driven so adding another master table later is easy:
# add a new entry in ENTITY_CONFIG, create permission if needed, then it will get
# list/new/edit/toggle screens automatically.

ITEM_TYPES = ["RAW", "PACKAGING", "FINISHED", "RESALE", "SERVICE"]
BP_TYPES = ["CUSTOMER", "VENDOR", "BOTH"]
BP_CATEGORIES = ["COMPANY", "INDIVIDUAL", "BANK", "ONE_TIME"]
WAREHOUSE_TYPES = ["MAIN", "STORE", "PRODUCTION", "TRANSIT", "WASTE"]
UOM_GROUPS = ["COUNT", "MASS", "VOLUME", "LENGTH", "AREA", "TIME", "SERVICE", "OTHER"]
SALE_CHANNEL_TYPES = ["RETAIL", "POS", "ONLINE", "DELIVERY", "MARKETPLACE", "WHOLESALE", "OTHER"]
ACCOUNT_TYPES = ["ASSET", "LIABILITY", "EQUITY", "REVENUE", "REVENUE_DEDUCTION", "COGS", "EXPENSE", "OTHER"]
GL_ACCOUNT_GROUPS = [
    "CASH_BANK", "AR", "AP", "TAX", "INVENTORY", "WIP", "FIXED_ASSET", "ACCUM_DEPRECIATION",
    "PREPAID_EXPENSE", "TOOL", "REVENUE", "REVENUE_DEDUCTION", "COGS", "DEPRECIATION_EXPENSE", "EXPENSE", "OTHER"
]
NORMAL_BALANCES = ["DEBIT", "CREDIT"]
OPEN_ITEM_TYPES = ["NONE", "CUSTOMER", "VENDOR", "EMPLOYEE", "OTHER"]
COA_REPORT_SECTIONS = ["BALANCE_SHEET", "P_AND_L", "CASH_FLOW", "OTHER"]
COA_NODE_TYPES = ["HEADER", "TOTAL", "POSTING_GROUP"]
ASSET_TYPES = ["FIXED_ASSET", "TOOL"]
DEPRECIATION_METHODS = ["STRAIGHT_LINE", "NONE"]
ASSET_STATUSES = ["PLANNED", "ACTIVE", "FULLY_DEPRECIATED", "RETIRED"]
TAX_TYPES = ["INPUT", "OUTPUT"]
OBJECT_CODES = [
    "CUSTOMER", "VENDOR", "BP", "ITEM", "WAREHOUSE", "TAX", "COA", "GL", "SALE_CHANNEL", "BOM",
    "ASSET_CLASS", "FIXED_ASSET", "ASSET_RUN",
    "PO", "GR", "AP", "VP", "SO", "DL", "AR", "CR", "PROD", "MI", "PR", "IM", "JE"
]


def fld(name, label, field_type="text", required=False, options=None, placeholder="", help_text="", default=None, step=None, tab=None, persist=True):
    return {
        "name": name,
        "label": label,
        "type": field_type,
        "required": required,
        "options": options or [],
        "placeholder": placeholder,
        "help_text": help_text,
        "default": default,
        "step": step,
        "tab": tab or "general",
        "persist": persist,
    }


ENTITY_CONFIG = {
    "items": {
        "title": "Item Master",
        "subtitle": "Nguyên vật liệu, bao bì, thành phẩm, hàng bán lại và dịch vụ. Form được chia tab theo kiểu SAP để maintain purchasing/sales/accounting defaults.",
        "table": "dbo.items",
        "pk": "id",
        "icon": "🍱",
        "code_field": "item_code",
        "search_columns": ["item_code", "item_name", "item_type", "base_uom"],
        "form_tabs": [
            {"key": "general", "label": "General"},
            {"key": "purchasing", "label": "Purchasing"},
            {"key": "sales", "label": "Sales"},
            {"key": "accounting", "label": "Accounting"},
            {"key": "tracking", "label": "Tracking"},
        ],
        "list_columns": [
            ("item_code", "Code", "text"),
            ("item_name", "Name", "text"),
            ("item_type", "Type", "badge"),
            ("base_uom", "UoM", "text"),
            ("input_tax_code", "Input Tax", "badge"),
            ("output_tax_code", "Output Tax", "badge"),
            ("standard_cost", "Std Cost", "money"),
            ("estimate_receive_days", "Est. Receive Days", "text"),
            ("delivery_days", "Delivery Days", "text"),
            ("profit_percent", "Profit %", "text"),
            ("can_be_sold", "Sellable", "active"),
            ("is_active", "Status", "active"),
        ],
        "fields": [
            fld("item_code", "Item Code", required=False, placeholder="FG-COFFEE-BOTTLE", help_text="Để trống để hệ thống tự sinh mã theo Document Numbering.", tab="general"),
            fld("item_name", "Item Name", required=True, placeholder="Cà phê sữa đóng chai 250ml", tab="general"),
            fld("item_type", "Item Type", "select", True, ITEM_TYPES, tab="general"),
            fld("base_uom", "Base UoM", "uom_select", required=True, placeholder="piece / gram / bottle", tab="general"),
            fld("is_active", "Active", "checkbox", default=True, tab="general"),

            fld("purchase_uom", "Purchase UoM", "uom_select", placeholder="kg / thùng / chai", tab="purchasing"),
            fld("input_tax_code_id", "Default Input Tax Code", "input_tax_code_select", help_text="Dùng làm default Tax Code khi tạo PR/PO/AP cho item này.", tab="purchasing"),
            fld("estimate_receive_days", "Estimate Receive Days", "integer", default="0", help_text="Số ngày dự kiến nhận hàng sau ngày tạo PR. Khi chọn item trên PR, Required Date sẽ default = PR Date + số ngày này.", tab="purchasing"),
            fld("standard_cost", "Standard Cost", "number", default="0", step="0.0001", tab="purchasing"),

            fld("sales_uom", "Sales UoM", "uom_select", placeholder="ly / chai / combo", tab="sales"),
            fld("output_tax_code_id", "Default Output Tax Code", "output_tax_code_select", help_text="Dùng làm default Tax Code khi bán hàng/AR cho item này.", tab="sales"),
            fld("delivery_days", "Delivery Days", "integer", default="0", help_text="Chỉ áp dụng cho FINISHED. Delivery Date mặc định = ngày tạo/cập nhật SO + số ngày này.", tab="sales"),
            fld("profit_percent", "Target Profit %", "number", default="20", step="0.0001", help_text="Dùng cho nút Tính giá trong Sales: Giá đề xuất = giá vốn tồn kho + % lợi nhuận mục tiêu.", tab="sales"),
            fld("can_be_sold", "Allow Standard Sale", "checkbox", default=True, help_text="Chỉ áp dụng cho Item Type = FINISHED. Các item khác không được bán theo luồng bán hàng thường, chỉ dùng cho scrap sale khi có module riêng.", tab="sales"),
            fld("sale_channel_ids", "Opened Sale Channels", "sale_channel_multi", help_text="Chọn một hoặc nhiều kênh bán hàng được phép bán item FINISHED này.", tab="sales", persist=False),
            fld("sales_price", "Sales Price", "number", default="", step="0.0001", help_text="Có thể để trống. Nếu trống, Sales sẽ tính giá theo cost tồn kho + Target Profit %.", tab="sales"),

            fld("inventory_account_id", "Inventory Account", "account_select", tab="accounting"),
            fld("cogs_account_id", "COGS Account", "account_select", tab="accounting"),
            fld("revenue_account_id", "Revenue Account", "account_select", tab="accounting"),
            fld("wip_account_id", "WIP Account", "account_select", tab="accounting"),

            fld("expiry_tracking", "Track Expiry Date", "checkbox", tab="tracking"),
            fld("lot_tracking", "Track Lot/Batch", "checkbox", tab="tracking"),
        ],
    },
    "business-partners": {
        "title": "Business Partners",
        "subtitle": "Khách hàng, nhà cung cấp hoặc đối tác vừa bán vừa mua.",
        "table": "dbo.business_partners",
        "pk": "id",
        "icon": "🤝",
        "code_field": "bp_code",
        "search_columns": ["bp_code", "bp_name", "bp_type", "bp_category", "phone", "email", "tax_no"],
        "list_columns": [
            ("bp_code", "Code", "text"),
            ("bp_name", "Name", "text"),
            ("bp_type", "Type", "badge"),
            ("bp_category", "Category", "badge"),
            ("phone", "Phone", "text"),
            ("email", "Email", "text"),
            ("tax_no", "Tax No", "text"),
            ("currency_code", "Currency", "text"),
            ("is_active", "Status", "active"),
        ],
        "fields": [
            fld("bp_code", "BP Code", required=False, placeholder="CUST001 / VEND001", help_text="Để trống để hệ thống tự sinh mã Customer/Vendor theo BP Type."),
            fld("bp_name", "BP Name", required=True),
            fld("bp_type", "BP Type", "select", True, BP_TYPES),
            fld("bp_category", "BP Category", "select", True, BP_CATEGORIES, help_text="COMPANY = Doanh nghiệp, INDIVIDUAL = Cá nhân, BANK = Ngân hàng, ONE_TIME = Vãng lai."),
            fld("phone", "Phone"),
            fld("email", "Email", "email"),
            fld("address_line", "Address", "textarea"),
            fld("tax_no", "Tax No"),
            fld("payment_terms", "Payment Terms", placeholder="COD / 15 days / 30 days"),
            fld("currency_code", "Currency", default="VND"),
            fld("ar_account_id", "AR Account", "account_select"),
            fld("ap_account_id", "AP Account", "account_select"),
            fld("is_active", "Active", "checkbox", default=True),
        ],
    },
    "warehouses": {
        "title": "Warehouses",
        "subtitle": "Kho tổng, kho cửa hàng, kho bếp/sản xuất và kho hủy hàng.",
        "table": "dbo.warehouses",
        "pk": "id",
        "icon": "🏬",
        "code_field": "warehouse_code",
        "search_columns": ["warehouse_code", "warehouse_name", "warehouse_type"],
        "list_columns": [
            ("warehouse_code", "Code", "text"),
            ("warehouse_name", "Name", "text"),
            ("warehouse_type", "Type", "badge"),
            ("is_active", "Status", "active"),
        ],
        "fields": [
            fld("warehouse_code", "Warehouse Code", required=False, placeholder="MAIN / STORE01", help_text="Để trống để hệ thống tự sinh mã kho."),
            fld("warehouse_name", "Warehouse Name", required=True),
            fld("warehouse_type", "Warehouse Type", "select", True, WAREHOUSE_TYPES),
            fld("is_active", "Active", "checkbox", default=True),
        ],
    },
    "uoms": {
        "title": "Unit of Measure",
        "subtitle": "Danh mục đơn vị đo lường dùng chung cho Item Master, PR, PO, GR, Sales và Production.",
        "table": "dbo.unit_of_measures",
        "pk": "id",
        "icon": "📏",
        "code_field": "unit_code",
        "search_columns": ["unit_code", "unit_name", "unit_group", "description"],
        "list_columns": [
            ("unit_code", "Unit Code", "text"),
            ("unit_name", "Unit Name", "text"),
            ("unit_group", "Group", "badge"),
            ("decimal_places", "Decimals", "qty"),
            ("description", "Description", "text"),
            ("is_active", "Status", "active"),
        ],
        "fields": [
            fld("unit_code", "Unit Code", required=True, placeholder="kg / bottle / carton", help_text="Nên dùng mã thống nhất, viết thường hoặc chuẩn nội bộ. Ví dụ: gram, kg, bottle, carton."),
            fld("unit_name", "Unit Name", required=True, placeholder="Kilogram / Bottle / Carton"),
            fld("unit_group", "Unit Group", "select", True, UOM_GROUPS, default="COUNT"),
            fld("decimal_places", "Decimal Places", "integer", True, default="4", help_text="Số chữ số thập phân cho đơn vị này khi hiển thị/nhập liệu."),
            fld("description", "Description", "textarea", placeholder="Ghi chú cách dùng đơn vị."),
            fld("is_active", "Active", "checkbox", default=True),
        ],
    },

    "chart-accounts": {
        "title": "Chart of Accounts Structure",
        "subtitle": "Quy định cấu trúc báo cáo GL: nhóm báo cáo, node cha/con, thứ tự hiển thị trên Balance Sheet/P&L.",
        "table": "dbo.coa_nodes",
        "pk": "id",
        "icon": "🗂️",
        "code_field": "node_code",
        "search_columns": ["node_code", "node_name", "report_section", "node_type"],
        "list_columns": [
            ("node_code", "Node", "text"),
            ("node_name", "Node Name", "text"),
            ("report_section", "Report", "badge"),
            ("node_type", "Node Type", "badge"),
            ("sequence_no", "Seq", "qty"),
            ("is_active", "Status", "active"),
        ],
        "fields": [
            fld("node_code", "Node Code", required=False, placeholder="BS-ASSET / PL-REV", help_text="Để trống để hệ thống tự sinh mã node theo Document Numbering."),
            fld("node_name", "Node Name", required=True, placeholder="Assets / Revenue / COGS"),
            fld("report_section", "Report Section", "select", True, COA_REPORT_SECTIONS),
            fld("node_type", "Node Type", "select", True, COA_NODE_TYPES),
            fld("parent_node_id", "Parent Node", "coa_node_select"),
            fld("normal_balance", "Normal Balance", "select", False, NORMAL_BALANCES),
            fld("sequence_no", "Sequence No", "number", True, default="10", step="1"),
            fld("is_active", "Active", "checkbox", default=True),
        ],
    },
    "gl-accounts": {
        "title": "G/L Master Data",
        "subtitle": "Quản lý tính chất từng tài khoản kế toán: nhóm tài khoản, tính chất Nợ/Có, cho phép posting và open item cho công nợ.",
        "table": "dbo.chart_accounts",
        "pk": "id",
        "icon": "📒",
        "code_field": "account_code",
        "search_columns": ["account_code", "account_name", "account_type", "account_group", "open_item_type"],
        "list_columns": [
            ("account_code", "G/L Account", "text"),
            ("account_name", "Name", "text"),
            ("account_type", "Type", "badge"),
            ("account_group", "Group", "badge"),
            ("normal_balance", "Balance", "badge"),
            ("is_open_item", "Open Item", "bool"),
            ("open_item_type", "O/I Type", "badge"),
            ("posting_allowed", "Posting", "bool"),
            ("is_active", "Status", "active"),
        ],
        "fields": [
            fld("account_code", "G/L Account", required=False, placeholder="152 / 155 / 511", help_text="Có thể nhập tay theo hệ thống tài khoản hoặc để trống để sinh mã tự động."),
            fld("account_name", "Account Name", required=True),
            fld("account_type", "Account Type", "select", True, ACCOUNT_TYPES),
            fld("account_group", "Account Group", "select", False, GL_ACCOUNT_GROUPS),
            fld("normal_balance", "Normal Balance", "select", False, NORMAL_BALANCES),
            fld("coa_node_id", "COA Report Node", "coa_node_select", help_text="Node dùng để nhóm tài khoản lên báo cáo GL/Balance Sheet/P&L."),
            fld("is_open_item", "Open Item Management", "checkbox", default=False, help_text="Bật cho tài khoản công nợ như 131/331 để theo dõi đối tượng và clearing."),
            fld("open_item_type", "Open Item Type", "select", False, OPEN_ITEM_TYPES),
            fld("posting_allowed", "Allow Posting", "checkbox", default=True),
            fld("is_active", "Active", "checkbox", default=True),
        ],
    },
    "tax-codes": {
        "title": "Tax Codes",
        "subtitle": "Phân loại Tax Code theo INPUT hoặc OUTPUT. Mỗi Tax Code chỉ có một VAT Account để áp dụng thống nhất cho mua hàng hoặc bán hàng.",
        "table": "dbo.tax_codes",
        "pk": "id",
        "icon": "🧮",
        "code_field": "tax_code",
        "search_columns": ["tax_code", "tax_name", "tax_type"],
        "list_columns": [
            ("tax_code", "Code", "text"),
            ("tax_name", "Name", "text"),
            ("tax_type", "Type", "badge"),
            ("rate", "Rate %", "qty"),
            ("is_active", "Status", "active"),
        ],
        "fields": [
            fld("tax_code", "Tax Code", required=False, placeholder="VAT10_IN / VAT10_OUT", help_text="Để trống để hệ thống tự sinh mã thuế."),
            fld("tax_name", "Tax Name", required=True, placeholder="Input VAT 10% / Output VAT 10%"),
            fld("tax_type", "Tax Type", "select", True, TAX_TYPES, default="INPUT", help_text="INPUT = thuế đầu vào, OUTPUT = thuế đầu ra. Không dùng BOTH để tránh mapping tài khoản VAT bị mơ hồ."),
            fld("rate", "Rate %", "number", True, default="0", step="0.0001"),
            fld("vat_account_id", "VAT Account", "account_select", help_text="Mặc định: INPUT → 1331, OUTPUT → 3331. Bạn vẫn có thể đổi nếu cần."),
            fld("is_active", "Active", "checkbox", default=True),
        ],
    },
    "sale-channels": {
        "title": "Sale Channels",
        "subtitle": "Quản lý kênh bán hàng như cửa hàng, POS, online, delivery, marketplace và bán sỉ.",
        "table": "dbo.sale_channels",
        "pk": "id",
        "icon": "🛒",
        "code_field": "channel_code",
        "search_columns": ["channel_code", "channel_name", "channel_type", "external_source"],
        "list_columns": [
            ("channel_code", "Channel", "text"),
            ("channel_name", "Name", "text"),
            ("channel_type", "Type", "badge"),
            ("external_source", "External Source", "text"),
            ("default_tax_code", "Tax Code", "badge"),
            ("is_active", "Status", "active"),
        ],
        "fields": [
            fld("channel_code", "Sale Channel Code", required=False, placeholder="RETAIL / POS / ONLINE", help_text="Để trống để hệ thống tự sinh mã kênh bán hàng."),
            fld("channel_name", "Sale Channel Name", required=True, placeholder="Retail Store / GrabFood / ShopeeFood"),
            fld("channel_type", "Channel Type", "select", True, SALE_CHANNEL_TYPES),
            fld("external_source", "External Source", placeholder="Loyverse / KiotViet / Sapo / CSV / Manual"),
            fld("default_customer_id", "Default Customer", "bp_customer_select"),
            fld("default_warehouse_id", "Default Warehouse", "warehouse_select"),
            fld("revenue_account_id", "Default Revenue Account", "account_select"),
            fld("discount_account_id", "Discount Account", "account_select"),
            fld("fee_account_id", "Platform Fee Account", "account_select"),
            fld("default_tax_code_id", "Tax Code", "output_tax_code_select", help_text="Chọn Output Tax Code để áp dụng thống nhất rate và tài khoản VAT đầu ra cho từng kênh bán hàng."),
            fld("is_active", "Active", "checkbox", default=True),
        ],
    },
    "boms": {
        "title": "BOM / Recipe",
        "subtitle": "Quản lý công thức/BOM cho Finished Good, gồm thành phẩm, version, base quantity và danh sách nguyên vật liệu cấu thành.",
        "table": "dbo.boms",
        "pk": "id",
        "icon": "🧾",
        "code_field": "bom_code",
        "search_columns": ["bom_code", "version_no"],
        "list_columns": [],
        "fields": [],
    },
    "asset-classes": {
        "title": "Asset Classes",
        "subtitle": "Nhóm tài sản cố định/công cụ dụng cụ, quy định thời gian khấu hao/phân bổ và tài khoản hạch toán mặc định.",
        "table": "dbo.asset_classes",
        "pk": "id",
        "icon": "🏷️",
        "code_field": "class_code",
        "search_columns": ["class_code", "class_name", "asset_type", "depreciation_method"],
        "list_columns": [
            ("class_code", "Class", "text"),
            ("class_name", "Name", "text"),
            ("asset_type", "Type", "badge"),
            ("useful_life_months", "Life (M)", "qty"),
            ("depreciation_method", "Method", "badge"),
            ("is_active", "Status", "active"),
        ],
        "fields": [
            fld("class_code", "Asset Class Code", required=False, placeholder="FA-EQUIP / TOOL-KITCHEN", help_text="Để trống để hệ thống tự sinh mã nhóm tài sản/CCDC."),
            fld("class_name", "Asset Class Name", required=True, placeholder="Máy móc thiết bị / Công cụ dụng cụ bếp"),
            fld("asset_type", "Asset Type", "select", True, ASSET_TYPES),
            fld("useful_life_months", "Useful Life (Months)", "number", True, default="12", step="1"),
            fld("depreciation_method", "Depreciation / Allocation Method", "select", True, DEPRECIATION_METHODS),
            fld("asset_account_id", "Asset / Prepaid Account", "account_select", help_text="TSCĐ: 211; CCDC: 153 hoặc 242 tùy cách quản lý."),
            fld("accumulated_dep_account_id", "Accumulated Depreciation / Allocation Account", "account_select", help_text="TSCĐ: 2141; CCDC: 242 nếu phân bổ từ chi phí trả trước."),
            fld("dep_expense_account_id", "Depreciation / Allocation Expense Account", "account_select", help_text="Ví dụ 627/641/642 tùy nơi sử dụng tài sản."),
            fld("is_active", "Active", "checkbox", default=True),
        ],
    },
    "fixed-assets": {
        "title": "Fixed Assets / Tools",
        "subtitle": "Quản lý tài sản cố định và công cụ dụng cụ: nguyên giá, ngày ghi tăng, thời gian khấu hao/phân bổ, trạng thái sử dụng.",
        "table": "dbo.fixed_assets",
        "pk": "id",
        "icon": "🧰",
        "code_field": "asset_code",
        "search_columns": ["asset_code", "asset_name", "asset_type", "location_name", "responsible_person"],
        "list_columns": [
            ("asset_code", "Asset", "text"),
            ("asset_name", "Name", "text"),
            ("asset_type", "Type", "badge"),
            ("asset_class", "Class", "text"),
            ("acquisition_cost", "Cost", "money"),
            ("accumulated_depreciation", "Accum. Dep", "money"),
            ("net_book_value", "NBV", "money"),
            ("asset_status", "Status", "badge"),
            ("is_active", "Active", "active"),
        ],
        "fields": [
            fld("asset_code", "Asset Code", required=False, placeholder="FA-2026-00001 / TOOL-2026-00001", help_text="Để trống để hệ thống tự sinh mã tài sản/CCDC."),
            fld("asset_name", "Asset Name", required=True, placeholder="Máy pha cà phê / Máy xay / Bộ dụng cụ bếp"),
            fld("asset_type", "Asset Type", "select", True, ASSET_TYPES),
            fld("asset_class_id", "Asset Class", "asset_class_select", True),
            fld("acquisition_date", "Acquisition Date", "date", True),
            fld("capitalization_date", "Capitalization Date", "date"),
            fld("depreciation_start_date", "Depreciation Start Date", "date"),
            fld("acquisition_cost", "Acquisition Cost", "number", True, default="0", step="0.0001"),
            fld("residual_value", "Residual Value", "number", True, default="0", step="0.0001"),
            fld("useful_life_months", "Useful Life (Months)", "number", True, default="12", step="1"),
            fld("asset_status", "Asset Status", "select", True, ASSET_STATUSES, default="ACTIVE"),
            fld("location_name", "Location", placeholder="Kitchen / Store 01 / Office"),
            fld("responsible_person", "Responsible Person", placeholder="Người/ bộ phận quản lý"),
            fld("serial_no", "Serial No"),
            fld("is_depreciable", "Depreciable / Allocatable", "checkbox", default=True),
            fld("is_active", "Active", "checkbox", default=True),
        ],
    },
    "number-ranges": {
        "title": "Document Numbering",
        "subtitle": "Quy tắc đánh số tự động cho mã master data và chứng từ. Next No chỉ tăng khi Save thành công.",
        "table": "dbo.number_ranges",
        "pk": "id",
        "icon": "#️⃣",
        "code_field": "object_code",
        "search_columns": ["object_code", "subkey", "prefix_template"],
        "list_columns": [
            ("object_code", "Object", "badge"),
            ("subkey", "Subkey", "text"),
            ("prefix_template", "Template", "text"),
            ("next_no", "Next No", "qty"),
            ("width", "Width", "qty"),
            ("year_mode", "Yearly", "bool"),
            ("allow_manual", "Manual", "bool"),
            ("is_active", "Status", "active"),
        ],
        "fields": [
            fld("object_code", "Object Code", "select", True, OBJECT_CODES),
            fld("subkey", "Subkey", default="", help_text="Để trống nếu không chia theo loại/phân hệ."),
            fld("prefix_template", "Prefix Template", required=True, placeholder="SO-{YYYY}-{MM}-{00001}", help_text="Generate chỉ preview số hiện tại; Next No chỉ tăng khi Save chứng từ/master data thành công."),
            fld("next_no", "Next No", "number", True, default="1", step="1"),
            fld("width", "Number Width", "number", True, default="5", step="1"),
            fld("year_mode", "Reset by Year", "checkbox", default=True),
            fld("allow_manual", "Allow Manual Number", "checkbox", default=True),
            fld("is_active", "Active", "checkbox", default=True),
        ],
    },
}


# Mapping for automatic master-code generation.
# The server generates the code only when the code field is blank on save,
# or when the user clicks the Generate button on the form.
MASTER_NUMBERING_CONFIG = {
    "items": {
        "object_code": "ITEM",
        "code_field": "item_code",
        "subkey_field": "item_type",
    },
    "business-partners": {
        "object_code_field": "bp_type",
        "object_code_map": {"CUSTOMER": "CUSTOMER", "VENDOR": "VENDOR", "BOTH": "BP"},
        "code_field": "bp_code",
        "subkey_field": None,
    },
    "warehouses": {
        "object_code": "WAREHOUSE",
        "code_field": "warehouse_code",
        "subkey_field": "warehouse_type",
    },
    "tax-codes": {
        "object_code": "TAX",
        "code_field": "tax_code",
        "subkey_field": None,
    },
    "chart-accounts": {
        "object_code": "COA",
        "code_field": "node_code",
        "subkey_field": "report_section",
    },
    "gl-accounts": {
        "object_code": "GL",
        "code_field": "account_code",
        "subkey_field": "account_type",
    },
    "sale-channels": {
        "object_code": "SALE_CHANNEL",
        "code_field": "channel_code",
        "subkey_field": "channel_type",
    },
    "asset-classes": {
        "object_code": "ASSET_CLASS",
        "code_field": "class_code",
        "subkey_field": "asset_type",
    },
    "fixed-assets": {
        "object_code": "FIXED_ASSET",
        "code_field": "asset_code",
        "subkey_field": "asset_type",
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_redirect(url: str, success: str = "", error: str = ""):
    if success:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}success={quote_plus(success)}"
    if error:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}error={quote_plus(error)}"
    return RedirectResponse(url, status_code=303)


def _get_entity(entity: str):
    return ENTITY_CONFIG.get(entity)


def _load_account_options(db: Session):
    rows = db.execute(text("""
        SELECT id, account_code, account_name, ISNULL(is_open_item, 0) AS is_open_item
        FROM dbo.chart_accounts
        WHERE is_active = 1
        ORDER BY account_code
    """)).mappings().all()
    return [(str(r["id"]), f'{r["account_code"]} - {r["account_name"]}' + (" [Open Item]" if r["is_open_item"] else "")) for r in rows]


def _load_coa_node_options(db: Session):
    rows = db.execute(text("""
        SELECT id, node_code, node_name, report_section
        FROM dbo.coa_nodes
        WHERE is_active = 1
        ORDER BY report_section, sequence_no, node_code
    """)).mappings().all()
    return [(str(r["id"]), f'{r["node_code"]} - {r["node_name"]} [{r["report_section"]}]') for r in rows]


def _load_customer_options(db: Session):
    rows = db.execute(text("""
        SELECT id, bp_code, bp_name
        FROM dbo.business_partners
        WHERE is_active = 1 AND bp_type IN (N'CUSTOMER', N'BOTH')
        ORDER BY bp_code
    """)).mappings().all()
    return [(str(r["id"]), f'{r["bp_code"]} - {r["bp_name"]}') for r in rows]


def _load_warehouse_options(db: Session):
    rows = db.execute(text("""
        SELECT id, warehouse_code, warehouse_name
        FROM dbo.warehouses
        WHERE is_active = 1
        ORDER BY warehouse_code
    """)).mappings().all()
    return [(str(r["id"]), f'{r["warehouse_code"]} - {r["warehouse_name"]}') for r in rows]


def _load_tax_code_options(db: Session):
    rows = db.execute(text("""
        SELECT id, tax_code, tax_name, rate, ISNULL(tax_type, N'OUTPUT') AS tax_type
        FROM dbo.tax_codes
        WHERE is_active = 1 AND ISNULL(tax_type, N'OUTPUT') IN (N'INPUT', N'OUTPUT')
        ORDER BY tax_type, tax_code
    """)).mappings().all()
    return [(str(r["id"]), f'{r["tax_code"]} - {r["tax_name"]} ({r["rate"]}%) [{r["tax_type"]}]') for r in rows]


def _load_input_tax_code_options(db: Session):
    rows = db.execute(text("""
        SELECT id, tax_code, tax_name, rate, ISNULL(tax_type, N'INPUT') AS tax_type
        FROM dbo.tax_codes
        WHERE is_active = 1 AND ISNULL(tax_type, N'INPUT') = N'INPUT'
        ORDER BY tax_code
    """)).mappings().all()
    return [(str(r["id"]), f'{r["tax_code"]} - {r["tax_name"]} ({r["rate"]}%) [{r["tax_type"]}]') for r in rows]


def _load_output_tax_code_options(db: Session):
    rows = db.execute(text("""
        SELECT id, tax_code, tax_name, rate, ISNULL(tax_type, N'OUTPUT') AS tax_type
        FROM dbo.tax_codes
        WHERE is_active = 1 AND ISNULL(tax_type, N'OUTPUT') = N'OUTPUT'
        ORDER BY tax_code
    """)).mappings().all()
    return [(str(r["id"]), f'{r["tax_code"]} - {r["tax_name"]} ({r["rate"]}%) [{r["tax_type"]}]') for r in rows]


def _load_sale_channel_options(db: Session):
    rows = db.execute(text("""
        SELECT id, channel_code, channel_name, channel_type
        FROM dbo.sale_channels
        WHERE is_active = 1
        ORDER BY channel_type, channel_code
    """)).mappings().all()
    return [(str(r["id"]), f'{r["channel_code"]} - {r["channel_name"]} [{r["channel_type"]}]') for r in rows]

def _get_item_sale_channel_ids(db: Session, item_id: int) -> list[int]:
    if not item_id:
        return []
    try:
        rows = db.execute(text("""
            IF OBJECT_ID(N'dbo.item_sale_channels', N'U') IS NOT NULL
                SELECT sale_channel_id FROM dbo.item_sale_channels WHERE item_id = :item_id
            ELSE
                SELECT CAST(NULL AS BIGINT) AS sale_channel_id WHERE 1 = 0
        """), {"item_id": item_id}).mappings().all()
        return [int(r["sale_channel_id"]) for r in rows if r["sale_channel_id"]]
    except Exception:
        return []

def _sync_item_sale_channels(db: Session, item_id: int, values: dict):
    item_type = str(values.get("item_type") or "").upper().strip()
    can_be_sold = 1 if values.get("can_be_sold") in (1, True, "1", "on", "true", "True") else 0
    selected = values.get("sale_channel_ids") or []
    try:
        db.execute(text("""
            IF OBJECT_ID(N'dbo.item_sale_channels', N'U') IS NOT NULL
            BEGIN
                DELETE FROM dbo.item_sale_channels WHERE item_id = :item_id;
            END
        """), {"item_id": item_id})
        if item_type == "FINISHED" and can_be_sold and selected:
            for channel_id in selected:
                db.execute(text("""
                    INSERT INTO dbo.item_sale_channels(item_id, sale_channel_id)
                    SELECT :item_id, :sale_channel_id
                    WHERE OBJECT_ID(N'dbo.item_sale_channels', N'U') IS NOT NULL
                      AND EXISTS (SELECT 1 FROM dbo.sale_channels WHERE id = :sale_channel_id AND is_active = 1)
                """), {"item_id": item_id, "sale_channel_id": int(channel_id)})
    except Exception:
        # If migration has not been applied yet, keep item save working.
        pass


def _load_unit_options(db: Session):
    try:
        units = []
        # Prefer centralized UoM Master when migration 29 has been applied.
        has_uom_master = bool(db.execute(text("SELECT CASE WHEN OBJECT_ID(N'dbo.unit_of_measures', N'U') IS NULL THEN 0 ELSE 1 END")).scalar())
        if has_uom_master:
            rows = db.execute(text("""
                SELECT unit_code AS unit_name
                FROM dbo.unit_of_measures
                WHERE is_active = 1 AND ISNULL(unit_code, N'') <> N''
                ORDER BY unit_code
            """)).mappings().all()
            units.extend([str(r["unit_name"]).strip() for r in rows if r["unit_name"]])

        # Backward-compatible fallback: collect units already maintained on Item Master/conversions.
        rows = db.execute(text("""
            SELECT DISTINCT unit_name
            FROM (
                SELECT base_uom AS unit_name FROM dbo.items WHERE ISNULL(base_uom, N'') <> N''
                UNION ALL SELECT purchase_uom FROM dbo.items WHERE ISNULL(purchase_uom, N'') <> N''
                UNION ALL SELECT sales_uom FROM dbo.items WHERE ISNULL(sales_uom, N'') <> N''
            ) u
            WHERE ISNULL(unit_name, N'') <> N''
            ORDER BY unit_name
        """)).mappings().all()
        for r in rows:
            u = str(r["unit_name"] or "").strip()
            if u and u not in units:
                units.append(u)

        has_conversions = bool(db.execute(text("SELECT CASE WHEN OBJECT_ID(N'dbo.item_unit_conversions', N'U') IS NULL THEN 0 ELSE 1 END")).scalar())
        if has_conversions:
            conv_rows = db.execute(text("""
                SELECT DISTINCT order_uom AS unit_name
                FROM dbo.item_unit_conversions
                WHERE ISNULL(order_uom, N'') <> N''
                ORDER BY order_uom
            """)).mappings().all()
            for r in conv_rows:
                u = str(r["unit_name"] or "").strip()
                if u and u not in units:
                    units.append(u)
        return sorted(units, key=lambda x: x.lower())
    except Exception:
        return []

def _get_item_unit_conversions(db: Session, item_id: int) -> list[dict]:
    if not item_id:
        return []
    try:
        rows = db.execute(text("""
            IF OBJECT_ID(N'dbo.item_unit_conversions', N'U') IS NOT NULL
                SELECT id, base_uom, order_uom, conversion_rate_to_base, is_active, note
                FROM dbo.item_unit_conversions
                WHERE item_id = :item_id
                ORDER BY CASE WHEN conversion_rate_to_base = 1 THEN 0 ELSE 1 END, order_uom
            ELSE
                SELECT CAST(NULL AS BIGINT) AS id, CAST(NULL AS NVARCHAR(30)) AS base_uom, CAST(NULL AS NVARCHAR(30)) AS order_uom,
                       CAST(NULL AS DECIMAL(19,6)) AS conversion_rate_to_base, CAST(NULL AS BIT) AS is_active, CAST(NULL AS NVARCHAR(500)) AS note
                WHERE 1 = 0
        """), {"item_id": item_id}).mappings().all()
        return [dict(r) for r in rows if r.get("order_uom")]
    except Exception:
        return []


def _parse_item_unit_conversions(form, base_uom: str | None) -> list[dict]:
    order_uoms = form.getlist("conversion_order_uom")
    rates = form.getlist("conversion_rate_to_base")
    notes = form.getlist("conversion_note")
    active_markers = form.getlist("conversion_active_marker")
    active_values = set(str(x) for x in form.getlist("conversion_active"))
    rows = []
    seen = set()
    base_uom = str(base_uom or "").strip()
    for idx, raw_uom in enumerate(order_uoms):
        order_uom = str(raw_uom or "").strip()
        if not order_uom:
            continue
        key = order_uom.lower()
        if key in seen:
            continue
        seen.add(key)
        try:
            rate = Decimal(str(rates[idx] if idx < len(rates) and rates[idx] not in (None, "") else "1"))
        except Exception:
            rate = Decimal("1")
        if rate <= 0:
            rate = Decimal("1")
        marker = str(active_markers[idx]) if idx < len(active_markers) else str(idx)
        note = str(notes[idx] if idx < len(notes) else "").strip() or None
        rows.append({
            "base_uom": base_uom,
            "order_uom": order_uom,
            "conversion_rate_to_base": rate,
            "is_active": 1 if marker in active_values else 0,
            "note": note,
        })
    # Always keep the 1:1 base unit conversion active.
    if base_uom and base_uom.lower() not in seen:
        rows.insert(0, {"base_uom": base_uom, "order_uom": base_uom, "conversion_rate_to_base": Decimal("1"), "is_active": 1, "note": "Default 1:1 conversion"})
    return rows


def _sync_item_unit_conversions(db: Session, item_id: int, values: dict, form):
    try:
        exists = db.execute(text("SELECT CASE WHEN OBJECT_ID(N'dbo.item_unit_conversions', N'U') IS NULL THEN 0 ELSE 1 END")).scalar()
        if not exists:
            return
        base_uom = str(values.get("base_uom") or "").strip()
        rows = _parse_item_unit_conversions(form, base_uom)
        db.execute(text("DELETE FROM dbo.item_unit_conversions WHERE item_id = :item_id"), {"item_id": item_id})
        for row in rows:
            db.execute(text("""
                INSERT INTO dbo.item_unit_conversions(item_id, base_uom, order_uom, conversion_rate_to_base, is_active, note)
                VALUES(:item_id, :base_uom, :order_uom, :conversion_rate_to_base, :is_active, :note)
            """), {"item_id": item_id, **row})
    except Exception:
        # Keep Item Master save working even if migration 28 has not been applied yet.
        pass

def _load_asset_class_options(db: Session):
    rows = db.execute(text("""
        SELECT id, class_code, class_name, asset_type
        FROM dbo.asset_classes
        WHERE is_active = 1
        ORDER BY asset_type, class_code
    """)).mappings().all()
    return [(str(r["id"]), f'{r["class_code"]} - {r["class_name"]} [{r["asset_type"]}]') for r in rows]


def _field_names(config):
    return [f["name"] for f in config["fields"] if f.get("persist", True)]


def _parse_form_data(config, form):
    values = {}
    errors = []
    for field in config["fields"]:
        name = field["name"]
        field_type = field["type"]
        raw = form.get(name)

        if field_type == "checkbox":
            values[name] = 1 if raw in ("on", "1", "true", "True", "yes") else 0
            continue

        if raw is None:
            raw = ""
        if isinstance(raw, str):
            raw = raw.strip()

        if field.get("required") and raw == "":
            errors.append(f"{field['label']} is required.")

        if raw == "":
            values[name] = [] if field_type == "sale_channel_multi" else None if field_type in ("number", "integer", "account_select", "coa_node_select", "bp_customer_select", "warehouse_select", "tax_code_select", "input_tax_code_select", "output_tax_code_select", "asset_class_select") else ""
            continue

        if field_type == "sale_channel_multi":
            cleaned = []
            for x in form.getlist(name):
                try:
                    val = int(str(x).strip())
                    if val > 0 and val not in cleaned:
                        cleaned.append(val)
                except ValueError:
                    pass
            values[name] = cleaned
        elif field_type == "integer":
            try:
                values[name] = int(raw)
            except ValueError:
                errors.append(f"{field['label']} must be a valid integer.")
                values[name] = 0
        elif field_type == "number":
            try:
                values[name] = parse_decimal_strict(raw)
            except InvalidOperation:
                errors.append(f"{field['label']} must be a valid number. Có thể nhập theo dạng 1.234,56 hoặc 1234,56.")
                values[name] = Decimal("0")
        elif field_type in ("account_select", "coa_node_select", "bp_customer_select", "warehouse_select", "tax_code_select", "input_tax_code_select", "output_tax_code_select", "asset_class_select"):
            try:
                values[name] = int(raw)
            except ValueError:
                values[name] = None
        else:
            values[name] = raw

    return values, errors


def _apply_defaults(config):
    row = {}
    for field in config["fields"]:
        default = field.get("default")
        if field["type"] == "checkbox":
            row[field["name"]] = 1 if default is True else 0
        elif field["type"] == "sale_channel_multi":
            row[field["name"]] = []
        else:
            row[field["name"]] = default or ""
    return row


def _default_vat_account_ids(db: Session):
    row = db.execute(text("""
        SELECT
            (SELECT TOP 1 id FROM dbo.chart_accounts WHERE account_code = N'1331' AND is_active = 1) AS input_vat_account_id,
            (SELECT TOP 1 id FROM dbo.chart_accounts WHERE account_code = N'3331' AND is_active = 1) AS output_vat_account_id
    """)).mappings().first()
    return {
        "input": str(row["input_vat_account_id"] or "") if row else "",
        "output": str(row["output_vat_account_id"] or "") if row else "",
    }


def _normalize_tax_code_values(db: Session, values: dict):
    """Keep Tax Code simple: INPUT/OUTPUT only and a single VAT Account.

    Legacy columns input_account_id/output_account_id may still exist in the database for backward
    compatibility, but new logic reads tax_codes.vat_account_id.
    """
    values = dict(values)
    errors = []
    tax_type = str(values.get("tax_type") or "").upper().strip()
    if tax_type not in ("INPUT", "OUTPUT"):
        errors.append("Tax Type chỉ được chọn INPUT hoặc OUTPUT. Option BOTH đã được loại bỏ.")
        return values, errors

    if not values.get("vat_account_id"):
        defaults = _default_vat_account_ids(db)
        default_id = defaults["input"] if tax_type == "INPUT" else defaults["output"]
        if default_id:
            values["vat_account_id"] = int(default_id)
    return values, errors


def _ensure_item_sales_price_nullable(db: Session):
    """Ensure dbo.items.sales_price can store NULL.

    V98 introduced blank Sales Price, but existing databases may still have
    sales_price as NOT NULL. Run a guarded, idempotent schema correction before
    saving Item Master so users are not forced to run the SQL manually.
    """
    try:
        db.execute(text("""
            IF OBJECT_ID(N'dbo.items', N'U') IS NOT NULL
               AND COL_LENGTH(N'dbo.items', N'sales_price') IS NOT NULL
            BEGIN
                DECLARE @constraint_name sysname;
                SELECT @constraint_name = dc.name
                FROM sys.default_constraints dc
                INNER JOIN sys.columns c ON c.default_object_id = dc.object_id
                INNER JOIN sys.tables t ON t.object_id = c.object_id
                INNER JOIN sys.schemas s ON s.schema_id = t.schema_id
                WHERE s.name = N'dbo'
                  AND t.name = N'items'
                  AND c.name = N'sales_price';

                IF @constraint_name IS NOT NULL
                BEGIN
                    DECLARE @drop_sql nvarchar(max);
                    SET @drop_sql = N'ALTER TABLE dbo.items DROP CONSTRAINT ' + QUOTENAME(@constraint_name);
                    EXEC sp_executesql @drop_sql;
                END;

                ALTER TABLE dbo.items ALTER COLUMN sales_price DECIMAL(19,4) NULL;

                IF NOT EXISTS (
                    SELECT 1
                    FROM sys.default_constraints dc
                    INNER JOIN sys.columns c ON c.default_object_id = dc.object_id
                    INNER JOIN sys.tables t ON t.object_id = c.object_id
                    INNER JOIN sys.schemas s ON s.schema_id = t.schema_id
                    WHERE s.name = N'dbo'
                      AND t.name = N'items'
                      AND c.name = N'sales_price'
                )
                BEGIN
                    ALTER TABLE dbo.items ADD CONSTRAINT DF_item_sales_price DEFAULT 0 FOR sales_price;
                END;
            END;
        """))
    except Exception:
        # Do not block save here. If the database user cannot alter schema,
        # the normal save error will still be shown and the SQL migration can be run manually.
        pass


def _sync_legacy_tax_account_columns(db: Session, tax_code_id: int):
    """Populate old input/output account columns from the new single VAT Account field.

    This keeps older queries/reports from failing while the UI and new services use vat_account_id.
    """
    db.execute(text("""
        IF COL_LENGTH(N'dbo.tax_codes', N'input_account_id') IS NOT NULL
           AND COL_LENGTH(N'dbo.tax_codes', N'output_account_id') IS NOT NULL
           AND COL_LENGTH(N'dbo.tax_codes', N'vat_account_id') IS NOT NULL
        BEGIN
            UPDATE dbo.tax_codes
            SET input_account_id = CASE WHEN tax_type = N'INPUT' THEN vat_account_id ELSE NULL END,
                output_account_id = CASE WHEN tax_type = N'OUTPUT' THEN vat_account_id ELSE NULL END
            WHERE id = :id;
        END
    """), {"id": tax_code_id})


def _normalize_item_values(values: dict):
    values = dict(values)
    item_type = str(values.get("item_type") or "").upper().strip()
    if item_type != "FINISHED":
        # Non-finished items are blocked from the standard Sales flow.
        # Scrap sale should be handled by a dedicated transaction later.
        values["can_be_sold"] = 0
        values["sale_channel_ids"] = []
        values["delivery_days"] = int(values.get("delivery_days") or 0)
    else:
        values["can_be_sold"] = 1 if values.get("can_be_sold") in (1, True, "1", "on", "true", "True") else 0
    values["estimate_receive_days"] = max(0, int(values.get("estimate_receive_days") or 0))
    values["delivery_days"] = max(0, int(values.get("delivery_days") or 0))
    try:
        values["profit_percent"] = max(0, parse_decimal(values.get("profit_percent") or 0))
    except Exception:
        values["profit_percent"] = Decimal("0")
    return values


def _template_context(request, user, db, entity, config, row=None, errors=None):
    master_numbering = MASTER_NUMBERING_CONFIG.get(entity)
    return {
        "request": request,
        "user": user,
        "entity": entity,
        "config": config,
        "row": row or _apply_defaults(config),
        "errors": errors or [],
        "account_options": _load_account_options(db),
        "coa_node_options": _load_coa_node_options(db),
        "customer_options": _load_customer_options(db),
        "warehouse_options": _load_warehouse_options(db),
        "tax_code_options": _load_tax_code_options(db),
        "input_tax_code_options": _load_input_tax_code_options(db),
        "output_tax_code_options": _load_output_tax_code_options(db),
        "asset_class_options": _load_asset_class_options(db),
        "sale_channel_options": _load_sale_channel_options(db),
        "unit_options": _load_unit_options(db),
        "item_unit_conversions": row.get("item_unit_conversions", []) if isinstance(row, dict) else [],
        "default_vat_accounts": _default_vat_account_ids(db),
        "entities": ENTITY_CONFIG,
        "master_numbering": master_numbering,
    }


def _resolve_master_numbering(entity: str, values: dict):
    numbering = MASTER_NUMBERING_CONFIG.get(entity)
    if not numbering:
        return None

    if numbering.get("object_code_field"):
        raw_object_value = str(values.get(numbering["object_code_field"]) or "").upper()
        object_code = numbering.get("object_code_map", {}).get(raw_object_value) or numbering.get("object_code")
    else:
        object_code = numbering.get("object_code")

    subkey_field = numbering.get("subkey_field")
    subkey = str(values.get(subkey_field) or "") if subkey_field else ""
    return {
        "object_code": object_code,
        "subkey": subkey,
        "code_field": numbering["code_field"],
    }


def _number_range_exists(db: Session, object_code: str, subkey: str) -> bool:
    row = db.execute(text("""
        SELECT COUNT(1) AS cnt
        FROM dbo.number_ranges
        WHERE object_code = :object_code
          AND subkey = :subkey
          AND is_active = 1
    """), {"object_code": object_code, "subkey": subkey or ""}).mappings().first()
    return bool(row and row["cnt"] > 0)


def _resolve_number_range_key(db: Session, entity: str, values: dict):
    resolved = _resolve_master_numbering(entity, values)
    if not resolved or not resolved.get("object_code"):
        raise ValueError("Master này chưa được cấu hình auto-numbering.")

    object_code = resolved["object_code"]
    subkey = resolved["subkey"] or ""

    # Prefer the specific subkey, e.g. ITEM/RAW, WAREHOUSE/STORE.
    # If it is not configured, gracefully fallback to blank subkey.
    if subkey and not _number_range_exists(db, object_code, subkey):
        subkey = ""

    return resolved, object_code, subkey


def _preview_master_code(db: Session, entity: str, values: dict) -> str:
    resolved, object_code, subkey = _resolve_number_range_key(db, entity, values)
    return NumberingService(db).preview(object_code=object_code, doc_date=date.today(), subkey=subkey)


def _consume_master_code(db: Session, entity: str, values: dict) -> str:
    resolved, object_code, subkey = _resolve_number_range_key(db, entity, values)
    return NumberingService(db).generate(object_code=object_code, doc_date=date.today(), subkey=subkey)


def _ensure_master_code_on_save(db: Session, entity: str, values: dict):
    resolved = _resolve_master_numbering(entity, values)
    if not resolved:
        return values

    values = dict(values)
    code_field = resolved["code_field"]
    current_code = str(values.get(code_field) or "").strip()

    if current_code == "":
        values[code_field] = _consume_master_code(db, entity, values)
    else:
        # If the user clicked Generate, the form contains the current preview.
        # Consume it on Save. If it is a manually-entered number, this returns False
        # and next_no remains unchanged.
        _, object_code, subkey = _resolve_number_range_key(db, entity, values)
        NumberingService(db).consume_if_current_preview(
            object_code=object_code,
            doc_date=date.today(),
            document_no=current_code,
            subkey=subkey,
        )
    return values


def _insert_row(db: Session, config, values):
    cols = _field_names(config)
    col_sql = ", ".join(cols)
    bind_sql = ", ".join([f":{c}" for c in cols])
    sql = text(f"INSERT INTO {config['table']} ({col_sql}) OUTPUT inserted.{config['pk']} VALUES ({bind_sql})")
    return db.execute(sql, values).scalar_one()


def _update_row(db: Session, config, row_id: int, values):
    cols = _field_names(config)
    set_sql = ", ".join([f"{c} = :{c}" for c in cols])
    values = dict(values)
    values["id"] = row_id
    sql = text(f"UPDATE {config['table']} SET {set_sql} WHERE {config['pk']} = :id")
    db.execute(sql, values)



# ---------------------------------------------------------------------------
# BOM / Recipe helpers
# ---------------------------------------------------------------------------

def _load_finished_good_options(db: Session):
    rows = db.execute(text("""
        SELECT id, item_code, item_name, base_uom
        FROM dbo.items
        WHERE is_active = 1 AND item_type = N'FINISHED'
        ORDER BY item_code
    """)).mappings().all()
    return [(str(r["id"]), f'{r["item_code"]} - {r["item_name"]} ({r["base_uom"]})') for r in rows]


def _load_component_item_options(db: Session):
    rows = db.execute(text("""
        SELECT id, item_code, item_name, item_type, base_uom
        FROM dbo.items
        WHERE is_active = 1
        ORDER BY CASE WHEN item_type = N'FINISHED' THEN 9 ELSE 1 END, item_type, item_code
    """)).mappings().all()
    return [(str(r["id"]), f'{r["item_code"]} - {r["item_name"]} [{r["item_type"]} / {r["base_uom"]}]') for r in rows]


def _bom_template_context(request, user, db, row=None, components=None, errors=None, is_copy=False):
    default_row = {
        "id": None,
        "bom_code": "",
        "finished_item_id": "",
        "version_no": "V1",
        "base_qty": Decimal("1"),
        "is_active": 1,
    }
    if row:
        default_row.update(dict(row))
    component_rows = components or []
    # Keep several blank rows available so users can define a BOM without adding rows manually first.
    while len(component_rows) < 6:
        component_rows.append({"component_item_id": "", "qty_per": "", "scrap_percent": "0"})
    return {
        "request": request,
        "user": user,
        "entity": "boms",
        "config": ENTITY_CONFIG["boms"],
        "row": default_row,
        "components": component_rows,
        "finished_good_options": _load_finished_good_options(db),
        "component_item_options": _load_component_item_options(db),
        "errors": errors or [],
        "entities": ENTITY_CONFIG,
        "is_copy": is_copy,
        "page_title": "BOM / Recipe",
    }


def _parse_bom_form(form):
    errors = []
    bom_code = str(form.get("bom_code") or "").strip()
    version_no = str(form.get("version_no") or "V1").strip() or "V1"
    is_active = 1 if form.get("is_active") in ("on", "1", "true", "True", "yes") else 0

    try:
        finished_item_id = int(str(form.get("finished_item_id") or "").strip())
    except ValueError:
        finished_item_id = None
        errors.append("Finished Good is required.")

    try:
        base_qty = parse_decimal(form.get("base_qty") or "1", "1")
        if base_qty <= 0:
            errors.append("Base Qty must be greater than 0.")
    except InvalidOperation:
        base_qty = Decimal("1")
        errors.append("Base Qty must be a valid number.")

    component_ids = form.getlist("component_item_id")
    qty_values = form.getlist("qty_per")
    scrap_values = form.getlist("scrap_percent")
    max_len = max(len(component_ids), len(qty_values), len(scrap_values), 0)
    components = []
    seen = set()

    for idx in range(max_len):
        raw_component = str(component_ids[idx] if idx < len(component_ids) else "").strip()
        raw_qty = str(qty_values[idx] if idx < len(qty_values) else "").strip()
        raw_scrap = str(scrap_values[idx] if idx < len(scrap_values) else "0").strip()

        # A fully blank line is ignored.
        if raw_component == "" and raw_qty == "" and raw_scrap in ("", "0", "0.0", "0.00"):
            continue

        try:
            component_item_id = int(raw_component)
        except ValueError:
            errors.append(f"Component line {idx + 1}: Component Item is required.")
            continue

        try:
            qty_per = Decimal(raw_qty)
            if qty_per <= 0:
                errors.append(f"Component line {idx + 1}: Qty Per must be greater than 0.")
        except InvalidOperation:
            qty_per = Decimal("0")
            errors.append(f"Component line {idx + 1}: Qty Per must be a valid number.")

        try:
            scrap_percent = Decimal(raw_scrap or "0")
            if scrap_percent < 0:
                errors.append(f"Component line {idx + 1}: Scrap % cannot be negative.")
        except InvalidOperation:
            scrap_percent = Decimal("0")
            errors.append(f"Component line {idx + 1}: Scrap % must be a valid number.")

        if component_item_id in seen:
            errors.append(f"Component line {idx + 1}: Component item is duplicated.")
        seen.add(component_item_id)

        components.append({
            "component_item_id": component_item_id,
            "qty_per": qty_per,
            "scrap_percent": scrap_percent,
        })

    if not components:
        errors.append("At least one component item is required for BOM.")

    header = {
        "bom_code": bom_code,
        "finished_item_id": finished_item_id,
        "version_no": version_no,
        "base_qty": base_qty,
        "is_active": is_active,
    }
    return header, components, errors


def _ensure_bom_code_on_save(db: Session, values: dict):
    values = dict(values)
    current_code = str(values.get("bom_code") or "").strip()
    numbering = NumberingService(db)
    if current_code == "":
        values["bom_code"] = numbering.generate(object_code="BOM", doc_date=date.today(), subkey="")
    else:
        numbering.consume_if_current_preview(object_code="BOM", doc_date=date.today(), document_no=current_code, subkey="")
    return values


def _insert_bom(db: Session, header: dict, components: list[dict]):
    bom_id = db.execute(text("""
        INSERT INTO dbo.boms(bom_code, finished_item_id, version_no, base_qty, is_active)
        OUTPUT inserted.id
        VALUES(:bom_code, :finished_item_id, :version_no, :base_qty, :is_active)
    """), header).scalar_one()
    for component in components:
        db.execute(text("""
            INSERT INTO dbo.bom_components(bom_id, component_item_id, qty_per, scrap_percent)
            VALUES(:bom_id, :component_item_id, :qty_per, :scrap_percent)
        """), {**component, "bom_id": bom_id})
    return bom_id


def _update_bom(db: Session, row_id: int, header: dict, components: list[dict]):
    header = dict(header)
    header["id"] = row_id
    db.execute(text("""
        UPDATE dbo.boms
        SET bom_code = :bom_code,
            finished_item_id = :finished_item_id,
            version_no = :version_no,
            base_qty = :base_qty,
            is_active = :is_active
        WHERE id = :id
    """), header)
    db.execute(text("DELETE FROM dbo.bom_components WHERE bom_id = :id"), {"id": row_id})
    for component in components:
        db.execute(text("""
            INSERT INTO dbo.bom_components(bom_id, component_item_id, qty_per, scrap_percent)
            VALUES(:bom_id, :component_item_id, :qty_per, :scrap_percent)
        """), {**component, "bom_id": row_id})


def _get_bom_header(db: Session, row_id: int):
    return db.execute(text("""
        SELECT id, bom_code, finished_item_id, version_no, base_qty, is_active
        FROM dbo.boms
        WHERE id = :id
    """), {"id": row_id}).mappings().first()


def _get_bom_components(db: Session, row_id: int):
    return [dict(r) for r in db.execute(text("""
        SELECT component_item_id, qty_per, scrap_percent
        FROM dbo.bom_components
        WHERE bom_id = :id
        ORDER BY id
    """), {"id": row_id}).mappings().all()]


def _bom_list_response(entity: str, request: Request, filters: dict, db: Session, user):
    params = {}
    where_sql = "WHERE 1=1"
    where_sql = _add_active_filter(where_sql, "b.is_active", filters.get("active_status", "ACTIVE"))
    where_sql = _add_code_range_filter(where_sql, params, "b.bom_code", filters.get("code_from", ""), filters.get("code_to", ""))
    q = filters.get("q", "")
    if q.strip():
        params["q"] = f"%{q.strip()}%"
        where_sql += """
            AND (
                b.bom_code LIKE :q
                OR b.version_no LIKE :q
                OR i.item_code LIKE :q
                OR i.item_name LIKE :q
            )
        """
    rows = db.execute(text(f"""
        SELECT TOP 300
            b.id,
            b.bom_code,
            i.item_code AS finished_item_code,
            i.item_name AS finished_item_name,
            b.version_no,
            b.base_qty,
            COUNT(c.id) AS component_count,
            b.is_active
        FROM dbo.boms b
        JOIN dbo.items i ON i.id = b.finished_item_id
        LEFT JOIN dbo.bom_components c ON c.bom_id = b.id
        {where_sql}
        GROUP BY b.id, b.bom_code, i.item_code, i.item_name, b.version_no, b.base_qty, b.is_active
        ORDER BY b.bom_code
    """), params).mappings().all()
    return templates.TemplateResponse("bom_list.html", {
        "request": request,
        "user": user,
        "entity": entity,
        "config": ENTITY_CONFIG["boms"],
        "rows": rows,
        "q": filters.get("q", ""),
        "filters": filters,
        "include_inactive": filters.get("include_inactive", 0),
        "entities": ENTITY_CONFIG,
        "page_title": "BOM / Recipe",
    })


def _bom_suggestions_response(q: str, limit: int, db: Session):
    q = q.strip()
    if not q:
        return JSONResponse({"items": []})
    limit = max(1, min(limit, 20))
    rows = db.execute(text(f"""
        SELECT TOP {limit}
            b.bom_code,
            i.item_code,
            i.item_name,
            b.version_no
        FROM dbo.boms b
        JOIN dbo.items i ON i.id = b.finished_item_id
        WHERE b.is_active = 1
          AND (b.bom_code LIKE :q OR i.item_code LIKE :q OR i.item_name LIKE :q OR b.version_no LIKE :q)
        ORDER BY CASE WHEN b.bom_code LIKE :starts THEN 0 ELSE 1 END, b.bom_code
    """), {"q": f"%{q}%", "starts": f"{q}%"}).mappings().all()
    return JSONResponse({
        "items": [
            {"value": r["bom_code"], "label": f'{r["bom_code"]} - {r["item_code"]} / {r["version_no"]} - {r["item_name"]}'}
            for r in rows
        ]
    })



def _resolve_master_active_status(active_status: str = "", include_inactive: int = 0) -> str:
    """Return ACTIVE / INACTIVE / ALL for master-data selection screens.

    Backward compatible with old include_inactive=1 query strings.
    """
    status = (active_status or "").strip().upper()
    if not status:
        status = "ALL" if include_inactive else "ACTIVE"
    if status not in {"ACTIVE", "INACTIVE", "ALL"}:
        status = "ACTIVE"
    return status


def _build_master_filters(q: str = "", code_from: str = "", code_to: str = "", active_status: str = "", include_inactive: int = 0) -> dict:
    status = _resolve_master_active_status(active_status, include_inactive)
    return {
        "q": (q or "").strip(),
        "code_from": (code_from or "").strip(),
        "code_to": (code_to or "").strip(),
        "active_status": status,
        "include_inactive": 1 if status == "ALL" else 0,
    }


def _add_active_filter(sql: str, column_expr: str, status: str) -> str:
    if status == "ACTIVE":
        return sql + f" AND {column_expr} = 1"
    if status == "INACTIVE":
        return sql + f" AND {column_expr} = 0"
    return sql


def _add_code_range_filter(sql: str, params: dict, column_expr: str, code_from: str = "", code_to: str = "") -> str:
    if (code_from or "").strip():
        params["code_from"] = code_from.strip()
        sql += f" AND {column_expr} >= :code_from"
    if (code_to or "").strip():
        params["code_to"] = code_to.strip()
        sql += f" AND {column_expr} <= :code_to"
    return sql

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("")
def master_index(request: Request, db: Session = Depends(get_db), user=Depends(require_permission("MASTER_VIEW"))):
    counts = {}
    for entity, config in ENTITY_CONFIG.items():
        try:
            row = db.execute(text(f"SELECT COUNT(1) AS total, SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) AS active_count FROM {config['table']}")).mappings().first()
            counts[entity] = {"total": row["total"] or 0, "active": row["active_count"] or 0}
        except Exception:
            counts[entity] = {"total": 0, "active": 0}

    return templates.TemplateResponse(
        "masters.html",
        {
            "request": request,
            "user": user,
            "entities": ENTITY_CONFIG,
            "counts": counts,
            "page_title": "Master Data",
        },
    )


@router.get("/{entity}")
def master_list(
    entity: str,
    request: Request,
    q: str = "",
    code_from: str = "",
    code_to: str = "",
    active_status: str = "",
    include_inactive: int = 0,
    db: Session = Depends(get_db),
    user=Depends(require_permission("MASTER_VIEW")),
):
    config = _get_entity(entity)
    if not config:
        return _safe_redirect("/masters", error="Master data entity không tồn tại.")
    filters = _build_master_filters(q, code_from, code_to, active_status, include_inactive)
    if entity == "boms":
        return _bom_list_response(entity, request, filters, db, user)

    if entity == "items":
        sql = """
            SELECT TOP 300
                i.id,
                i.item_code,
                i.item_name,
                i.item_type,
                i.base_uom,
                ISNULL(itc.tax_code, N'-') AS input_tax_code,
                ISNULL(otc.tax_code, N'-') AS output_tax_code,
                i.standard_cost,
                i.sales_price,
                ISNULL(i.estimate_receive_days, 0) AS estimate_receive_days,
                ISNULL(i.delivery_days, 0) AS delivery_days,
                ISNULL(i.can_be_sold, CASE WHEN i.item_type = N'FINISHED' THEN 1 ELSE 0 END) AS can_be_sold,
                i.is_active
            FROM dbo.items i
            LEFT JOIN dbo.tax_codes itc ON itc.id = i.input_tax_code_id
            LEFT JOIN dbo.tax_codes otc ON otc.id = i.output_tax_code_id
            WHERE 1=1
        """
        params = {}
        sql = _add_active_filter(sql, "i.is_active", filters["active_status"])
        sql = _add_code_range_filter(sql, params, "i.item_code", filters["code_from"], filters["code_to"])
        if filters["q"]:
            params["q"] = f"%{filters['q']}%"
            sql += """
                AND (
                    i.item_code LIKE :q
                    OR i.item_name LIKE :q
                    OR i.item_type LIKE :q
                    OR i.base_uom LIKE :q
                    OR itc.tax_code LIKE :q
                    OR itc.tax_name LIKE :q
                    OR otc.tax_code LIKE :q
                    OR otc.tax_name LIKE :q
                )
            """
        sql += " ORDER BY i.item_code"
        rows = db.execute(text(sql), params).mappings().all()
        return templates.TemplateResponse(
            "master_list.html",
            {
                "request": request,
                "user": user,
                "entity": entity,
                "config": config,
                "rows": rows,
                "q": filters["q"],
                "filters": filters,
                "include_inactive": filters["include_inactive"],
                "entities": ENTITY_CONFIG,
                "page_title": config["title"],
            },
        )

    if entity == "sale-channels":
        sql = """
            SELECT TOP 300
                sc.id,
                sc.channel_code,
                sc.channel_name,
                sc.channel_type,
                sc.external_source,
                ISNULL(tc.tax_code, N'-') AS default_tax_code,
                sc.is_active
            FROM dbo.sale_channels sc
            LEFT JOIN dbo.tax_codes tc ON tc.id = sc.default_tax_code_id
            WHERE 1=1
        """
        params = {}
        sql = _add_active_filter(sql, "sc.is_active", filters["active_status"])
        sql = _add_code_range_filter(sql, params, "sc.channel_code", filters["code_from"], filters["code_to"])
        if filters["q"]:
            params["q"] = f"%{filters['q']}%"
            sql += """
                AND (
                    sc.channel_code LIKE :q
                    OR sc.channel_name LIKE :q
                    OR sc.channel_type LIKE :q
                    OR sc.external_source LIKE :q
                    OR tc.tax_code LIKE :q
                    OR tc.tax_name LIKE :q
                )
            """
        sql += " ORDER BY sc.channel_code"
        rows = db.execute(text(sql), params).mappings().all()
        return templates.TemplateResponse(
            "master_list.html",
            {
                "request": request,
                "user": user,
                "entity": entity,
                "config": config,
                "rows": rows,
                "q": filters["q"],
                "filters": filters,
                "include_inactive": filters["include_inactive"],
                "entities": ENTITY_CONFIG,
                "page_title": config["title"],
            },
        )


    if entity == "fixed-assets":
        sql = """
            SELECT TOP 300
                v.id,
                v.asset_code,
                v.asset_name,
                v.asset_type,
                v.asset_class,
                v.acquisition_cost,
                v.accumulated_depreciation,
                v.net_book_value,
                v.asset_status,
                v.is_active
            FROM dbo.v_asset_nbv v
            WHERE 1=1
        """
        params = {}
        sql = _add_active_filter(sql, "v.is_active", filters["active_status"])
        sql = _add_code_range_filter(sql, params, "v.asset_code", filters["code_from"], filters["code_to"])
        if filters["q"]:
            params["q"] = f"%{filters['q']}%"
            sql += """
                AND (
                    v.asset_code LIKE :q
                    OR v.asset_name LIKE :q
                    OR v.asset_type LIKE :q
                    OR v.asset_class LIKE :q
                    OR v.asset_status LIKE :q
                )
            """
        sql += " ORDER BY v.asset_code"
        rows = db.execute(text(sql), params).mappings().all()
        return templates.TemplateResponse(
            "master_list.html",
            {
                "request": request,
                "user": user,
                "entity": entity,
                "config": config,
                "rows": rows,
                "q": filters["q"],
                "filters": filters,
                "include_inactive": filters["include_inactive"],
                "entities": ENTITY_CONFIG,
                "page_title": config["title"],
            },
        )

    select_cols = [config["pk"]] + [c[0] for c in config["list_columns"]]
    # Remove duplicate column names while keeping order.
    select_cols = list(dict.fromkeys(select_cols))
    sql = f"SELECT TOP 300 {', '.join(select_cols)} FROM {config['table']} WHERE 1=1"
    params = {}

    sql = _add_active_filter(sql, "is_active", filters["active_status"])
    sql = _add_code_range_filter(sql, params, config.get("code_field") or config["pk"], filters["code_from"], filters["code_to"])

    if filters["q"]:
        q_clauses = []
        for i, col in enumerate(config["search_columns"]):
            key = f"q{i}"
            q_clauses.append(f"{col} LIKE :{key}")
            params[key] = f"%{filters['q']}%"
        sql += " AND (" + " OR ".join(q_clauses) + ")"

    order_col = config.get("code_field") or config["pk"]
    sql += f" ORDER BY {order_col}"
    rows = db.execute(text(sql), params).mappings().all()

    return templates.TemplateResponse(
        "master_list.html",
        {
            "request": request,
            "user": user,
            "entity": entity,
            "config": config,
            "rows": rows,
            "q": filters["q"],
            "filters": filters,
            "include_inactive": filters["include_inactive"],
            "entities": ENTITY_CONFIG,
            "page_title": config["title"],
        },
    )


@router.get("/{entity}/new")
def master_new_form(
    entity: str,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_permission("MASTER_EDIT")),
):
    config = _get_entity(entity)
    if not config:
        return _safe_redirect("/masters", error="Master data entity không tồn tại.")
    if entity == "boms":
        return templates.TemplateResponse("bom_form.html", _bom_template_context(request, user, db))
    return templates.TemplateResponse("master_form.html", _template_context(request, user, db, entity, config))


# FastAPI does not provide sync request.form(); define POST handlers through explicit Form injection
# is too rigid for metadata-driven forms. The following helper endpoints use Starlette's async form
# parsing while still using SQLAlchemy sync sessions.

@router.post("/{entity}/save-new")
async def master_save_new(
    entity: str,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_permission("MASTER_EDIT")),
):
    config = _get_entity(entity)
    if not config:
        return _safe_redirect("/masters", error="Master data entity không tồn tại.")

    form = await request.form()
    if entity == "boms":
        header, components, errors = _parse_bom_form(form)
        if errors:
            return templates.TemplateResponse("bom_form.html", _bom_template_context(request, user, db, row=header, components=components, errors=errors))
        try:
            header = _ensure_bom_code_on_save(db, header)
            _insert_bom(db, header, components)
            db.commit()
            return _safe_redirect("/masters/boms", success="Đã tạo mới BOM / Recipe.")
        except IntegrityError:
            db.rollback()
            return templates.TemplateResponse("bom_form.html", _bom_template_context(request, user, db, row=header, components=components, errors=["BOM Code bị trùng hoặc Finished Good/Component Item không hợp lệ."]))
        except SQLAlchemyError as exc:
            db.rollback()
            return templates.TemplateResponse("bom_form.html", _bom_template_context(request, user, db, row=header, components=components, errors=[f"Không thể lưu BOM: {str(exc)[:300]}" ]))
        except Exception as exc:
            db.rollback()
            return templates.TemplateResponse("bom_form.html", _bom_template_context(request, user, db, row=header, components=components, errors=[str(exc)]))

    values, errors = _parse_form_data(config, form)
    if entity == "items":
        values = _normalize_item_values(values)
    if entity == "tax-codes":
        values, tax_errors = _normalize_tax_code_values(db, values)
        errors.extend(tax_errors)
    if errors:
        return templates.TemplateResponse("master_form.html", _template_context(request, user, db, entity, config, row=values, errors=errors))

    try:
        values = _ensure_master_code_on_save(db, entity, values)
        if entity == "items":
            _ensure_item_sales_price_nullable(db)
        new_id = _insert_row(db, config, values)
        if entity == "items":
            _sync_item_sale_channels(db, int(new_id), values)
            _sync_item_unit_conversions(db, int(new_id), values, form)
        if entity == "tax-codes":
            tax_id = db.execute(text("SELECT id FROM dbo.tax_codes WHERE tax_code = :tax_code"), {"tax_code": values.get("tax_code")}).scalar()
            if tax_id:
                _sync_legacy_tax_account_columns(db, int(tax_id))
        db.commit()
        return _safe_redirect(f"/masters/{entity}", success=f"Đã tạo mới {config['title']}.")
    except IntegrityError:
        db.rollback()
        return templates.TemplateResponse("master_form.html", _template_context(request, user, db, entity, config, row=values, errors=["Code bị trùng hoặc dữ liệu tham chiếu không hợp lệ."]))
    except SQLAlchemyError as exc:
        db.rollback()
        return templates.TemplateResponse("master_form.html", _template_context(request, user, db, entity, config, row=values, errors=[f"Không thể lưu dữ liệu: {str(exc)[:300]}"]))


@router.get("/{entity}/suggestions")
def master_suggestions(
    entity: str,
    q: str = "",
    limit: int = 10,
    db: Session = Depends(get_db),
    user=Depends(require_permission("MASTER_VIEW")),
):
    config = _get_entity(entity)
    if not config:
        return JSONResponse({"items": []})
    if entity == "boms":
        return _bom_suggestions_response(q, limit, db)

    q = q.strip()
    if not q:
        return JSONResponse({"items": []})

    limit = max(1, min(limit, 20))
    code_col = config.get("code_field") or config["search_columns"][0]
    label_col = None
    for col in config["search_columns"]:
        if col != code_col:
            label_col = col
            break
    label_col = label_col or code_col

    params = {}
    clauses = []
    for i, col in enumerate(config["search_columns"]):
        key = f"q{i}"
        clauses.append(f"{col} LIKE :{key}")
        params[key] = f"%{q}%"

    sql = f"""
        SELECT TOP {limit}
            CAST({code_col} AS NVARCHAR(200)) AS code,
            CAST({label_col} AS NVARCHAR(300)) AS label
        FROM {config['table']}
        WHERE is_active = 1 AND ({' OR '.join(clauses)})
        ORDER BY CASE WHEN {code_col} LIKE :starts THEN 0 ELSE 1 END, {code_col}
    """
    params["starts"] = f"{q}%"
    rows = db.execute(text(sql), params).mappings().all()
    return JSONResponse({
        "items": [
            {
                "value": r["code"],
                "label": f"{r['code']} - {r['label']}" if r["label"] and r["label"] != r["code"] else r["code"],
            }
            for r in rows
        ]
    })


@router.post("/{entity}/generate-code")
async def master_generate_code(
    entity: str,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_permission("MASTER_EDIT")),
):
    config = _get_entity(entity)
    if not config:
        return JSONResponse({"ok": False, "error": "Master data entity không tồn tại."}, status_code=404)

    form = await request.form()
    if entity == "boms":
        try:
            document_no = NumberingService(db).preview(object_code="BOM", doc_date=date.today(), subkey="")
            return JSONResponse({"ok": True, "code": document_no, "preview_only": True})
        except Exception as exc:
            db.rollback()
            return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)

    values, errors = _parse_form_data(config, form)
    try:
        document_no = _preview_master_code(db, entity, values)
        return JSONResponse({"ok": True, "code": document_no, "preview_only": True})
    except Exception as exc:
        db.rollback()
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)



@router.get("/{entity}/{row_id}")
def master_view_form(
    entity: str,
    row_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_permission("MASTER_VIEW")),
):
    config = _get_entity(entity)
    if not config:
        return _safe_redirect("/masters", error="Master data entity không tồn tại.")
    if entity == "boms":
        row = _get_bom_header(db, row_id)
        if not row:
            return _safe_redirect("/masters/boms", error="Không tìm thấy BOM cần xem.")
        components = _get_bom_components(db, row_id)
        ctx = _bom_template_context(request, user, db, row=dict(row), components=components)
        ctx["view_mode"] = True
        return templates.TemplateResponse("bom_form.html", ctx)

    cols = list(dict.fromkeys([config["pk"]] + _field_names(config)))
    row = db.execute(text(f"SELECT {', '.join(cols)} FROM {config['table']} WHERE {config['pk']} = :id"), {"id": row_id}).mappings().first()
    if not row:
        return _safe_redirect(f"/masters/{entity}", error="Không tìm thấy dữ liệu cần xem.")

    row_dict = dict(row)
    if entity == "items":
        row_dict["sale_channel_ids"] = _get_item_sale_channel_ids(db, row_id)
        row_dict["item_unit_conversions"] = _get_item_unit_conversions(db, row_id)
    ctx = _template_context(request, user, db, entity, config, row=row_dict)
    ctx["view_mode"] = True
    return templates.TemplateResponse("master_form.html", ctx)

@router.get("/{entity}/{row_id}/copy")
def master_copy_form(
    entity: str,
    row_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_permission("MASTER_EDIT")),
):
    config = _get_entity(entity)
    if not config:
        return _safe_redirect("/masters", error="Master data entity không tồn tại.")
    if entity == "boms":
        row = _get_bom_header(db, row_id)
        if not row:
            return _safe_redirect("/masters/boms", error="Không tìm thấy BOM cần copy.")
        copied = dict(row)
        copied["id"] = None
        copied["bom_code"] = ""
        copied["version_no"] = f"{copied.get('version_no') or 'V1'}-COPY"
        components = _get_bom_components(db, row_id)
        return templates.TemplateResponse("bom_form.html", _bom_template_context(request, user, db, row=copied, components=components, is_copy=True))

    cols = list(dict.fromkeys([config["pk"]] + _field_names(config)))
    row = db.execute(text(f"SELECT {', '.join(cols)} FROM {config['table']} WHERE {config['pk']} = :id"), {"id": row_id}).mappings().first()
    if not row:
        return _safe_redirect(f"/masters/{entity}", error="Không tìm thấy dữ liệu cần copy.")

    copied = dict(row)
    copied.pop(config["pk"], None)
    copied[config["pk"]] = None

    code_field = config.get("code_field")
    if code_field:
        copied[code_field] = ""

    # Make duplicated descriptions obvious without forcing users to retype everything.
    for name_key in ("item_name", "bp_name", "warehouse_name", "tax_name", "account_name", "node_name", "channel_name", "class_name", "asset_name"):
        if name_key in copied and copied[name_key]:
            copied[name_key] = f"{copied[name_key]} - Copy"
            break

    if entity == "items":
        copied["sale_channel_ids"] = _get_item_sale_channel_ids(db, row_id)
        copied["item_unit_conversions"] = _get_item_unit_conversions(db, row_id)
    return templates.TemplateResponse("master_form.html", _template_context(request, user, db, entity, config, row=copied))


@router.get("/{entity}/{row_id}/edit")
def master_edit_form(
    entity: str,
    row_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_permission("MASTER_EDIT")),
):
    config = _get_entity(entity)
    if not config:
        return _safe_redirect("/masters", error="Master data entity không tồn tại.")
    if entity == "boms":
        row = _get_bom_header(db, row_id)
        if not row:
            return _safe_redirect("/masters/boms", error="Không tìm thấy BOM cần sửa.")
        components = _get_bom_components(db, row_id)
        return templates.TemplateResponse("bom_form.html", _bom_template_context(request, user, db, row=dict(row), components=components))

    cols = list(dict.fromkeys([config["pk"]] + _field_names(config)))
    row = db.execute(text(f"SELECT {', '.join(cols)} FROM {config['table']} WHERE {config['pk']} = :id"), {"id": row_id}).mappings().first()
    if not row:
        return _safe_redirect(f"/masters/{entity}", error="Không tìm thấy dữ liệu cần sửa.")

    row_dict = dict(row)
    if entity == "items":
        row_dict["sale_channel_ids"] = _get_item_sale_channel_ids(db, row_id)
        row_dict["item_unit_conversions"] = _get_item_unit_conversions(db, row_id)
    return templates.TemplateResponse("master_form.html", _template_context(request, user, db, entity, config, row=row_dict))


@router.post("/{entity}/{row_id}/save")
async def master_save_edit(
    entity: str,
    row_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_permission("MASTER_EDIT")),
):
    config = _get_entity(entity)
    if not config:
        return _safe_redirect("/masters", error="Master data entity không tồn tại.")

    form = await request.form()
    if entity == "boms":
        header, components, errors = _parse_bom_form(form)
        if str(header.get("bom_code") or "").strip() == "":
            errors.append("BOM Code không được để trống khi chỉnh sửa dữ liệu đã tồn tại.")
        if errors:
            header["id"] = row_id
            return templates.TemplateResponse("bom_form.html", _bom_template_context(request, user, db, row=header, components=components, errors=errors))
        try:
            _update_bom(db, row_id, header, components)
            db.commit()
            return _safe_redirect("/masters/boms", success="Đã cập nhật BOM / Recipe.")
        except IntegrityError:
            db.rollback()
            header["id"] = row_id
            return templates.TemplateResponse("bom_form.html", _bom_template_context(request, user, db, row=header, components=components, errors=["BOM Code bị trùng hoặc dữ liệu tham chiếu không hợp lệ."]))
        except SQLAlchemyError as exc:
            db.rollback()
            header["id"] = row_id
            return templates.TemplateResponse("bom_form.html", _bom_template_context(request, user, db, row=header, components=components, errors=[f"Không thể lưu BOM: {str(exc)[:300]}" ]))

    values, errors = _parse_form_data(config, form)
    if entity == "items":
        values = _normalize_item_values(values)
    if entity == "tax-codes":
        values, tax_errors = _normalize_tax_code_values(db, values)
        errors.extend(tax_errors)

    resolved = _resolve_master_numbering(entity, values)
    if resolved and str(values.get(resolved["code_field"]) or "").strip() == "":
        errors.append("Code không được để trống khi chỉnh sửa dữ liệu đã tồn tại.")

    if errors:
        values["id"] = row_id
        return templates.TemplateResponse("master_form.html", _template_context(request, user, db, entity, config, row=values, errors=errors))

    try:
        if entity == "items":
            _ensure_item_sales_price_nullable(db)
        _update_row(db, config, row_id, values)
        if entity == "items":
            _sync_item_sale_channels(db, row_id, values)
            _sync_item_unit_conversions(db, row_id, values, form)
        if entity == "tax-codes":
            _sync_legacy_tax_account_columns(db, row_id)
        db.commit()
        return _safe_redirect(f"/masters/{entity}", success=f"Đã cập nhật {config['title']}.")
    except IntegrityError:
        db.rollback()
        values["id"] = row_id
        return templates.TemplateResponse("master_form.html", _template_context(request, user, db, entity, config, row=values, errors=["Code bị trùng hoặc dữ liệu tham chiếu không hợp lệ."]))
    except SQLAlchemyError as exc:
        db.rollback()
        values["id"] = row_id
        return templates.TemplateResponse("master_form.html", _template_context(request, user, db, entity, config, row=values, errors=[f"Không thể lưu dữ liệu: {str(exc)[:300]}"]))


@router.post("/{entity}/{row_id}/toggle")
def master_toggle_active(
    entity: str,
    row_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_permission("MASTER_EDIT")),
):
    config = _get_entity(entity)
    if not config:
        return _safe_redirect("/masters", error="Master data entity không tồn tại.")
    if entity == "boms":
        try:
            db.execute(text("UPDATE dbo.boms SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END WHERE id = :id"), {"id": row_id})
            db.commit()
            return _safe_redirect("/masters/boms?include_inactive=1", success="Đã cập nhật trạng thái BOM Active/Inactive.")
        except SQLAlchemyError as exc:
            db.rollback()
            return _safe_redirect("/masters/boms", error=f"Không thể cập nhật trạng thái: {str(exc)[:200]}")

    try:
        db.execute(text(f"UPDATE {config['table']} SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END WHERE {config['pk']} = :id"), {"id": row_id})
        db.commit()
        return _safe_redirect(f"/masters/{entity}?include_inactive=1", success="Đã cập nhật trạng thái Active/Inactive.")
    except SQLAlchemyError as exc:
        db.rollback()
        return _safe_redirect(f"/masters/{entity}", error=f"Không thể cập nhật trạng thái: {str(exc)[:200]}")
