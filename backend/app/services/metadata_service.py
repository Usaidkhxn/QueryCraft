from app.database import get_connection


def fetch_all_dict(sql: str, params=()):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(sql, params)
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def get_tables():
    rows = fetch_all_dict(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
    )
    return [row["name"] for row in rows]


def get_table_columns(table_name: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name});")
    columns = [row[1] for row in cursor.fetchall()]
    conn.close()
    return columns


def get_metric_families():
    return fetch_all_dict(
        """
        SELECT metric_family, COUNT(*) AS rows
        FROM metrics_long
        GROUP BY metric_family
        ORDER BY metric_family
        """
    )


def get_sample_metric_paths(limit_per_family: int = 25):
    families = get_metric_families()
    output = {}

    for family in families:
        metric_family = family["metric_family"]

        rows = fetch_all_dict(
            """
            SELECT metric_path, COUNT(*) AS rows
            FROM metrics_long
            WHERE metric_family = ?
              AND metric_path IS NOT NULL
              AND TRIM(metric_path) <> ''
            GROUP BY metric_path
            ORDER BY rows DESC
            LIMIT ?
            """,
            (metric_family, limit_per_family),
        )

        output[metric_family] = rows

    return output


def get_year_coverage():
    return fetch_all_dict(
        """
        SELECT metric_family, MIN(year_int) AS min_year, MAX(year_int) AS max_year
        FROM metrics_long
        WHERE year_int IS NOT NULL
        GROUP BY metric_family
        ORDER BY metric_family
        """
    )


def get_schema_context():
    schema_lines = []

    schema_lines.append("PRIMARY ANALYTICS TABLE:")
    schema_lines.append("Table: metrics_long")
    schema_lines.append(
        "Columns: source_file, source_sheet, source_table, metric_family, "
        "unit_id, institution_name, category_1, category_2, category_3, "
        "metric_path, year_label, year_int, value_text, value_numeric"
    )
    schema_lines.append("")
    schema_lines.append("Use metrics_long for uploaded Excel datasets.")
    schema_lines.append("Use value_numeric for calculations and comparisons.")
    schema_lines.append("Use value_text for text fields.")
    schema_lines.append("Use year_int for year filters.")
    schema_lines.append("Use institution_name for school names.")
    schema_lines.append("Use metric_path/category fields to filter sub-metrics.")
    schema_lines.append("")

    schema_lines.append("EXACT metric_family VALUES:")
    for row in get_metric_families():
        schema_lines.append(f"- {row['metric_family']} ({row['rows']} rows)")

    schema_lines.append("")
    schema_lines.append("YEAR COVERAGE BY metric_family:")
    for row in get_year_coverage():
        schema_lines.append(
            f"- {row['metric_family']}: {row['min_year']} to {row['max_year']}"
        )

    schema_lines.append("")
    schema_lines.append("SAMPLE metric_path VALUES BY metric_family:")
    sample_paths = get_sample_metric_paths()

    for family, paths in sample_paths.items():
        schema_lines.append(f"{family}:")
        if not paths:
            schema_lines.append("  - No metric_path values")
        else:
            for path in paths:
                schema_lines.append(f"  - {path['metric_path']}")

    schema_lines.append("")
    schema_lines.append("SUPPORT TABLES:")
    schema_lines.append("Table: data_dictionary")
    schema_lines.append(
        "Columns: source_file, source_sheet, table_name, column_name, detected_role, sample_values"
    )
    schema_lines.append("Table: ingested_files")
    schema_lines.append(
        "Columns: file_name, sheet_name, raw_table_name, rows_loaded, columns_loaded, ingested_at"
    )

    schema_lines.append("")
    schema_lines.append("CRITICAL RULES:")
    schema_lines.append("- When filtering metric_family, use the EXACT values listed above.")
    schema_lines.append("- Do not invent metric_family values like 'Total Enrollment'. Use 'total_enrollment'.")
    schema_lines.append("- For total enrollment questions, use metric_family = 'total_enrollment'.")
    schema_lines.append("- For financial aid questions, use metric_family = 'student_financial_aid'.")
    schema_lines.append("- For graduation rate questions, use metric_family = 'graduation_rate_bachelors_by_race_ethnicity'.")
    schema_lines.append("- For admissions questions, use metric_family = 'admissions'.")
    schema_lines.append("- For SAT questions, use metric_family = 'sat_test_scores'.")
    schema_lines.append("- For ACT questions, use metric_family = 'act_test_scores'.")

    return "\n".join(schema_lines)