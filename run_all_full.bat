@echo off
setlocal ENABLEEXTENSIONS ENABLEDELAYEDEXPANSION
title NewBot — run_all_full (with alerts)
cd /d "%~dp0"

if not exist "venv" (
  echo [run_all_full] Creating venv...
  python -m venv "venv" || (echo Python not found & exit /b 1)
)
call "venv\Scripts\activate.bat"
python -m pip show uvicorn >NUL 2>&1 || pip install uvicorn fastapi pydantic httpx

echo [run_all_full] Starting services...
if exist "ai_llm_gateway\main.py"      start "gateway"           cmd /c "cd /d ai_llm_gateway      && ..\venv\Scripts\python -m uvicorn main:app --host 0.0.0.0 --port 8800 --reload"
if exist "ai_radar\main.py"            start "ai_radar"          cmd /c "cd /d ai_radar            && ..\venv\Scripts\python -m uvicorn main:app --host 0.0.0.0 --port 8750 --reload"
if exist "exchange_ingestor\main.py"   start "exchange_ingestor" cmd /c "cd /d exchange_ingestor   && ..\venv\Scripts\python -m uvicorn main:app --host 0.0.0.0 --port 8700 --reload"
if exist "trade_executor\main.py"      start "trade_executor"    cmd /c "cd /d trade_executor      && ..\venv\Scripts\python -m uvicorn main:app --host 0.0.0.0 --port 8600 --reload"
if exist "alerts\main.py"              start "alerts"            cmd /c "cd /d alerts              && ..\venv\Scripts\python -m uvicorn main:app --host 0.0.0.0 --port 8650 --reload"
if exist "backtester\main.py"          start "backtester"        cmd /c "cd /d backtester          && ..\venv\Scripts\python -m uvicorn main:app --host 0.0.0.0 --port 8900 --reload"

echo [run_all_full] Waiting 5 seconds for services to boot...
timeout /t 5 >nul

echo [run_all_full] Opening dashboard...
start "" "http://127.0.0.1:8800/dashboard_ops"

echo [run_all_full] Done. All modules launched.
exit /b 0
