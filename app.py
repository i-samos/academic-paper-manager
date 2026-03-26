import streamlit as st
import duckdb
import pandas as pd
import re
import os
import urllib.parse
import subprocess
import platform
import fitz  # PyMuPDF
import io

st.set_page_config(page_title="Research Catalog", layout="wide")

st.markdown('<style>[data-testid="stDataEditor"] > div {height: 70vh !important;}</style>', unsafe_allow_html=True)

DB_FILE = "research_data.db"
PDF_FOLDER = "library" 

def init_db():
    conn = duckdb.connect(DB_FILE)
    conn.execute("CREATE TABLE IF NOT EXISTS categories (name VARCHAR PRIMARY KEY)")
    conn.execute("INSERT OR IGNORE INTO categories VALUES ('Uncategorized')")
    conn.execute("CREATE TABLE IF NOT EXISTS research_papers (title VARCHAR, authors VARCHAR, year VARCHAR, category VARCHAR, doi VARCHAR)")
    cols = conn.execute("PRAGMA table_info('research_papers')").fetchall()
    if not any(col[1] == 'category' for col in cols):
        conn.execute("ALTER TABLE research_papers ADD COLUMN category VARCHAR DEFAULT 'Uncategorized'")
    conn.close()

def get_query(sql, params=None):
    conn = duckdb.connect(DB_FILE)
    df = conn.execute(sql, params).df() if params else conn.execute(sql).df()
    conn.close()
    return df

def run_sql(sql, params=None):
    conn = duckdb.connect(DB_FILE)
    conn.execute(sql, params) if params else conn.execute(sql)
    conn.close()

