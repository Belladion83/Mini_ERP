from decimal import Decimal
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from app.core.config import get_settings
from app.api import auth, dashboard, masters, purchase, sales, inventory, production, accounting, integrations, admin

settings = get_settings()

app = FastAPI(title=settings.app_name)
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


def _format_decimal_vn(value, places=4, trim=True):
    """Format numbers using Vietnamese/ERP style: 1.234.567,89."""
    try:
        if value is None or value == "":
            return "0"
        number = Decimal(str(value))
        text = f"{number:,.{places}f}"
        if trim:
            text = text.rstrip("0").rstrip(".")
        # Python gives US style: 1,234.56. ERP/VN style requires 1.234,56.
        return text.replace(",", "_").replace(".", ",").replace("_", ".")
    except Exception:
        return value


def format_vnd(value):
    return _format_decimal_vn(value, places=0, trim=False)


def format_qty(value):
    return _format_decimal_vn(value, places=4, trim=True)


# Register filters on every Jinja2Templates instance used by routers.
for router_module in [dashboard, masters, purchase, sales, inventory, production, accounting, integrations, admin, auth]:
    if hasattr(router_module, "templates"):
        router_module.templates.env.filters["vnd"] = format_vnd
        router_module.templates.env.filters["qty"] = format_qty

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(masters.router)
app.include_router(purchase.router)
app.include_router(sales.router)
app.include_router(inventory.router)
app.include_router(production.router)
app.include_router(accounting.router)
app.include_router(integrations.router)
app.include_router(admin.router)


@app.on_event("startup")
async def print_runtime_settings():
    s = get_settings()
    print("[Mini ERP] .env file:", s.diagnostic_summary().get("env_file_path"))
    print("[Mini ERP] SQL Server:", s.sqlserver_effective_server)
    print("[Mini ERP] Database:", s.diagnostic_summary().get("sqlserver_database"))


@app.exception_handler(403)
async def forbidden_handler(request: Request, exc):
    return RedirectResponse("/login", status_code=303)
