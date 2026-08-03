@echo off
REM Instala las dependencias y ejecuta la macro de GTA SA.
REM Ejecutar como administrador (el hook global de teclado lo requiere).

cd /d "%~dp0"

echo Instalando dependencias...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo Error instalando dependencias.
    pause
    exit /b 1
)

echo Iniciando macro...
python gta_sa_turbo.py
pause
