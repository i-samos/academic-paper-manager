# 📚 Research Catalog

An interactive, local-first dashboard built with **Python** and **Streamlit** to organize, categorize, and analyze your library of research papers. This tool manages metadata via **DuckDB** and provides automated PDF linking and visualization features.

## ✨ Key Features

* **Local Database Management**: Uses a local `research_data.db` powered by **DuckDB** for lightning-fast paper tracking without a heavy server setup.
* **Dynamic Categorization**: Create, rename, and manage custom categories like "Uncategorized" or user-defined labels to keep your research organized.
* **Smart Citation Formatting**: Automatically generates clean "Author et al., Year" citations from messy bibliography strings or semicolon-separated lists.
* **PDF Integration**: Automatically matches database entries to local PDF files in the `static/` folder using a slug-matching algorithm and provides direct links to open them.
* **Bulk Match & Assign**: Quickly find papers in your database by pasting a list of titles and batch-assigning them to specific categories.
* **Full-Text Extraction**: Extract and consolidate text from selected PDFs into a single `.txt` file for easy reading or LLM processing using **PyMuPDF**.
* **Visual Analytics**: Features an interactive **Plotly Bubble Matrix** showing paper distribution by category and publication year.
* **Windows Integration**: Includes functionality to open the specific folder location of a selected PDF directly from the UI using Windows Explorer.
* **Data Portability**: Export your filtered paper collections to **CSV** format for use in other tools.

## 🛠️ Requirements

To run this application, you will need:
* **Python 3**
* **Libraries**: `streamlit`, `duckdb`, `pandas`, `pymupdf` (fitz), `plotly`, `numpy`.

## 🚀 Installation & Usage

### Windows Setup
1. Clone this repository to your local machine.
2. Ensure you have a folder named `static` containing your PDF files.
3. Run the **`run_app.bat`** file. [cite_start]This script automatically navigates to the directory and launches the Streamlit server with static file serving enabled[cite: 1].

### Linux/macOS Setup
1. Create a virtual environment: `python3 -m venv venv`.
2. Activate it: `source venv/bin/activate`.
3. Install dependencies: `pip install streamlit duckdb pandas pymupdf plotly numpy`.
4. [cite_start]Run the app: `python3 -m streamlit run app.py --server.enableStaticServing true`[cite: 1].

## 📂 Project Structure

* **`app.py`**: The main application logic, database management, and UI.
* **`run_app.bat`**: Windows batch file to launch the application with the necessary flags[cite: 1].
* **`static/`**: Place your PDF files here. The app matches files to titles based on their filenames.
* **`research_data.db`**: The local DuckDB database file (created automatically on first run).
