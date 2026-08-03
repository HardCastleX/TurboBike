@echo off
REM Ejecuta la macro de GTA SA.
REM Ejecutar como administrador (el hook global de teclado lo requiere).

cd /d "%~dp0"

REM Comprueba si las dependencias ya estan instaladas.
python -c "import keyboard, pydirectinput" 2>nul
if errorlevel 1 (
    echo Instalando dependencias...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo Error instalando dependencias.
        pause
        exit /b 1
    )
) else (
    echo Dependencias ya instaladas.
)

echo Iniciando macro...
python gta_sa_turbo.py
pause
