"""
backend.data_workbench.queries
───────────────────────
Safe SQL query execution over uploaded parquet files via DuckDB.

Security model:
  - Only SELECT statements are permitted.
  - Semicolons and multiple statements are rejected.
  - Result rows are capped at DATA_QUERY_ROW_LIMIT.
  - Query timeout is enforced via threading.
  - Only the dataset's own curated parquet can be queried (no arbitrary paths).

Public API:
  ask_dataset(dataset_id, question)      → natural-language → SQL → results
  run_sql(dataset_id, sql, curated_key)  → direct SQL execution
"""

from __future__ import annotations

import logging
import os
import re
import threading
from typing import Any

import pandas as pd

from backend.data_workbench.config import cfg
from backend.data_workbench.store import get_dataset

logger = logging.getLogger(__name__)

# ── SQL safety ────────────────────────────────────────────────────────

_DISALLOWED = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|REPLACE|COPY|GRANT|REVOKE|ATTACH|DETACH|INSTALL|LOAD|PRAGMA|SET|CALL|EXPORT)\b",
    re.IGNORECASE,
)

_DISALLOWED_TABLE_FUNCTIONS = re.compile(
    r"\b(read_parquet|parquet_scan|read_csv|read_csv_auto|csv_scan|read_json|read_json_auto|json_scan|read_text|glob|sqlite_scan|postgres_scan)\s*\(",
    re.IGNORECASE,
)

_DATASET_FROM = re.compile(r"\bFROM\s+(dataset|data|tbl|table|df)\b", re.IGNORECASE)


def _duckdb_quote(value: str) -> str:
    return value.replace("'", "''")


def _validate_sql(sql: str) -> str | None:
    """Return error string if SQL is unsafe, else None."""
    stripped = sql.strip()
    if not stripped.upper().startswith("SELECT"):
        return "Only SELECT statements are allowed."
    if ";" in stripped:
        return "Semicolons are not allowed (prevents multi-statement injection)."
    if _DISALLOWED.search(stripped):
        return "Detected disallowed SQL keyword."
    if _DISALLOWED_TABLE_FUNCTIONS.search(stripped):
        return "Direct file/table functions are not allowed. Query FROM dataset instead."
    if not _DATASET_FROM.search(stripped):
        return "Queries must read from the uploaded dataset using FROM dataset."
    return None


def _inject_limit(sql: str, row_limit: int) -> str:
    """Append or clamp LIMIT so callers cannot bypass the row cap."""
    sql = sql.rstrip("; \n\t")
    limit_match = re.search(r"\bLIMIT\s+(\d+)\b", sql, re.IGNORECASE)
    if limit_match:
        requested = int(limit_match.group(1))
        if requested > row_limit:
            sql = sql[:limit_match.start(1)] + str(row_limit) + sql[limit_match.end(1):]
        return sql
    sql += f" LIMIT {row_limit}"
    return sql


# ── Curated parquet resolver ──────────────────────────────────────────

def _parquet_ref(curated_key: str) -> str:
    """Return a DuckDB-readable reference string for the parquet file."""
    try:
        from backend.db.s3_store import is_enabled as s3_on, s3_uri
        if s3_on() and curated_key.startswith("datahub/"):
            return s3_uri(curated_key)
    except Exception:
        pass
    # Local file fallback
    from pathlib import Path
    if Path(curated_key).exists():
        return str(curated_key)
    return curated_key


# ── SQL runner ────────────────────────────────────────────────────────

def run_sql(
    sql: str,
    curated_key: str,
    row_limit: int | None = None,
) -> dict:
    """
    Execute a SELECT query over the curated parquet and return results.

    Returns:
        {
            "ok": bool,
            "error": str | None,
            "columns": [str, ...],
            "rows": [[...], ...],
            "row_count": int,
            "df": pd.DataFrame,
        }
    """
    if row_limit is None:
        row_limit = cfg().query_row_limit

    err = _validate_sql(sql)
    if err:
        return {"ok": False, "error": err, "columns": [], "rows": [], "row_count": 0, "df": pd.DataFrame()}

    sql = _inject_limit(sql, row_limit)
    ref = _parquet_ref(curated_key)

    # Replace bare table references "FROM dataset" or "FROM data" with parquet ref
    ref_sql = ref.replace("'", "''")
    sql_exec = _DATASET_FROM.sub(
        f"FROM read_parquet('{ref_sql}')",
        sql,
    )

    result: dict = {}
    exc_holder: list = []

    def _run():
        try:
            import duckdb
            conn = duckdb.connect()
            conn.execute("SET memory_limit='512MB';")
            conn.execute("SET threads=2;")
            # Configure S3 if needed
            try:
                conn.execute("LOAD httpfs;")
                region = os.getenv("AWS_REGION", "us-east-1")
                key_id = os.getenv("AWS_ACCESS_KEY_ID", "")
                secret = os.getenv("AWS_SECRET_ACCESS_KEY", "")
                conn.execute(f"SET s3_region='{_duckdb_quote(region)}';")
                if key_id:
                    conn.execute(f"SET s3_access_key_id='{_duckdb_quote(key_id)}';")
                    conn.execute(f"SET s3_secret_access_key='{_duckdb_quote(secret)}';")
            except Exception:
                pass
            df = conn.execute(sql_exec).df()
            result["df"] = df
        except Exception as e:
            exc_holder.append(str(e))

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=cfg().query_timeout_s)

    if t.is_alive():
        return {"ok": False, "error": "Query timed out.", "columns": [], "rows": [], "row_count": 0, "df": pd.DataFrame()}
    if exc_holder:
        return {"ok": False, "error": exc_holder[0], "columns": [], "rows": [], "row_count": 0, "df": pd.DataFrame()}

    df = result.get("df", pd.DataFrame())
    return {
        "ok":        True,
        "error":     None,
        "columns":   list(df.columns),
        "rows":      df.values.tolist(),
        "row_count": len(df),
        "df":        df,
        "sql_executed": sql_exec,
    }


