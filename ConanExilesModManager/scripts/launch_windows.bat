@echo off
SETLOCAL ENABLEDELAYEDEXPANSION

REM Change to repo root (script lives in scripts\)
PUSHD %~dp0\..

IF NOT EXIST .venv (
  python -m venv .venv
  .venv\Scripts\python -m pip install --upgrade pip
  IF EXIST requirements.txt (
    .venv\Scripts\python -m pip install -r requirements.txt
  )
)

REM Activate venv and run
call .venv\Scripts\activate.bat
python main.pyw %*

ENDLOCAL
