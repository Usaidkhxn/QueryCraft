import re
import requests
from app.config import OLLAMA_URL, OLLAMA_MODEL


def clean_generated_sql(sql: str) -> str:
    sql = sql.strip()
    sql = sql.replace("```sql", "").replace("```", "").strip()

    # Fix bad model output like: ORDER BY year_int; LIMIT 100
    sql = re.sub(r";\s*LIMIT", " LIMIT", sql, flags=re.IGNORECASE)

    # Keep only one SQL statement
    parts = [part.strip() for part in sql.split(";") if part.strip()]
    if parts:
        sql = parts[0]

    return sql.strip() + ";"


def extract_year(user_query: str, default_year: int | None = None):
    matches = re.findall(r"20\d{2}", user_query)

    if matches:
        return int(matches[0])

    return default_year


def map_academic_year_for_aid_and_degrees(year: int | None):
    """
    Student financial aid and degrees files use academic-year columns:
    2023-24, 2022-23, etc.

    During ingestion:
    2023-24 becomes year_int = 2023.

    So when the user says 2024 for these files, we map it to 2023.
    """
    if year is None:
        return 2023

    if year == 2024:
        return 2023

    return year


def detect_financial_aid_measure(q: str):
    if "pell" in q:
        return "Pell grants"

    if "other federal" in q:
        return "Other Federal grants"

    if "federal grant" in q or "federal grants" in q:
        return "Federal grants"

    if "state" in q or "local" in q:
        return "State/Local grants"

    if "institutional" in q:
        return "Institutional grants"

    if "federal student loan" in q or "federal student loans" in q:
        return "Federal student loans"

    if "other student loan" in q or "other student loans" in q:
        return "Other student loans"

    if "student loan" in q or "student loans" in q or "loan" in q:
        return "Student loans"

    if "any aid" in q or "financial aid" in q or "aid" in q:
        return "Any Aid"

    return None


def detect_financial_aid_stat(q: str, aid_measure: str):
    """
    Student financial aid rows usually have:
    - Percent
    - Average amount
    - Total only for first-time full-time undergraduates

    For Any Aid, only Percent is available.
    """
    if aid_measure == "Any Aid":
        return "Percent"

    if "average" in q or "amount" in q or "dollar" in q or "$" in q:
        return "Average amount"

    if (
        "percent" in q
        or "percentage" in q
        or "rate" in q
        or "receiving" in q
        or "received" in q
        or "taking" in q
    ):
        return "Percent"

    # Default for grants/loans when user says "Pell grants by institution"
    return "Percent"


def detect_sat_measure(q: str):
    if "submitted" in q or "submit" in q:
        if "percent" in q or "percentage" in q:
            return "Enrolled students who submitted SAT test scores - Percent"
        return "Enrolled students who submitted SAT test scores - Number"

    if "number" in q and "sat" in q:
        return "Enrolled students who submitted SAT test scores - Number"

    if "percent" in q and "sat" in q:
        return "Enrolled students who submitted SAT test scores - Percent"

    if "math" in q:
        if "25" in q or "25th" in q:
            return "SAT Math - 25th Percentile"
        if "75" in q or "75th" in q:
            return "SAT Math - 75th Percentile"
        return "SAT Math - 75th Percentile"

    if "verbal" in q or "reading" in q or "evidence" in q:
        if "25" in q or "25th" in q:
            return "SAT Verbal - 25th Percentile"
        if "75" in q or "75th" in q:
            return "SAT Verbal - 75th Percentile"
        return "SAT Verbal - 75th Percentile"

    return None


def detect_act_measure(q: str):
    if "submitted" in q or "submit" in q:
        if "percent" in q or "percentage" in q:
            return "Students submitting ACT scores - Percent"
        return "Students submitting ACT scores - Number"

    if "number" in q and "act" in q:
        return "Students submitting ACT scores - Number"

    if "percent" in q and "act" in q:
        return "Students submitting ACT scores - Percent"

    section = "Composite"

    if "english" in q:
        section = "English"
    elif "math" in q:
        section = "Math"
    elif "composite" in q:
        section = "Composite"

    if "25" in q or "25th" in q:
        return f"ACT {section} - 25th Percentile"

    if "75" in q or "75th" in q:
        return f"ACT {section} - 75th Percentile"

    return "ACT Composite - 75th Percentile"


