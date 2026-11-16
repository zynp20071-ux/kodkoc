@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Gerekli kutuphaneler kontrol ediliyor...
echo (Ilk seferde 1-3 dakika surebilir, lutfen pencereyi kapatmayin.)
echo.
python -m pip install --disable-pip-version-check -r requirements.txt
echo.
echo KodKoc baslatiliyor, tarayicin birazdan acilacak...
echo Kullanirken bu siyah pencereyi KAPATMA. Isin bitince kapatabilirsin.
echo.
python app.py
echo.
pause
