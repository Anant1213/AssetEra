"""
backend.data_workbench.store
─────────────────────
SQLite-based metadata store for the Data Workbench.

All tables live in a local SQLite file (~/.assetera/datahub.db by default).
This means no external database is needed — the Data Workbench works
out-of-the-box with just S3 credentials.

Schema:
  projects   — named workspaces grouping related datasets
  datasets   — one row per uploaded file or multi-file collection
  uploads    — individual file upload records
  columns    — per-column stats saved after profiling
  profiles   — full profile + quality JSON + LLM narrative
  views      — auto-generated chart specs
  jobs       — processing job queue (inline for small files)
"""

from __future__ import annotations

import json
import logging
import shutil
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.data_workbench.config import cfg

logger = logging.getLogger(__name__)

_local = threading.local()

# ── DDL ────────────────────────────────────────────────────────────────

_DDL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS projects (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS datasets (
    id             TEXT PRIMARY KEY,
    project_id     TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name           TEXT NOT NULL,
    source_type    TEXT NOT NULL DEFAULT 'structured',
    status         TEXT NOT NULL DEFAULT 'uploaded',
    row_count      INTEGER,
    column_count   INTEGER,
    file_count     INTEGER NOT NULL DEFAULT 0,
    curated_key    TEXT,
    context_hint   TEXT,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS uploads (
    id             TEXT PRIMARY KEY,
    dataset_id     TEXT NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    filename       TEXT NOT NULL,
    size_bytes     INTEGER NOT NULL,
    sha256         TEXT NOT NULL,
    s3_raw_key     TEXT,
    local_path     TEXT,
    upload_status  TEXT NOT NULL DEFAULT 'received',
    created_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS columns (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_id     TEXT NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    column_name    TEXT NOT NULL,
    inferred_type  TEXT NOT NULL DEFAULT 'mixed',
    null_pct       REAL,
    distinct_count INTEGER,
    min_value      TEXT,
    max_value      TEXT,
    mean_value     REAL,
    std_value      REAL,
    top_values     TEXT,
    semantic_label TEXT,
    created_at     TEXT NOT NULL,
    UNIQUE(dataset_id, column_name)
);

CREATE TABLE IF NOT EXISTS profiles (
    id               TEXT PRIMARY KEY,
    dataset_id       TEXT NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    profile_version  INTEGER NOT NULL DEFAULT 1,
    profile_json     TEXT NOT NULL,
    quality_json     TEXT NOT NULL,
    narrative        TEXT,
    llm_hints        TEXT,
    generated_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS views (
    id          TEXT PRIMARY KEY,
    dataset_id  TEXT NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    view_name   TEXT NOT NULL,
    view_level  TEXT NOT NULL DEFAULT 'basic',
    chart_type  TEXT NOT NULL,
    priority    INTEGER NOT NULL DEFAULT 100,
    spec_json   TEXT NOT NULL,
    explanation TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
    id           TEXT PRIMARY KEY,
    dataset_id   TEXT NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    job_type     TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'queued',
    attempts     INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    payload_json TEXT NOT NULL DEFAULT '{}',
    result_json  TEXT,
    error_text   TEXT,
    created_at   TEXT NOT NULL,
    started_at   TEXT,
    finished_at  TEXT
);

CREATE INDEX IF NOT EXISTS idx_datasets_project   ON datasets(project_id);
CREATE INDEX IF NOT EXISTS idx_uploads_dataset    ON uploads(dataset_id);
CREATE INDEX IF NOT EXISTS idx_columns_dataset    ON columns(dataset_id);
CREATE INDEX IF NOT EXISTS idx_views_dataset      ON views(dataset_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status        ON jobs(status, created_at);
"""


# ── Connection ────────────────────────────────────────────────────────

def _conn() -> sqlite3.Connection:
    if getattr(_local, "conn", None) is None:
        db_path = Path(cfg().sqlite_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.executescript(_DDL)
        conn.commit()
        _local.conn = conn
    return _local.conn


def _now() -> str:
    return datetime.utcnow().isoformat()


def _uid() -> str:
    return str(uuid.uuid4())


# ── Projects ──────────────────────────────────────────────────────────

def create_project(name: str, description: str = "") -> dict:
    row = {"id": _uid(), "name": name, "description": description,
           "created_at": _now(), "updated_at": _now()}
    _conn().execute(
        "INSERT INTO projects VALUES (:id,:name,:description,:created_at,:updated_at)", row
    )
    _conn().commit()
    return row


def list_projects() -> list[dict]:
    rows = _conn().execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]


def get_project(project_id: str) -> dict | None:
    row = _conn().execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    return dict(row) if row else None


def delete_project(project_id: str) -> None:
    _conn().execute("DELETE FROM projects WHERE id=?", (project_id,))
    _conn().commit()


# ── Datasets ──────────────────────────────────────────────────────────

def create_dataset(
    project_id: str, name: str,
    source_type: str = "structured",
    context_hint: str = "",
) -> dict:
    row = {
        "id": _uid(), "project_id": project_id, "name": name,
        "source_type": source_type, "status": "uploaded",
        "row_count": None, "column_count": None, "file_count": 0,
        "curated_key": None, "context_hint": context_hint,
        "created_at": _now(), "updated_at": _now(),
    }
    _conn().execute(
        "INSERT INTO datasets VALUES "
        "(:id,:project_id,:name,:source_type,:status,:row_count,:column_count,"
        ":file_count,:curated_key,:context_hint,:created_at,:updated_at)",
        row,
    )
    _conn().commit()
    return row


def list_datasets(project_id: str) -> list[dict]:
    rows = _conn().execute(
        "SELECT * FROM datasets WHERE project_id=? ORDER BY created_at DESC",
        (project_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_dataset(dataset_id: str) -> dict | None:
    row = _conn().execute("SELECT * FROM datasets WHERE id=?", (dataset_id,)).fetchone()
    return dict(row) if row else None


def update_dataset(dataset_id: str, **kwargs) -> None:
    kwargs["updated_at"] = _now()
    sets = ", ".join(f"{k}=:{k}" for k in kwargs)
    kwargs["id"] = dataset_id
    _conn().execute(f"UPDATE datasets SET {sets} WHERE id=:id", kwargs)
    _conn().commit()


def delete_dataset(dataset_id: str) -> None:
    row = _conn().execute("SELECT curated_key FROM datasets WHERE id=?", (dataset_id,)).fetchone()
    curated_key = row["curated_key"] if row else ""

    if curated_key:
        try:
            if curated_key.startswith(f"datahub/{dataset_id}/"):
                from backend.db.s3_store import is_enabled as s3_on, list_keys, delete_key
                if s3_on():
                    for key in list_keys(f"datahub/{dataset_id}/"):
                        delete_key(key)
            else:
                path = Path(curated_key)
                if path.exists() and path.parent.name == dataset_id:
                    shutil.rmtree(path.parent, ignore_errors=True)
        except Exception as exc:
            logger.warning("Could not delete curated data for dataset %s: %s", dataset_id, exc)

    _conn().execute("DELETE FROM datasets WHERE id=?", (dataset_id,))
    _conn().commit()


# ── Uploads ───────────────────────────────────────────────────────────

def create_upload(
    dataset_id: str, filename: str, size_bytes: int,
    sha256: str, s3_raw_key: str = "", local_path: str = "",
) -> dict:
    row = {
        "id": _uid(), "dataset_id": dataset_id, "filename": filename,
        "size_bytes": size_bytes, "sha256": sha256,
        "s3_raw_key": s3_raw_key, "local_path": local_path,
        "upload_status": "stored", "created_at": _now(),
    }
    _conn().execute(
        "INSERT INTO uploads VALUES "
        "(:id,:dataset_id,:filename,:size_bytes,:sha256,:s3_raw_key,:local_path,:upload_status,:created_at)",
        row,
    )
    _conn().commit()
    return row


def list_uploads(dataset_id: str) -> list[dict]:
    rows = _conn().execute(
        "SELECT * FROM uploads WHERE dataset_id=? ORDER BY created_at", (dataset_id,)
    ).fetchall()
    return [dict(r) for r in rows]


# ── Columns ───────────────────────────────────────────────────────────

def save_columns(dataset_id: str, col_list: list[dict]) -> None:
    """Upsert column stats. col_list items must have at minimum 'column_name' and 'inferred_type'."""
    now = _now()
    _conn().execute("DELETE FROM columns WHERE dataset_id=?", (dataset_id,))
    for col in col_list:
        _conn().execute(
            "INSERT INTO columns "
            "(dataset_id,column_name,inferred_type,null_pct,distinct_count,"
            "min_value,max_value,mean_value,std_value,top_values,semantic_label,created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                dataset_id,
                col.get("column_name"),
                col.get("inferred_type", "mixed"),
                col.get("null_pct"),
                col.get("distinct_count"),
                str(col.get("min_value", "")) if col.get("min_value") is not None else None,
                str(col.get("max_value", "")) if col.get("max_value") is not None else None,
                col.get("mean_value"),
                col.get("std_value"),
                json.dumps(col.get("top_values")) if col.get("top_values") else None,
                col.get("semantic_label"),
                now,
            ),
        )
    _conn().commit()


def list_columns(dataset_id: str) -> list[dict]:
    rows = _conn().execute(
        "SELECT * FROM columns WHERE dataset_id=? ORDER BY id", (dataset_id,)
    ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        if d.get("top_values"):
            try:
                d["top_values"] = json.loads(d["top_values"])
            except Exception:
                pass
        result.append(d)
    return result


# ── Profiles ──────────────────────────────────────────────────────────

def save_profile(
    dataset_id: str,
    profile_json: dict,
    quality_json: dict,
    narrative: str = "",
    llm_hints: str = "",
) -> str:
    pid = _uid()
    _conn().execute("DELETE FROM profiles WHERE dataset_id=?", (dataset_id,))
    _conn().execute(
        "INSERT INTO profiles VALUES (?,?,?,?,?,?,?,?)",
        (pid, dataset_id, 1, json.dumps(profile_json), json.dumps(quality_json),
         narrative, llm_hints, _now()),
    )
    _conn().commit()
    return pid


def get_profile(dataset_id: str) -> dict | None:
    row = _conn().execute(
        "SELECT * FROM profiles WHERE dataset_id=? ORDER BY generated_at DESC LIMIT 1",
        (dataset_id,),
    ).fetchone()
    if not row:
        return None
    d = dict(row)
    try:
        d["profile_json"] = json.loads(d["profile_json"])
        d["quality_json"] = json.loads(d["quality_json"])
    except Exception:
        pass
    return d


# ── Views ─────────────────────────────────────────────────────────────

def save_views(dataset_id: str, specs: list[dict]) -> None:
    _conn().execute("DELETE FROM views WHERE dataset_id=?", (dataset_id,))
    now = _now()
    for i, spec in enumerate(specs):
        _conn().execute(
            "INSERT INTO views VALUES (?,?,?,?,?,?,?,?,?)",
            (
                _uid(), dataset_id,
                spec.get("title", f"View {i+1}"),
                spec.get("level", "basic"),
                spec.get("chart_type", "bar"),
                spec.get("priority", 100),
                json.dumps(spec),
                spec.get("explanation", ""),
                now,
            ),
        )
    _conn().commit()


def list_views(dataset_id: str) -> list[dict]:
    rows = _conn().execute(
        "SELECT * FROM views WHERE dataset_id=? ORDER BY priority, created_at",
        (dataset_id,),
    ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d["spec"] = json.loads(d["spec_json"])
        except Exception:
            d["spec"] = {}
        result.append(d)
    return result


# ── Jobs ──────────────────────────────────────────────────────────────

def create_job(dataset_id: str, job_type: str, payload: dict | None = None) -> str:
    jid = _uid()
    _conn().execute(
        "INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (jid, dataset_id, job_type, "queued", 0, 3,
         json.dumps(payload or {}), None, None, _now(), None, None),
    )
    _conn().commit()
    return jid


def update_job(job_id: str, **kwargs) -> None:
    if "result_json" in kwargs and isinstance(kwargs["result_json"], dict):
        kwargs["result_json"] = json.dumps(kwargs["result_json"])
    sets = ", ".join(f"{k}=?" for k in kwargs)
    _conn().execute(f"UPDATE jobs SET {sets} WHERE id=?", (*kwargs.values(), job_id))
    _conn().commit()


def get_job(job_id: str) -> dict | None:
    row = _conn().execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    try:
        d["payload_json"] = json.loads(d["payload_json"] or "{}")
    except Exception:
        pass
    return d