def rule_based_sql(user_query: str):
    q = user_query.lower()
    year = extract_year(user_query)

    wants_trend = (
        "trend" in q
        or "over time" in q
        or "from" in q and "to" in q
    )

    # -----------------------------
    # Student Financial Aid
    # -----------------------------
    if "financial aid" in q or "pell" in q or "grant" in q or "loan" in q:
        aid_year = map_academic_year_for_aid_and_degrees(year)
        aid_measure = detect_financial_aid_measure(q)

        if aid_measure:
            aid_stat = detect_financial_aid_stat(q, aid_measure)

            if wants_trend and "rowan" in q:
                return f"""
SELECT DISTINCT institution_name, year_int, value_numeric
FROM metrics_long
WHERE metric_family = 'student_financial_aid'
  AND category_1 = '{aid_measure}'
  AND category_2 = '{aid_stat}'
  AND institution_name = 'Rowan University'
  AND value_numeric IS NOT NULL
ORDER BY year_int ASC
LIMIT 100;
"""

            if wants_trend:
                return f"""
SELECT DISTINCT institution_name, year_int, value_numeric
FROM metrics_long
WHERE metric_family = 'student_financial_aid'
  AND category_1 = '{aid_measure}'
  AND category_2 = '{aid_stat}'
  AND institution_name IS NOT NULL
  AND value_numeric IS NOT NULL
ORDER BY institution_name, year_int
LIMIT 500;
"""

            return f"""
SELECT DISTINCT institution_name, year_int, value_numeric
FROM metrics_long
WHERE metric_family = 'student_financial_aid'
  AND category_1 = '{aid_measure}'
  AND category_2 = '{aid_stat}'
  AND year_int = {aid_year}
  AND institution_name IS NOT NULL
  AND value_numeric IS NOT NULL
ORDER BY value_numeric DESC
LIMIT 100;
"""

    # -----------------------------
    # SAT
    # -----------------------------
    if "sat" in q:
        sat_year = year or 2024
        sat_measure = detect_sat_measure(q)

        if sat_measure:
            if wants_trend and "rowan" in q:
                return f"""
SELECT DISTINCT institution_name, year_int, value_numeric
FROM metrics_long
WHERE metric_family = 'sat_test_scores'
  AND category_1 = '{sat_measure}'
  AND institution_name = 'Rowan University'
  AND value_numeric IS NOT NULL
ORDER BY year_int ASC
LIMIT 100;
"""

            if wants_trend:
                return f"""
SELECT DISTINCT institution_name, year_int, value_numeric
FROM metrics_long
WHERE metric_family = 'sat_test_scores'
  AND category_1 = '{sat_measure}'
  AND institution_name IS NOT NULL
  AND value_numeric IS NOT NULL
ORDER BY institution_name, year_int
LIMIT 500;
"""

            return f"""
SELECT DISTINCT institution_name, year_int, value_numeric
FROM metrics_long
WHERE metric_family = 'sat_test_scores'
  AND category_1 = '{sat_measure}'
  AND year_int = {sat_year}
  AND institution_name IS NOT NULL
  AND value_numeric IS NOT NULL
ORDER BY value_numeric DESC
LIMIT 100;
"""

        # Generic SAT query: keep the measure column so results are meaningful.
        return f"""
SELECT DISTINCT institution_name, category_1 AS sat_measure, year_int, value_numeric
FROM metrics_long
WHERE metric_family = 'sat_test_scores'
  AND year_int = {sat_year}
  AND institution_name IS NOT NULL
  AND value_numeric IS NOT NULL
ORDER BY institution_name, sat_measure
LIMIT 500;
"""

    # -----------------------------
    # ACT
    # -----------------------------
    if "act" in q:
        act_year = year or 2024
        act_measure = detect_act_measure(q)

        if wants_trend and "rowan" in q:
            return f"""
SELECT DISTINCT institution_name, year_int, value_numeric
FROM metrics_long
WHERE metric_family = 'act_test_scores'
  AND category_1 = '{act_measure}'
  AND institution_name = 'Rowan University'
  AND value_numeric IS NOT NULL
ORDER BY year_int ASC
LIMIT 100;
"""

        if wants_trend:
            return f"""
SELECT DISTINCT institution_name, year_int, value_numeric
FROM metrics_long
WHERE metric_family = 'act_test_scores'
  AND category_1 = '{act_measure}'
  AND institution_name IS NOT NULL
  AND value_numeric IS NOT NULL
ORDER BY institution_name, year_int
LIMIT 500;
"""

        return f"""
SELECT DISTINCT institution_name, year_int, value_numeric
FROM metrics_long
WHERE metric_family = 'act_test_scores'
  AND category_1 = '{act_measure}'
  AND year_int = {act_year}
  AND institution_name IS NOT NULL
  AND value_numeric IS NOT NULL
ORDER BY value_numeric DESC
LIMIT 100;
"""

    return None


