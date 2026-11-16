@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo KodKoc testleri calistiriliyor...
echo (Testler gecici bir veritabani kullanir; gercek kayitlarina ve internete dokunmaz.)
echo.
python -m pip install -q --disable-pip-version-check -r requirements.txt pytest
python -m pytest -v
echo.
pause
