@echo off
cd /d C:\Mini-ERP\mini_erp_fnb_app
call .venv\Scripts\activate
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
