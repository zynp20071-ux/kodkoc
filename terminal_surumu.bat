@echo off
chcp 65001 >nul
cd /d "%~dp0"
python -m pip install -q --disable-pip-version-check -r requirements.txt
python kodkoc.py
echo.
pause
