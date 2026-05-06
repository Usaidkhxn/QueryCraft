import re
import zipfile
import shutil
import sqlite3
from pathlib import Path
from datetime import datetime

import pandas as pd

from app.config import DB_PATH, UPLOAD_DIR


def sanitize_name(name: str, max_len: int = 60) -> str:
    name = str(name).strip().lower()
    name = re.sub(r"[^a-z0-9]+", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    if not name:
        name = "unknown"
    return name[:max_len]


def clean_column_name(col) -> str:
    col = str(col).strip()
    col = re.sub(r"\s+", " ", col)

    lower = col.lower()

    if lower.startswith("unnamed"):
        return ""

    replacements = {
        "unit id": "unit_id",
        "unit id ": "unit_id",
        "unit id.": "unit_id",
        "unitid": "unit_id",
        "institution name": "institution_name",
        "institution name (n=5,059)": "institution_name",
        "institution name (n=1,726)": "institution_name",
        "institution name ": "institution_name",
        "institution name.": "institution_name",
        "institution name(n=5,059)": "institution_name",
        "institution name(n=1,726)": "institution_name",
        "institution name (n=5059)": "institution_name",
        "institution name (n=1726)": "institution_name",
        "institution name(n=5059)": "institution_name",
        "institution name(n=1726)": "institution_name",
        "institution name (n=5,059) ": "institution_name",
        "institution name (n=1,726) ": "institution_name",
        "instituton name": "institution_name",
        "institution name (n=1,726)": "institution_name",
        "institution name (n=5,059)": "institution_name",
        "institution name (n=5059)": "institution_name",
        "institution name (n=1726)": "institution_name",
        "institution name (n=13)": "institution_name",
    }

    if lower in replacements:
        return replacements[lower]

    return sanitize_name(col, max_len=80)


def dedupe_columns(columns):
    cleaned = []
    counts = {}

    unnamed_count = 1

    for col in columns:
        new_col = clean_column_name(col)

        if not new_col:
            new_col = f"category_{unnamed_count}"
            unnamed_count += 1

        if new_col in counts:
            counts[new_col] += 1
            new_col = f"{new_col}_{counts[new_col]}"
        else:
            counts[new_col] = 1

        cleaned.append(new_col)

    return cleaned


def is_year_column(col: str) -> bool:
    col = str(col).strip()

    patterns = [
        r"^fall_\d{4}$",
        r"^fall \d{4}$",
        r"^\d{4}$",
        r"^\d{4}_\d{2}$",
        r"^\d{4}-\d{2}$",
        r"^\d{4}_\d{4}$",
        r"^\d{4}-\d{4}$",
        r"^aug_31_\d{4}$",
        r"^aug 31, \d{4}$",
        r"^aug_\d{2}_\d{4}$",
    ]

    lower = col.lower()

    return any(re.match(pattern, lower) for pattern in patterns)


def extract_year_int(year_label: str):
    match = re.search(r"(20\d{2})", str(year_label))
    if match:
        return int(match.group(1))
    return None


def normalize_value(value):
    if pd.isna(value):
        return None, None

    text = str(value).strip()

    if text == "":
        return None, None

    if text.endswith("%"):
        try:
            return text, float(text.replace("%", "").replace(",", ""))
        except ValueError:
            return text, None

    try:
        numeric = float(str(value).replace(",", ""))
        return text, numeric
    except ValueError:
        return text, None


def get_conn():
    return sqlite3.connect(DB_PATH)


def ensure_core_tables():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS ingested_files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_name TEXT,
        sheet_name TEXT,
        raw_table_name TEXT,
        rows_loaded INTEGER,
        columns_loaded INTEGER,
        ingested_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS data_dictionary (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_file TEXT,
        source_sheet TEXT,
        table_name TEXT,
        column_name TEXT,
        detected_role TEXT,
        sample_values TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS metrics_long (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_file TEXT,
        source_sheet TEXT,
        source_table TEXT,
        metric_family TEXT,
        unit_id TEXT,
        institution_name TEXT,
        category_1 TEXT,
        category_2 TEXT,
        category_3 TEXT,
        metric_path TEXT,
        year_label TEXT,
        year_int INTEGER,
        value_text TEXT,
        value_numeric REAL
    )
    """)

    conn.commit()
    conn.close()


def detect_column_role(col: str):
    col_lower = col.lower()

    if col_lower == "unit_id":
        return "institution_id"

    if col_lower == "institution_name":
        return "institution_name"

    if is_year_column(col):
        return "year_value"

    if any(word in col_lower for word in ["category", "field", "metric", "level", "rank", "source", "functional", "race", "gender"]):
        return "dimension"

    return "attribute"


def sample_values_for_column(df: pd.DataFrame, col: str, limit: int = 5):
    values = (
        df[col]
        .dropna()
        .astype(str)
        .map(lambda x: x.strip())
    )
    values = [v for v in values.unique().tolist() if v != ""]
    return ", ".join(values[:limit])


def save_data_dictionary(df: pd.DataFrame, source_file: str, sheet_name: str, table_name: str):
    conn = get_conn()
    cur = conn.cursor()

    for col in df.columns:
        cur.execute(
            """
            INSERT INTO data_dictionary
            (source_file, source_sheet, table_name, column_name, detected_role, sample_values)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                source_file,
                sheet_name,
                table_name,
                col,
                detect_column_role(col),
                sample_values_for_column(df, col),
            )
        )

    conn.commit()
    conn.close()