def generate_sql(user_query: str, schema: str) -> str:
    deterministic_sql = rule_based_sql(user_query)

    if deterministic_sql:
        return clean_generated_sql(deterministic_sql)

    prompt = f"""
You are QueryCraft's SQL generator for an analytics chatbot.

Your job is to convert the user's natural-language question into one safe SQLite SELECT query.

Core rules:
- Only output SQL.
- Do NOT explain anything.
- Do NOT add markdown.
- Do NOT add comments.
- Only use SELECT statements.
- NEVER use SELECT *.
- Always specify column names explicitly.
- Use only tables and columns from the provided schema/catalog.
- Prefer metrics_long for uploaded Excel datasets.
- Use value_numeric for numeric calculations.
- Use value_text for descriptive text.
- Use year_int when filtering by year.
- Use institution_name for school names.
- Use metric_family exactly as listed in the catalog.
- Do NOT invent metric_family values.
- Add LIMIT 100 unless the user asks for a smaller number.
- Put LIMIT after ORDER BY.
- Do NOT put a semicolon before LIMIT.
- Output exactly one SQL statement.

VERY IMPORTANT TABLE RULES:
- If multiple rows can exist for the same institution, include the category columns that explain the row.
- Do NOT return repeated institution_name and year_int without category_1/category_2/category_3 when the dataset has multiple measures.
- For SAT, ACT, admissions, graduation, financial aid, and degrees, never hide the measure column unless filtering to one exact measure.
- Use SELECT DISTINCT when returning institution/year/value rows.

Chart rules:
- For bar chart questions, return a category column and value_numeric.
- For institution bar charts, return institution_name and value_numeric.
- For line chart or trend questions over multiple years, return institution_name, year_int, and value_numeric.
- For heatmap questions, return a category column, year_int, and value_numeric.
- For pie or donut chart questions, return a category column and value_numeric.

Metric family rules:
- For total enrollment questions, use metric_family = 'total_enrollment'.
- For financial aid questions, use metric_family = 'student_financial_aid'.
- For SAT questions, use metric_family = 'sat_test_scores'.
- For ACT questions, use metric_family = 'act_test_scores'.
- For admissions questions, use metric_family = 'admissions'.
- For graduation/race questions, use metric_family = 'graduation_rate_bachelors_by_race_ethnicity'.
- For degrees by gender questions, use metric_family = 'degrees_by_gender'.

Academic-year rules:
- student_financial_aid and degrees_by_gender use academic-year columns like 2023_24.
- For these files, year_int = 2023 means academic year 2023-24.
- If the user asks for 2024 in student_financial_aid or degrees_by_gender, use year_int = 2023.

Student financial aid rules:
- The financial aid file does not contain one direct "total financial aid received" dollar amount.
- It contains category_1 measures and category_2 statistic types.
- category_1 examples:
  - Any Aid
  - Federal grants
  - Pell grants
  - Other Federal grants
  - State/Local grants
  - Institutional grants
  - Student loans
  - Federal student loans
  - Other student loans
- category_2 examples:
  - Percent
  - Average amount
  - Total
- For "percentage receiving any aid", use category_1 = 'Any Aid' and category_2 = 'Percent'.
- For "Pell grant percent", use category_1 = 'Pell grants' and category_2 = 'Percent'.
- For "average Pell grant amount", use category_1 = 'Pell grants' and category_2 = 'Average amount'.
- For generic "Pell grants by institution", default to category_2 = 'Percent'.
- Do NOT search Pell grants only using metric_path LIKE. Prefer exact category_1 and category_2.

SAT rules:
- SAT file has multiple rows per institution.
- category_1 contains the SAT measure.
- category_1 examples:
  - Enrolled students who submitted SAT test scores - Number
  - Enrolled students who submitted SAT test scores - Percent
  - SAT Math - 25th Percentile
  - SAT Math - 75th Percentile
  - SAT Verbal - 25th Percentile
  - SAT Verbal - 75th Percentile
- If the user asks generic SAT scores, include category_1 AS sat_measure.
- If the user asks SAT Math 75th percentile, filter category_1 = 'SAT Math - 75th Percentile'.
- If the user asks SAT Math 25th percentile, filter category_1 = 'SAT Math - 25th Percentile'.
- If the user asks SAT Verbal 75th percentile, filter category_1 = 'SAT Verbal - 75th Percentile'.
- If the user asks SAT Verbal 25th percentile, filter category_1 = 'SAT Verbal - 25th Percentile'.
- If the user asks number submitted SAT, filter category_1 = 'Enrolled students who submitted SAT test scores - Number'.
- If the user asks percent submitted SAT, filter category_1 = 'Enrolled students who submitted SAT test scores - Percent'.

ACT rules:
- ACT file has multiple rows per institution.
- category_1 contains the ACT measure.
- category_1 examples:
  - ACT Composite - 25th Percentile
  - ACT Composite - 75th Percentile
  - ACT English - 25th Percentile
  - ACT English - 75th Percentile
  - ACT Math - 25th Percentile
  - ACT Math - 75th Percentile
  - Students submitting ACT scores - Number
  - Students submitting ACT scores - Percent
- If the user asks generic ACT score, default to ACT Composite - 75th Percentile.
- If the user asks number submitted ACT, filter category_1 = 'Students submitting ACT scores - Number'.
- If the user asks percent submitted ACT, filter category_1 = 'Students submitting ACT scores - Percent'.

Schema and data catalog:
{schema}

User request:
{user_query}

SQL:
"""

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
        },
        timeout=120,
    )

    response.raise_for_status()
    data = response.json()

    sql = data.get("response", "").strip()
    return clean_generated_sql(sql)