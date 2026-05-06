from app.services.metadata_service import get_schema_context
from app.services.llm_service import generate_sql
from app.services.sql_service import validate_sql, execute_sql


def handle_chat(user_message: str):
    schema = get_schema_context()

    sql = generate_sql(user_message, schema)

    is_valid, error = validate_sql(sql)

    if not is_valid:
        return {
            "mode": "error",
            "reply": "Invalid SQL generated.",
            "sql": sql,
            "results": None,
            "evidence": [schema],
            "error": error,
        }

    try:
        results = execute_sql(sql)

        return {
            "mode": "sql_execution",
            "reply": f"Found {len(results)} result(s).",
            "sql": sql,
            "results": results,
            "evidence": [schema],
            "error": None,
        }

    except Exception as e:
        return {
            "mode": "execution_error",
            "reply": "Error executing SQL.",
            "sql": sql,
            "results": None,
            "evidence": [schema],
            "error": str(e),
        }


def handle_chat_with_steps(user_message: str):
    yield {
        "type": "step",
        "step": "Reading dataset catalog",
        "message": "Inspecting available tables, metrics, years, and column metadata...",
    }

    schema = get_schema_context()

    yield {
        "type": "step",
        "step": "Generating SQL",
        "message": "Using the dataset catalog to generate a safe SQL query...",
    }

    sql = generate_sql(user_message, schema)

    yield {
        "type": "step",
        "step": "Validating SQL",
        "message": "Checking that the query is read-only and allowed...",
        "sql": sql,
    }

    is_valid, error = validate_sql(sql)

    if not is_valid:
        yield {
            "type": "final",
            "data": {
                "mode": "error",
                "reply": "I generated SQL, but it did not pass validation.",
                "sql": sql,
                "results": None,
                "evidence": [schema],
                "error": error,
            },
        }
        return

    yield {
        "type": "step",
        "step": "Running query",
        "message": "Executing the validated SQL against the local database...",
        "sql": sql,
    }

    try:
        results = execute_sql(sql)

        yield {
            "type": "step",
            "step": "Formatting answer",
            "message": f"Formatting {len(results)} result(s) for display...",
            "sql": sql,
        }

        yield {
            "type": "final",
            "data": {
                "mode": "sql_execution",
                "reply": f"Found {len(results)} result(s).",
                "sql": sql,
                "results": results,
                "evidence": [schema],
                "error": None,
            },
        }

    except Exception as e:
        yield {
            "type": "final",
            "data": {
                "mode": "execution_error",
                "reply": "The SQL was valid, but execution failed.",
                "sql": sql,
                "results": None,
                "evidence": [schema],
                "error": str(e),
            },
        }