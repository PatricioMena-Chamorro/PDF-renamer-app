@echo off
echo ======================================
echo  PDF Renamer - Scientific Papers
echo ======================================

REM Crear entorno virtual si no existe
if not exist .venv (
    echo Creando entorno virtual...
    python -m venv .venv
)

REM Activar entorno virtual
call .venv\Scripts\activate

REM Instalar dependencias
echo Instalando dependencias...
pip install --upgrade pip
pip install -r requirements.txt

REM Ejecutar app
echo Iniciando la aplicacion...
streamlit run app.py

pause
