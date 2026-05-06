import re
from app.database import get_connection
from app.config import ALLOWED_SQL_TABLES


def clean_sql_for_execution(sql: str) -> str:
    sql = sql.strip()

    sql = sql.replace("```sql", "").replace("```", "").strip()

    # Fix bad model output like: ORDER BY year_int; LIMIT 100;
    sql = re.sub(r";\s*LIMIT", " LIMIT", sql, flags=re.IGNORECASE)

    # Remove all trailing semicolons
    sql = sql.rstrip(";").strip()

    return sql


def validate_sql(sql: str):
    cleaned = clean_sql_for_execution(sql)
    sql_upper = cleaned.upper()

    if not sql_upper.startswith("SELECT"):
        return False, "Only SELECT queries are allowed."

    forbidden = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE", "REPLACE"]
    for word in forbidden:
        if re.search(rf"\b{word}\b", sql_upper):
            return False, f"Forbidden keyword detected: {word}"

    # Block multiple statements
    if ";" in cleaned:
        return False, "Multiple SQL statements are not allowed."

    allowed = any(table.lower() in cleaned.lower() for table in ALLOWED_SQL_TABLES)
    if not allowed:
        return False, "Query uses unauthorized table."

    return True, None


def execute_sql(sql: str):
    cleaned = clean_sql_for_execution(sql)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(cleaned)
    rows = cursor.fetchall()

    conn.close()

    return [dict(row) for row in rows]