def make_citation_authors(authors, year):
    if pd.isna(authors) or not str(authors).strip():
        return ""

    text = str(authors).strip()

    def extract_surname(name):
        name = name.strip().strip("., ")
        if not name:
            return ""

        if "." in name:
            first_part = name.split(".", 1)[0].strip()
            if first_part and " " not in first_part:
                return first_part

        parts = name.split()
        return parts[-1].strip(".,") if parts else ""

    if ";" in text:
        text = text.replace(",", ".")
        text = re.sub(r"\s*;\s*", ", ", text)
        author_list = [a.strip() for a in text.split(",") if a.strip()]

    else:
        text = re.sub(r"\s+\band\b\s+", ", ", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*&\s*", ", ", text)
        author_list = [a.strip() for a in text.split(",") if a.strip()]

    if not author_list:
        return ""

    surnames = [extract_surname(a) for a in author_list if extract_surname(a)]

    if not surnames:
        return ""

    year_text = ""
    if pd.notna(year) and str(year).strip():
        m = re.search(r"\b\d{4}\b", str(year))
        year_text = m.group(0) if m else str(year).strip()

    if len(surnames) == 1:
        citation = surnames[0]
    elif len(surnames) == 2:
        citation = f"{surnames[0]} and {surnames[1]}"
    else:
        citation = f"{surnames[0]} et al."

    return f"{citation}, {year_text}" if year_text else citation
    
init_db()

# --- MODALS ---
@st.dialog("Manage Categories")
def manage_categories_modal():
    cats_df = get_query("SELECT name FROM categories ORDER BY name ASC")
    all_cats = cats_df['name'].tolist()
    st.subheader("Create New")
    new_c = st.text_input("New Category Name")
    if st.button("Add Category"):
        if new_c:
            run_sql("INSERT OR IGNORE INTO categories VALUES (?)", (new_c,))
            st.rerun()
    st.divider()
    manageable = [c for c in all_cats if c != 'Uncategorized']
    if manageable:
        target = st.selectbox("Select Category", manageable)
        edit_name = st.text_input("Rename to", value=target)
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Rename Everywhere"):
                run_sql("UPDATE research_papers SET category = ? WHERE category = ?", (edit_name, target))
                run_sql("INSERT OR IGNORE INTO categories VALUES (?)", (edit_name,))
                run_sql("DELETE FROM categories WHERE name = ?", (target,))
                st.rerun()
        with c2:
            if st.button("Delete Category"):
                run_sql("UPDATE research_papers SET category = 'Uncategorized' WHERE category = ?", (target,))
                run_sql("DELETE FROM categories WHERE name = ?", (target,))
                st.rerun()

@st.dialog("Bulk Match & Assign", width="large")
def bulk_match_modal():
    st.write("Paste your list to find matches in the DB.")
    pasted_text = st.text_area("Paste titles/list here...", height=150)
    master_cats = get_query("SELECT name FROM categories ORDER BY name ASC")['name'].tolist()
    if pasted_text:
        raw_lines = [line.strip() for line in pasted_text.split('\n') if line.strip()]
        all_matches = []
        conn = duckdb.connect(DB_FILE)
        for line in raw_lines:
            clean_line = re.sub(r'[*_\-]', '', line)
            clean_line = re.sub(r'\(.*?\d{4}\)', '', clean_line).strip()
            res = conn.execute("SELECT title, authors, category FROM research_papers WHERE title ILIKE ? OR ? ILIKE '%' || title || '%'", (f'%{clean_line}%', clean_line)).df()
            if not res.empty:
                res.columns = [c.lower() for c in res.columns]
                all_matches.append(res)
        conn.close()
        if all_matches:
            match_df = pd.concat(all_matches).drop_duplicates(subset=['title'])
            match_df.insert(0, "Apply", True)
            edited_match_df = st.data_editor(match_df, hide_index=True, width='stretch')
            target_cat = st.selectbox("Assign to:", master_cats)
            if st.button("Update Selected"):
                to_update = edited_match_df[edited_match_df["Apply"] == True]['title'].tolist()
                run_sql("UPDATE research_papers SET category = ? WHERE title IN ?", (target_cat, to_update))
                st.rerun()

@st.dialog("Add Paper", width="large")
def add_paper_modal():
    st.write("Manual paper entry")

    categories = get_query("SELECT name FROM categories ORDER BY name ASC")["name"].tolist()

    title = st.text_input("Title")
    authors = st.text_input("Authors")
    year = st.text_input("Year")
    category = st.selectbox("Category", categories)
    doi = st.text_input("DOI")

    c1, c2 = st.columns(2)

    with c1:
        if st.button("Save Paper", width='stretch'):
            if not title.strip():
                st.error("Title is required.")
            else:
                existing = get_query(
                    "SELECT * FROM research_papers WHERE lower(title) = lower(?)",
                    (title.strip(),)
                )

                if not existing.empty:
                    st.warning("A paper with this title already exists.")
                else:
                    run_sql(
                        """
                        INSERT INTO research_papers (title, authors, year, category, doi)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            title.strip(),
                            authors.strip(),
                            year.strip(),
                            category,
                            doi.strip()
                        )
                    )
                    st.success("Paper added successfully.")
                    st.rerun()

    with c2:
        if st.button("Cancel", width='stretch'):
            st.rerun()


@st.dialog("Edit Paper", width="large")
def edit_paper_modal(selected_row):
    st.write("Edit selected paper")

    schema_df = get_query("PRAGMA table_info('research_papers')")
    all_columns = schema_df["name"].tolist()

    if not all_columns:
        st.error("No columns found in research_papers.")
        return

    if "title" not in all_columns:
        st.error("The table must contain a 'title' column to identify the row.")
        return

    original_title = selected_row.get("title", "")

    edited_values = {}

    categories = []
    if "category" in all_columns:
        categories = get_query("SELECT name FROM categories ORDER BY name ASC")["name"].tolist()

    for col in all_columns:
        current_value = selected_row.get(col, "")
        if pd.isna(current_value):
            current_value = ""

        label = col.replace("_", " ").title()

        if col == "category" and categories:
            try:
                default_index = categories.index(current_value) if current_value in categories else 0
            except Exception:
                default_index = 0

            edited_values[col] = st.selectbox(label, categories, index=default_index, key=f"edit_{col}")
        else:
            edited_values[col] = st.text_input(label, value=str(current_value), key=f"edit_{col}")

    c1, c2 = st.columns(2)

    with c1:
        if st.button("Save Changes", width="stretch"):
            new_title = str(edited_values.get("title", "")).strip()

            if not new_title:
                st.error("Title is required.")
            else:
                duplicate = get_query(
                    """
                    SELECT *
                    FROM research_papers
                    WHERE lower(title) = lower(?) AND lower(title) != lower(?)
                    """,
                    (new_title, original_title)
                )

                if not duplicate.empty:
                    st.warning("Another paper with this title already exists.")
                else:
                    set_clause = ", ".join([f"{col} = ?" for col in all_columns])
                    values = [str(edited_values.get(col, "")).strip() for col in all_columns]

                    run_sql(
                        f"""
                        UPDATE research_papers
                        SET {set_clause}
                        WHERE title = ?
                        """,
                        tuple(values + [original_title])
                    )

                    st.success("Paper updated successfully.")
                    st.rerun()

    with c2:
        if st.button("Cancel Edit", width="stretch"):
            st.rerun()
            
            
            
# --- DATA REFRESH ---
df = get_query("SELECT * FROM research_papers")
df.columns = [c.lower() for c in df.columns]
df["cited_authors"] = df.apply(
    lambda row: make_citation_authors(row["authors"], row["year"]),
    axis=1
)

# --- SESSION STATE ---
if "selected_cat" not in st.session_state:
    st.session_state.selected_cat = "All"

# --- SIDEBAR ---
st.sidebar.subheader("📁 Categories")
cat_counts = get_query("SELECT c.name, COUNT(p.title) as count FROM categories c LEFT JOIN research_papers p ON c.name = p.category GROUP BY c.name ORDER BY c.name ASC")
total_papers = len(df)
all_label = f"📁 All ({total_papers})"
if st.sidebar.button(f"▶️ {all_label}" if st.session_state.selected_cat == "All" else all_label, width='stretch', type="primary" if st.session_state.selected_cat == "All" else "secondary"):
    st.session_state.selected_cat = "All"
    st.rerun()

for _, row in cat_counts.iterrows():
    c_name, c_count = row['name'], row['count']
    is_active = st.session_state.selected_cat == c_name
    if st.sidebar.button(f"▶️ {c_name} ({c_count})" if is_active else f"{c_name} ({c_count})", width='stretch', key=f"side_{c_name}", type="primary" if is_active else "secondary"):
        st.session_state.selected_cat = c_name
        st.rerun()

# --- TOP CONTROLS ---
top_c1, top_c2, top_c3, top_c4, top_c5, top_c6, top_c7 = st.columns([1, 1, 2.5, 1.2, 1.2, 1.2, 1.6])

with top_c1:
    if st.button("⚙️ Manage Categories", width='stretch'):
        manage_categories_modal()

with top_c2:
    if st.button("🔍 Bulk Match", width='stretch'):
        bulk_match_modal()

with top_c3:
    search = st.text_input(
        "🔍 Search",
        label_visibility="collapsed",
        placeholder="Search papers..."
    )

with top_c4:
    if st.button("➕ Add Paper", width='stretch'):
        add_paper_modal()

with top_c5:
    edit_paper_placeholder = st.container()

with top_c6:
    export_csv_placeholder = st.container()

with top_c7:
    generate_txt_placeholder = st.container()
        
# --- FILTERING ---
selected_cat = st.session_state.selected_cat
filtered_df = df.copy()
if selected_cat != "All":
    filtered_df = filtered_df[filtered_df['category'] == selected_cat]

if search:
    filtered_df = filtered_df[
        filtered_df['title'].str.contains(search, case=False, na=False) |
        filtered_df['authors'].str.contains(search, case=False, na=False)
    ]
    
# --- MAIN ROW 2: COLUMN VISIBILITY ---
st.write("Display Columns:")
all_cols = [c for c in df.columns if c.lower() != "select"]
cols_to_show = []
cb_cols = st.columns(len(all_cols))
for i, col_name in enumerate(all_cols):
    with cb_cols[i]:
        if st.checkbox(col_name.title(), value=True, key=f"vis_{col_name}"):
            cols_to_show.append(col_name)

# --- MAIN TABLE ---
st.subheader(f"Current View: {selected_cat} ({len(filtered_df)} papers)")

if not filtered_df.empty:
    select_all = st.checkbox("Select All Visible Rows", key="master_select_all")
    table_df = filtered_df.reset_index(drop=True)
    table_df.insert(0, "Select", select_all)

    def get_clean_slug(text, length=50):
        clean = re.sub(r'[^a-z0-9]', '', str(text).lower())
        return clean[:length]

    def find_pdf_file(title):
        if not title:
            return None

        target_slug = get_clean_slug(title)

        if os.path.exists("static"):
            for f in os.listdir("static"):
                if not f.lower().endswith(".pdf"):
                    continue

                file_slug = get_clean_slug(os.path.splitext(f)[0])

                if file_slug.startswith(target_slug) or target_slug.startswith(file_slug):
                    return os.path.abspath(os.path.join("static", f))

        return None

    def make_url(title):
        file_path = find_pdf_file(title)
        if file_path:
            return f"app/static/{urllib.parse.quote(os.path.basename(file_path))}"
        return None

    table_df.insert(1, "PDF", table_df["title"].apply(make_url))
    table_df.insert(2, "File Path", table_df["title"].apply(find_pdf_file))

    if "doi" in table_df.columns:
        table_df["doi"] = table_df["doi"].apply(
            lambda x: f"https://doi.org/{x}" if pd.notnull(x) and not str(x).startswith("http") else x
        )

    edited_df = st.data_editor(
        table_df[["Select", "PDF"] + cols_to_show],
        hide_index=True,
        width="stretch",
        column_config={
            "PDF": st.column_config.LinkColumn(
                "PDF",
                display_text="🟢 Open",
                help="If empty, the file was not found in the 'static' folder."
            ),
            "doi": st.column_config.LinkColumn("DOI"),
            "File Path": None
        },
        disabled=[c for c in (["PDF"] + cols_to_show) if c != "Select"]
    )

    selected_indices = edited_df[edited_df["Select"] == True].index.tolist()
    selected_rows = table_df.loc[selected_indices].copy()

    export_cols = [c for c in cols_to_show if c in selected_rows.columns]
    export_df = selected_rows[export_cols].copy()

    clean_cat_name = re.sub(r'[^a-zA-Z0-9]', '_', selected_cat).lower()

    with edit_paper_placeholder:
        edit_clicked = st.button(
            "✏️ Edit Paper",
            width="stretch",
            disabled=len(selected_rows) != 1
        )
    if edit_clicked:
        selected_row = selected_rows.iloc[0].to_dict()
        edit_paper_modal(selected_row)
        
    with export_csv_placeholder:
        st.download_button(
            label="📥 Export CSV",
            data=export_df.to_csv(index=False).encode("utf-8"),
            file_name=f"research_papers_{clean_cat_name}_selected.csv",
            mime="text/csv",
            width="stretch",
            disabled=export_df.empty
        )

    txt_download_data = None

    with generate_txt_placeholder:
        txt_c1, txt_c2 = st.columns([4, 1])

        with txt_c1:
            generate_txt_clicked = st.button(
                "📝 Generate TXT",
                width="stretch",
                disabled=selected_rows.empty
            )

        if generate_txt_clicked:
            all_text = ""

            for _, row in selected_rows.iterrows():
                title = row["title"]
                file_path = find_pdf_file(title)

                if file_path and os.path.exists(file_path):
                    try:
                        doc = fitz.open(file_path)

                        all_text += "\n\n<<<PAPER_START>>>\n"
                        all_text += f"TITLE: {title}\n"
                        all_text += f"FILENAME: {os.path.basename(file_path)}\n"
                        all_text += "<<<CONTENT_START>>>\n\n"

                        for page in doc:
                            all_text += page.get_text()

                        all_text += "\n<<<PAPER_END>>>\n"
                        doc.close()

                    except Exception as e:
                        st.error(f"Error reading {title}: {e}")
                else:
                    st.warning(f"No PDF found in static folder for: {title}")

            if all_text:
                st.session_state["txt_download_data"] = all_text.encode("utf-8")
            else:
                st.session_state["txt_download_data"] = None

        with txt_c2:
            st.download_button(
                label="⬇",
                data=st.session_state.get("txt_download_data", b""),
                file_name=f"{clean_cat_name}_selected_papers.txt",
                mime="text/plain",
                width="stretch",
                disabled=st.session_state.get("txt_download_data") is None
            )

    st.write("### 📂 Open file in folder (Selected Only)")

    if selected_rows.empty:
        st.info("No files selected.")
    else:
        for i, row in selected_rows.reset_index(drop=True).iterrows():

            title = row["title"]
            file_path = find_pdf_file(title)  # 🔥 Recalculate properly

            if file_path:
                if st.button(f"Show in Folder: {title[:80]}", key=f"show_folder_selected_{i}"):

                    if platform.system() == "Windows":
                        subprocess.run(f'explorer /select,"{file_path}"', check=False)
                    else:
                        st.warning("Show in folder is currently set up for Windows only.")
            else:
                st.warning(f"No PDF found in static folder for: {title}")

# --- BUBBLE MATRIX: Papers per Category per Year ---
st.divider()
with st.expander("📊 Papers per Category per Year", expanded=False):

    raw = get_query("""
        SELECT
            REGEXP_REPLACE(TRIM(category), '\\s+(new|New)$', '') AS category,
            CAST(year AS INTEGER) AS year,
            COUNT(*) AS count
        FROM research_papers
        WHERE year IS NOT NULL AND TRIM(year) != ''
          AND category IS NOT NULL AND TRIM(category) != ''
          AND year ~ '^[0-9]{4}$'
        GROUP BY 1, 2
        ORDER BY 1, 2
    """)

    if raw.empty:
        st.info("No data available.")
    else:
        import plotly.graph_objects as go
        import numpy as np

        # Aggregate merged categories (after regex, some rows may now share a name)
        agg = raw.groupby(['category', 'year'], as_index=False)['count'].sum()

        cats = sorted(agg['category'].unique())
        years = sorted(agg['year'].unique())

        # Build a lookup for fast access
        lookup = {(r['category'], r['year']): r['count'] for _, r in agg.iterrows()}
        max_count = agg['count'].max()

        # Bubble size scaling: area ∝ count
        MAX_BUBBLE = 28
        def bubble_size(n):
            return MAX_BUBBLE * (n / max_count) ** 0.5

        # Build scatter traces — one per category for clean hover
        fig = go.Figure()

        # Vertical gridlines (one per year)
        for yr in years:
            fig.add_vline(x=yr, line_width=1, line_dash="dot", line_color="rgba(150,150,150,0.25)")

        xs, ys, sizes, texts, hovers = [], [], [], [], []
        for cat in cats:
            for yr in years:
                n = lookup.get((cat, yr), 0)
                if n > 0:
                    xs.append(yr)
                    ys.append(cat)
                    sizes.append(bubble_size(n))
                    texts.append(str(n))
                    hovers.append(f"<b>{cat}</b><br>Year: {yr}<br>Papers: {n}")

        fig.add_trace(go.Scatter(
            x=xs, y=ys,
            mode='markers+text',
            marker=dict(
                size=sizes,
                sizemode='diameter',
                color=sizes,
                colorscale=[
                    [0.0,  '#9FE1CB'],
                    [0.33, '#5DCAA5'],
                    [0.66, '#1D9E75'],
                    [1.0,  '#085041'],
                ],
                showscale=False,
                line=dict(width=0),
            ),
            text=texts,
            textposition='middle center',
            textfont=dict(color='white', size=11),
            hovertemplate='%{customdata}<extra></extra>',
            customdata=hovers,
        ))

        fig.update_layout(
            xaxis=dict(
                title='Year',
                tickmode='array',
                tickvals=years,
                ticktext=[str(y) for y in years],
                tickangle=0,
                showgrid=False,
                zeroline=False,
            ),
            yaxis=dict(
                title='',
                autorange='reversed',
                showgrid=False,
                zeroline=False,
            ),
            height=max(400, len(cats) * 38 + 80),
            margin=dict(l=260, r=30, t=30, b=60),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            hoverlabel=dict(bgcolor='white', font_size=13),
        )

        st.plotly_chart(fig, width='stretch')
