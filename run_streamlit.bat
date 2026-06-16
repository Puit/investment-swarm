@echo off
cd /d "%~dp0"
echo Activando venv...
call venv\Scripts\activate.bat

echo Verificando yfinance...
python -c "import yfinance" 2>nul
if errorlevel 1 (
    echo Instalando yfinance...
    pip install yfinance==1.4.1
)

echo Lanzando Streamlit...
python -m streamlit run dashboard/dashboard.py
pause