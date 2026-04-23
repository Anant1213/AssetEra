"""
Portfolio Store — Postgres-backed CRUD for custom user portfolios.
Falls back gracefully to no-op if Postgres is not configured.
"""

from __future__ import annotations
import json
import logging
from datetime import datetime
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


def _get_conn():
    """Get Postgres connection. Returns None if not configured."""
    try:
        from backend.db.postgres_store import get_connection
        return get_connection()
    except Exception as e:
        logger.warning("Postgres not available for portfolio store: %s", e)
        return None


def is_enabled() -> bool:
    """Check if portfolio store is available."""
    try:
        from backend.db.postgres_store import is_enabled as pg_enabled
        return pg_enabled()
    except Exception:
        return False


def _init_table():
    """Create portfolios table if it doesn't exist."""
    conn = _get_conn()
    if conn is None:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS custom_portfolios (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    holdings JSONB NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                );
            """)
            conn.commit()
        logger.info("custom_portfolios table initialized")
    except Exception as e:
        logger.warning("Failed to init portfolio table: %s", e)
    finally:
        conn.close()


def create_portfolio(
    name: str,
    description: str = "",
    holdings: list[dict] = None,
) -> Optional[int]:
    """
    Create a new portfolio.

    Args:
        name: Portfolio name
        description: Optional description
        holdings: List of {"ticker": str, "weight": float}

    Returns:
        Portfolio ID if successful, None otherwise
    """
    if holdings is None:
        holdings = []

    conn = _get_conn()
    if conn is None:
        logger.warning("Portfolio store not available")
        return None

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO custom_portfolios (name, description, holdings)
                VALUES (%s, %s, %s)
                RETURNING id;
                """,
                (name, description, json.dumps(holdings)),
            )
            portfolio_id = cur.fetchone()[0]
            conn.commit()
            logger.info("Created portfolio %d: %s", portfolio_id, name)
            return portfolio_id
    except Exception as e:
        logger.warning("Failed to create portfolio: %s", e)
        return None
    finally:
        conn.close()


def list_portfolios() -> list[dict]:
    """List all custom portfolios."""
    conn = _get_conn()
    if conn is None:
        return []

    try:
        df = pd.read_sql(
            "SELECT id, name, description, holdings, created_at FROM custom_portfolios ORDER BY created_at DESC;",
            conn,
        )
        if df.empty:
            return []
        return df.to_dict("records")
    except Exception as e:
        logger.warning("Failed to list portfolios: %s", e)
        return []
    finally:
        conn.close()


def get_portfolio(portfolio_id: int) -> Optional[dict]:
    """Get a portfolio by ID."""
    conn = _get_conn()
    if conn is None:
        return None

    try:
        df = pd.read_sql(
            "SELECT id, name, description, holdings, created_at FROM custom_portfolios WHERE id=%s;",
            conn,
            params=(portfolio_id,),
        )
        if df.empty:
            return None
        row = df.iloc[0].to_dict()
        # Parse holdings JSON
        if isinstance(row["holdings"], str):
            row["holdings"] = json.loads(row["holdings"])
        return row
    except Exception as e:
        logger.warning("Failed to get portfolio %d: %s", portfolio_id, e)
        return None
    finally:
        conn.close()


def update_portfolio(
    portfolio_id: int,
    name: str = None,
    description: str = None,
    holdings: list[dict] = None,
) -> bool:
    """Update a portfolio."""
    conn = _get_conn()
    if conn is None:
        return False

    try:
        updates = []
        params = []
        if name is not None:
            updates.append("name=%s")
            params.append(name)
        if description is not None:
            updates.append("description=%s")
            params.append(description)
        if holdings is not None:
            updates.append("holdings=%s")
            params.append(json.dumps(holdings))

        if not updates:
            return True

        updates.append("updated_at=NOW()")
        params.append(portfolio_id)

        query = f"UPDATE custom_portfolios SET {', '.join(updates)} WHERE id=%s;"
        with conn.cursor() as cur:
            cur.execute(query, params)
            conn.commit()
        logger.info("Updated portfolio %d", portfolio_id)
        return True
    except Exception as e:
        logger.warning("Failed to update portfolio %d: %s", portfolio_id, e)
        return False
    finally:
        conn.close()


def delete_portfolio(portfolio_id: int) -> bool:
    """Delete a portfolio."""
    conn = _get_conn()
    if conn is None:
        return False

    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM custom_portfolios WHERE id=%s;", (portfolio_id,))
            conn.commit()
        logger.info("Deleted portfolio %d", portfolio_id)
        return True
    except Exception as e:
        logger.warning("Failed to delete portfolio %d: %s", portfolio_id, e)
        return False
    finally:
        conn.close()


# Initialize table on module load
if is_enabled():
    _init_table()
