from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.db import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "dbo"}
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str | None] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ChartAccount(Base):
    __tablename__ = "chart_accounts"
    __table_args__ = {"schema": "dbo"}
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    account_code: Mapped[str] = mapped_column(String(30), unique=True)
    account_name: Mapped[str] = mapped_column(String(200))
    account_type: Mapped[str] = mapped_column(String(50))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Warehouse(Base):
    __tablename__ = "warehouses"
    __table_args__ = {"schema": "dbo"}
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    warehouse_code: Mapped[str] = mapped_column(String(30), unique=True)
    warehouse_name: Mapped[str] = mapped_column(String(200))
    warehouse_type: Mapped[str] = mapped_column(String(50), default="MAIN")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class BusinessPartner(Base):
    __tablename__ = "business_partners"
    __table_args__ = {"schema": "dbo"}
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    bp_code: Mapped[str] = mapped_column(String(50), unique=True)
    bp_name: Mapped[str] = mapped_column(String(250))
    bp_type: Mapped[str] = mapped_column(String(20))
    bp_category: Mapped[str] = mapped_column(String(30), default="COMPANY")
    phone: Mapped[str | None] = mapped_column(String(50))
    email: Mapped[str | None] = mapped_column(String(200))
    ar_account_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("dbo.chart_accounts.id"))
    ap_account_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("dbo.chart_accounts.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class TaxCode(Base):
    __tablename__ = "tax_codes"
    __table_args__ = {"schema": "dbo"}
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tax_code: Mapped[str] = mapped_column(String(30), unique=True)
    tax_name: Mapped[str] = mapped_column(String(200))
    tax_type: Mapped[str] = mapped_column(String(20), default="INPUT")
    rate: Mapped[Decimal] = mapped_column(Numeric(9, 4), default=0)
    vat_account_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("dbo.chart_accounts.id"))
    # Legacy columns kept for compatibility with older migrations/reports.
    input_account_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("dbo.chart_accounts.id"))
    output_account_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("dbo.chart_accounts.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Item(Base):
    __tablename__ = "items"
    __table_args__ = {"schema": "dbo"}
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    item_code: Mapped[str] = mapped_column(String(50), unique=True)
    item_name: Mapped[str] = mapped_column(String(250))
    item_type: Mapped[str] = mapped_column(String(30))
    base_uom: Mapped[str] = mapped_column(String(30))
    standard_cost: Mapped[Decimal] = mapped_column(Numeric(19, 4), default=0)
    sales_price: Mapped[Decimal | None] = mapped_column(Numeric(19, 4), nullable=True, default=None)
    inventory_account_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("dbo.chart_accounts.id"))
    cogs_account_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("dbo.chart_accounts.id"))
    revenue_account_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("dbo.chart_accounts.id"))
    wip_account_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("dbo.chart_accounts.id"))
    expiry_tracking: Mapped[bool] = mapped_column(Boolean, default=False)
    lot_tracking: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class InventoryMovement(Base):
    __tablename__ = "inventory_movements"
    __table_args__ = {"schema": "dbo"}
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    movement_no: Mapped[str] = mapped_column(String(50), unique=True)
    movement_date: Mapped[date] = mapped_column(Date)
    movement_type: Mapped[str] = mapped_column(String(50))
    source_doc_type: Mapped[str | None] = mapped_column(String(50))
    source_doc_id: Mapped[int | None] = mapped_column(BigInteger)
    item_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("dbo.items.id"))
    warehouse_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("dbo.warehouses.id"))
    lot_no: Mapped[str | None] = mapped_column(String(100))
    expiry_date: Mapped[date | None] = mapped_column(Date)
    qty_in: Mapped[Decimal] = mapped_column(Numeric(19, 4), default=0)
    qty_out: Mapped[Decimal] = mapped_column(Numeric(19, 4), default=0)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(19, 4), default=0)
    amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), default=0)
    notes: Mapped[str | None] = mapped_column(String(500))


class JournalEntry(Base):
    __tablename__ = "journal_entries"
    __table_args__ = {"schema": "dbo"}
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    je_no: Mapped[str] = mapped_column(String(50), unique=True)
    je_date: Mapped[date] = mapped_column(Date)
    source_doc_type: Mapped[str | None] = mapped_column(String(50))
    source_doc_id: Mapped[int | None] = mapped_column(BigInteger)
    memo: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(30), default="POSTED")
    created_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("dbo.users.id"))
    lines: Mapped[list["JournalEntryLine"]] = relationship(back_populates="header", cascade="all, delete-orphan")


class JournalEntryLine(Base):
    __tablename__ = "journal_entry_lines"
    __table_args__ = {"schema": "dbo"}
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    journal_entry_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("dbo.journal_entries.id"))
    line_no: Mapped[int] = mapped_column(Integer)
    account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("dbo.chart_accounts.id"))
    debit: Mapped[Decimal] = mapped_column(Numeric(19, 4), default=0)
    credit: Mapped[Decimal] = mapped_column(Numeric(19, 4), default=0)
    bp_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("dbo.business_partners.id"))
    item_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("dbo.items.id"))
    asset_id: Mapped[int | None] = mapped_column(BigInteger)
    memo: Mapped[str | None] = mapped_column(String(500))
    header: Mapped[JournalEntry] = relationship(back_populates="lines")


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    __table_args__ = {"schema": "dbo"}
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    po_no: Mapped[str] = mapped_column(String(50), unique=True)
    po_date: Mapped[date] = mapped_column(Date)
    vendor_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("dbo.business_partners.id"))
    status: Mapped[str] = mapped_column(String(30), default="DRAFT")
    total_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), default=0)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), default=0)
    grand_total: Mapped[Decimal] = mapped_column(Numeric(19, 4), default=0)
    created_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("dbo.users.id"))


class SalesOrder(Base):
    __tablename__ = "sales_orders"
    __table_args__ = {"schema": "dbo"}
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    so_no: Mapped[str] = mapped_column(String(50), unique=True)
    so_date: Mapped[date] = mapped_column(Date)
    customer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("dbo.business_partners.id"))
    status: Mapped[str] = mapped_column(String(30), default="DRAFT")
    channel_code: Mapped[str | None] = mapped_column(String(50))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), default=0)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), default=0)
    grand_total: Mapped[Decimal] = mapped_column(Numeric(19, 4), default=0)
    external_ref: Mapped[str | None] = mapped_column(String(100))
    created_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("dbo.users.id"))


class ProductionOrder(Base):
    __tablename__ = "production_orders"
    __table_args__ = {"schema": "dbo"}
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    prod_no: Mapped[str] = mapped_column(String(50), unique=True)
    prod_date: Mapped[date] = mapped_column(Date)
    finished_item_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("dbo.items.id"))
    bom_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("dbo.boms.id"))
    planned_qty: Mapped[Decimal] = mapped_column(Numeric(19, 4))
    completed_qty: Mapped[Decimal] = mapped_column(Numeric(19, 4), default=0)
    status: Mapped[str] = mapped_column(String(30), default="DRAFT")
    issue_warehouse_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("dbo.warehouses.id"))
    receipt_warehouse_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("dbo.warehouses.id"))
    created_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("dbo.users.id"))
