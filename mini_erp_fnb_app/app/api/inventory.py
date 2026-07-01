from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.core.permissions import require_permission
from app.services.inventory_service import InventoryService

router = APIRouter(prefix="/inventory", tags=["inventory"])
templates = Jinja2Templates(directory="app/templates")


@router.get("")
def inventory_index(request: Request, db: Session = Depends(get_db), user=Depends(require_permission("INVENTORY_VIEW"))):
    balances = db.execute(text("SELECT * FROM dbo.v_inventory_balance ORDER BY item_code, warehouse_code")).mappings().all()
    movements = InventoryService(db).stock_card()
    return templates.TemplateResponse("inventory.html", {"request": request, "user": user, "balances": balances, "movements": movements})
