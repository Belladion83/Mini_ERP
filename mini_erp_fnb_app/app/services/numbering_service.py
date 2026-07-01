from datetime import date
from sqlalchemy import text
from sqlalchemy.orm import Session


class NumberingService:
    def __init__(self, db: Session):
        self.db = db

    def preview(self, object_code: str, doc_date: date, subkey: str = "") -> str:
        """Preview the next document/master number without increasing next_no.

        Use this for UI Generate buttons. The number range is consumed only when
        the user actually saves the document/master data.
        """
        sql = text("""
            DECLARE @doc NVARCHAR(80);
            EXEC dbo.sp_PreviewDocumentNo
                @ObjectCode = :object_code,
                @Subkey = :subkey,
                @DocDate = :doc_date,
                @DocumentNo = @doc OUTPUT;
            SELECT @doc AS document_no;
        """)
        row = self.db.execute(sql, {
            "object_code": object_code,
            "subkey": subkey or "",
            "doc_date": doc_date,
        }).mappings().first()
        if not row or not row["document_no"]:
            raise ValueError(f"Cannot preview number for {object_code}/{subkey}")
        return row["document_no"]

    def generate(self, object_code: str, doc_date: date, subkey: str = "") -> str:
        """Consume the next number and increase next_no.

        Use this only inside save/posting operations. If the surrounding SQLAlchemy
        transaction is rolled back, the number-range increment is rolled back too.
        """
        sql = text("""
            DECLARE @doc NVARCHAR(80);
            EXEC dbo.sp_GenerateDocumentNo
                @ObjectCode = :object_code,
                @Subkey = :subkey,
                @DocDate = :doc_date,
                @DocumentNo = @doc OUTPUT;
            SELECT @doc AS document_no;
        """)
        row = self.db.execute(sql, {
            "object_code": object_code,
            "subkey": subkey or "",
            "doc_date": doc_date,
        }).mappings().first()
        if not row or not row["document_no"]:
            raise ValueError(f"Cannot generate number for {object_code}/{subkey}")
        return row["document_no"]

    def consume_if_current_preview(self, object_code: str, doc_date: date, document_no: str, subkey: str = "") -> bool:
        """Increase next_no only if document_no is exactly the current preview.

        This supports the workflow where a user clicks Generate, sees the code on
        the form, and later presses Save. Repeated Generate clicks do not increment;
        Save increments once when the generated code is persisted.
        """
        if not document_no:
            return False
        sql = text("""
            DECLARE @consumed BIT;
            EXEC dbo.sp_ConsumeDocumentNoIfMatch
                @ObjectCode = :object_code,
                @Subkey = :subkey,
                @DocDate = :doc_date,
                @DocumentNo = :document_no,
                @Consumed = @consumed OUTPUT;
            SELECT @consumed AS consumed;
        """)
        row = self.db.execute(sql, {
            "object_code": object_code,
            "subkey": subkey or "",
            "doc_date": doc_date,
            "document_no": document_no,
        }).mappings().first()
        return bool(row and row["consumed"])

    def ensure_unique(self, table_name: str, column_name: str, document_no: str) -> None:
        allowed_tables = {
            "purchase_requisitions", "purchase_orders", "goods_receipts", "ap_invoices", "vendor_payments",
            "sales_orders", "deliveries", "ar_invoices", "customer_receipts",
            "production_orders", "material_issues", "production_receipts",
            "inventory_movements", "journal_entries",
        }
        if table_name not in allowed_tables:
            raise ValueError("Invalid table for document number validation")
        sql = text(f"SELECT COUNT(1) AS cnt FROM dbo.{table_name} WHERE {column_name} = :document_no")
        row = self.db.execute(sql, {"document_no": document_no}).mappings().first()
        if row and row["cnt"] > 0:
            raise ValueError(f"Document number already exists: {document_no}")