def normalize_sheet_to_metrics_long(df: pd.DataFrame, source_file: str, sheet_name: str, raw_table_name: str):
    if df.empty:
        return 0

    columns = list(df.columns)

    year_cols = [col for col in columns if is_year_column(col)]
    if not year_cols:
        return 0

    unit_col = "unit_id" if "unit_id" in columns else None
    institution_col = "institution_name" if "institution_name" in columns else None

    dimension_cols = [
        col for col in columns
        if col not in year_cols and col not in [unit_col, institution_col]
    ]

    dimension_cols = dimension_cols[:3]

    for col in dimension_cols:
        df[col] = df[col].ffill()

    metric_family = sanitize_name(Path(source_file).stem, max_len=80)

    rows = []

    for _, row in df.iterrows():
        unit_id = str(row[unit_col]).strip() if unit_col and not pd.isna(row[unit_col]) else None
        institution_name = str(row[institution_col]).strip() if institution_col and not pd.isna(row[institution_col]) else None

        dims = []
        for col in dimension_cols:
            value = row[col]
            if pd.isna(value):
                dims.append(None)
            else:
                dims.append(str(value).strip())

        while len(dims) < 3:
            dims.append(None)

        metric_path = " | ".join([d for d in dims if d])

        for year_col in year_cols:
            value_text, value_numeric = normalize_value(row[year_col])

            if value_text is None and value_numeric is None:
                continue

            rows.append({
                "source_file": source_file,
                "source_sheet": sheet_name,
                "source_table": raw_table_name,
                "metric_family": metric_family,
                "unit_id": unit_id,
                "institution_name": institution_name,
                "category_1": dims[0],
                "category_2": dims[1],
                "category_3": dims[2],
                "metric_path": metric_path,
                "year_label": str(year_col),
                "year_int": extract_year_int(str(year_col)),
                "value_text": value_text,
                "value_numeric": value_numeric,
            })

    if not rows:
        return 0

    long_df = pd.DataFrame(rows)

    conn = get_conn()
    long_df.to_sql("metrics_long", conn, if_exists="append", index=False)
    conn.close()

    return len(rows)


def read_excel_sheets(file_path: Path):
    excel = pd.ExcelFile(file_path)
    sheets = []

    for sheet_name in excel.sheet_names:
        df = pd.read_excel(file_path, sheet_name=sheet_name, dtype=object)

        df = df.dropna(how="all")
        df = df.dropna(axis=1, how="all")

        if df.empty:
            continue

        df.columns = dedupe_columns(df.columns)

        sheets.append((sheet_name, df))

    return sheets


def ingest_excel_file(file_path: str):
    ensure_core_tables()

    file_path = Path(file_path)
    source_file = file_path.name

    ingested = []

    sheets = read_excel_sheets(file_path)

    for sheet_name, df in sheets:
        raw_table_name = f"raw_{sanitize_name(file_path.stem)}_{sanitize_name(sheet_name)}"

        conn = get_conn()
        df.to_sql(raw_table_name, conn, if_exists="replace", index=False)
        conn.close()

        save_data_dictionary(df, source_file, sheet_name, raw_table_name)

        long_rows = normalize_sheet_to_metrics_long(df, source_file, sheet_name, raw_table_name)

        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO ingested_files
            (file_name, sheet_name, raw_table_name, rows_loaded, columns_loaded, ingested_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                source_file,
                sheet_name,
                raw_table_name,
                len(df),
                len(df.columns),
                datetime.now().isoformat(timespec="seconds"),
            )
        )
        conn.commit()
        conn.close()

        ingested.append({
            "file": source_file,
            "sheet": sheet_name,
            "raw_table": raw_table_name,
            "raw_rows": len(df),
            "raw_columns": len(df.columns),
            "normalized_metric_rows": long_rows,
        })

    return ingested


def ingest_folder(folder_path: str):
    folder = Path(folder_path)

    if not folder.exists():
        raise FileNotFoundError(f"Folder not found: {folder_path}")

    files = list(folder.glob("*.xlsx")) + list(folder.glob("*.xls"))

    results = []

    for file_path in files:
        results.extend(ingest_excel_file(str(file_path)))

    return {
        "folder": str(folder),
        "files_found": len(files),
        "sheets_ingested": len(results),
        "details": results,
    }


def ingest_zip_file(zip_path: str):
    ensure_core_tables()

    zip_path = Path(zip_path)
    extract_dir = UPLOAD_DIR / sanitize_name(zip_path.stem)

    if extract_dir.exists():
        shutil.rmtree(extract_dir)

    extract_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(extract_dir)

    files = list(extract_dir.rglob("*.xlsx")) + list(extract_dir.rglob("*.xls"))

    results = []

    for file_path in files:
        results.extend(ingest_excel_file(str(file_path)))

    return {
        "zip_file": zip_path.name,
        "files_found": len(files),
        "sheets_ingested": len(results),
        "details": results,
    }


def get_ingestion_summary():
    ensure_core_tables()

    conn = get_conn()

    files = pd.read_sql_query(
        """
        SELECT file_name, sheet_name, raw_table_name, rows_loaded, columns_loaded, ingested_at
        FROM ingested_files
        ORDER BY id DESC
        """,
        conn
    ).to_dict(orient="records")

    metric_count = pd.read_sql_query(
        "SELECT COUNT(*) AS total_metric_rows FROM metrics_long",
        conn
    ).to_dict(orient="records")[0]

    families = pd.read_sql_query(
        """
        SELECT metric_family, COUNT(*) AS rows
        FROM metrics_long
        GROUP BY metric_family
        ORDER BY rows DESC
        """,
        conn
    ).to_dict(orient="records")

    conn.close()

    return {
        "files": files,
        "metric_rows": metric_count["total_metric_rows"],
        "metric_families": families,
    }