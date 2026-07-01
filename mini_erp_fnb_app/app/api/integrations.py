from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.orm import Session
from pathlib import Path
import tempfile
from app.core.db import get_db
from app.core.permissions import require_permission
from app.integrations.csv_pos_connector import CSVPOSConnector

router = APIRouter(prefix="/integrations", tags=["integrations"])
templates = Jinja2Templates(directory="app/templates")


@router.get("")
def integrations_index(request: Request, db: Session = Depends(get_db), user=Depends(require_permission("INTEGRATION_VIEW"))):
    connections = db.execute(text("SELECT id, connection_code, connection_name, provider, is_active FROM dbo.integration_connections ORDER BY connection_code")).mappings().all()
    logs = db.execute(text("SELECT TOP 20 sync_type, started_at, finished_at, status, message, records_processed FROM dbo.integration_sync_logs ORDER BY id DESC")).mappings().all()
    return templates.TemplateResponse("integrations.html", {"request": request, "user": user, "connections": connections, "logs": logs})


@router.post("/csv-preview")
async def csv_preview(file: UploadFile = File(...), db: Session = Depends(get_db), user=Depends(require_permission("INTEGRATION_EDIT"))):
    suffix = Path(file.filename or "sales.csv").suffix or ".csv"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        temp_path = tmp.name
    connector = CSVPOSConnector(temp_path)
    sales = connector.pull_sales()
    # In a real implementation, map external item codes to internal item codes,
    # then call SalesService.create_quick_sale for each receipt.
    return {"records_detected": len(sales), "sample_refs": [s.external_ref for s in sales[:10]]}