# ── Natural-language → SQL ────────────────────────────────────────────

_NL2SQL_SYSTEM = """You are a DuckDB SQL expert.
Given a dataset schema and a question, produce a single SELECT statement.
Use FROM dataset as the table. The caller safely substitutes the uploaded
dataset parquet path.
Rules:
  - Output ONLY the SQL, no explanation, no markdown.
  - Use LIMIT 5000 or fewer.
  - Aggregate with GROUP BY when question implies grouping.
  - Use ILIKE for case-insensitive text filters.
  - Never use semicolons."""

_NL2SQL_USER = """\
Schema (column: type):
{schema}

Question: {question}

Write a SELECT query using FROM dataset (the caller will replace 'dataset' with the actual parquet path)."""


def ask_dataset(
    dataset_id: str,
    question: str,
    schema_hint: list[dict] | None = None,
) -> dict:
    """
    Translate a natural-language question to SQL and execute it.

    Returns:
        {
          "ok": bool, "error": str|None,
          "sql_generated": str, "sql_executed": str,
          "explanation": str,
          "columns": [...], "rows": [...], "row_count": int, "df": DataFrame
        }
    """
    dataset = get_dataset(dataset_id)
    if not dataset:
        return {"ok": False, "error": "Dataset not found."}

    curated_key = dataset.get("curated_key")
    if not curated_key:
        return {"ok": False, "error": "Dataset has no curated parquet yet."}

    # Build schema hint
    if schema_hint is None:
        from backend.data_workbench.store import list_columns
        cols = list_columns(dataset_id)
        schema_hint = [{"name": c["column_name"], "type": c["inferred_type"]} for c in cols]

    schema_str = "\n".join(f"  {c['name']}: {c['type']}" for c in (schema_hint or []))

    # Generate SQL
    sql_generated = ""
    explanation = ""

    if os.getenv("OPENAI_API_KEY"):
        try:
            from openai import OpenAI
            from backend.data_workbench.config import cfg as dcfg
            client = OpenAI()
            resp = client.chat.completions.create(
                model=dcfg().openai_model,
                messages=[
                    {"role": "system", "content": _NL2SQL_SYSTEM},
                    {"role": "user",   "content": _NL2SQL_USER.format(
                        schema=schema_str, question=question
                    )},
                ],
                temperature=0.1,
                max_tokens=400,
            )
            sql_generated = (resp.choices[0].message.content or "").strip()
            if sql_generated.startswith("```"):
                sql_generated = re.sub(r"```[a-z]*\n?", "", sql_generated).strip("`").strip()
        except Exception as e:
            logger.warning("NL→SQL generation failed: %s", e)
            return {"ok": False, "error": f"LLM error: {e}", "sql_generated": ""}
    else:
        # Fallback: basic heuristic SQL
        num_cols = [c["name"] for c in (schema_hint or []) if c.get("type") == "numeric"]
        if num_cols:
            sql_generated = f"SELECT * FROM dataset LIMIT 100"
        else:
            sql_generated = "SELECT * FROM dataset LIMIT 100"

    result = run_sql(sql_generated, curated_key)
    result["sql_generated"] = sql_generated

    # Ask LLM to explain the result
    if result["ok"] and os.getenv("OPENAI_API_KEY") and not result["df"].empty:
        try:
            from openai import OpenAI
            from backend.data_workbench.config import cfg as dcfg
            client = OpenAI()
            preview = result["df"].head(5).to_string(index=False)
            exp_resp = client.chat.completions.create(
                model=dcfg().openai_model,
                messages=[{
                    "role": "user",
                    "content": (
                        f"Question: {question}\n"
                        f"SQL ran: {sql_generated}\n"
                        f"Result preview:\n{preview}\n\n"
                        "Explain this result in 2-3 plain sentences for a non-technical user."
                    ),
                }],
                temperature=0.3,
                max_tokens=200,
            )
            explanation = exp_resp.choices[0].message.content or ""
        except Exception:
            pass

    result["explanation"] = explanation
    return result
