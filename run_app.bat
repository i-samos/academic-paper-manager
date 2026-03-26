@echo off
:: Ensure we are in the correct folder 
cd /d "%~dp0"

:: 1. Create virtual environment if it doesn't exist
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

:: 2. Create the 'static' folder if it doesn't exist
if not exist "static" (
    echo Creating 'static' folder for PDFs...
    mkdir "static"
)

:: 3. Activate the environment and install/update requirements
echo Activating environment and checking dependencies...
call venv\Scripts\activate
pip install streamlit duckdb pandas pymupdf plotly numpy

:: 4. Run the Streamlit app 
:: Uses the specific flag for static file serving enabled in your original script 
echo Starting Research Catalog...
python -m streamlit run app.py --server.enableStaticServing true

:: Keep window open if it crashes 
pause