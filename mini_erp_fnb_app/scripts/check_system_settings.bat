@echo off
cd /d "%~dp0.."
call .venv\Scripts\activate
python scripts\check_system_settings.py
pause
