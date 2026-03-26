#!/bin/bash

# Navigate to the script's directory
cd "$(dirname "$0")"

# 1. Create the 'static' folder if it doesn't exist
mkdir -p static

# 2. Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# 3. Activate the environment and install/update requirements
echo "Activating environment and checking dependencies..."
source venv/bin/activate
pip install --upgrade pip
pip install streamlit duckdb pandas pymupdf plotly numpy

# 4. Run the Streamlit app
echo "Starting Research Catalog..."
# Using the specific flag for static serving found in your original script 
python3 -m streamlit run app.py --server.enableStaticServing true