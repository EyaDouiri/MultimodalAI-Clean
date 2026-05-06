@echo off
echo.
echo  Alia Backend - Demarrage
echo  ========================
cd /d %~dp0
pip install -r requirements.txt -q
python manage.py migrate --run-syncdb
daphne -b 127.0.0.1 -p 8000 alia_backend.asgi:application
pause
