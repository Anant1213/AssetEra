"""
backend.data_workbench.config
──────────────────────
Configuration and feature flags for the Data Workbench.
All values have safe defaults so the module loads without any env vars set.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DataHubConfig:
    # Storage
    bucket: str = ""
    aws_region: str = "us-east-1"
    raw_prefix: str = "datahub"

    # Processing limits
    max_sync_mb: int = 200          # files > this size skip inline processing
    profile_sample_rows: int = 50_000
    query_row_limit: int = 5_000
    query_timeout_s: int = 20

    # LLM
    openai_model: str = "gpt-4o-mini"
    llm_max_tokens: int = 1_000
    llm_enabled: bool = True

    # SQLite metadata DB path (local file — no external server needed)
    sqlite_path: str = str(Path.home() / ".assetera" / "datahub.db")

    # Upload limits
    max_upload_bytes: int = 200 * 1024 * 1024   # 200 MB

    # Supported structured extensions
    structured_extensions: tuple = (".csv", ".xlsx", ".xls", ".json", ".parquet")


def get_config() -> DataHubConfig:
    """Build config from environment variables with sensible defaults."""
    return DataHubConfig(
        bucket=os.getenv("DATA_BUCKET", ""),
        aws_region=os.getenv("AWS_REGION", "us-east-1"),
        max_sync_mb=int(os.getenv("DATA_MAX_SYNC_MB", "200")),
        profile_sample_rows=int(os.getenv("DATA_PROFILE_SAMPLE_ROWS", "50000")),
        query_row_limit=int(os.getenv("DATA_QUERY_ROW_LIMIT", "5000")),
        query_timeout_s=int(os.getenv("DATA_QUERY_TIMEOUT_S", "20")),
        openai_model=os.getenv("DATAHUB_LLM_MODEL", "gpt-4o-mini"),
        llm_enabled=bool(os.getenv("OPENAI_API_KEY")),
        sqlite_path=os.getenv(
            "DATAHUB_DB_PATH",
            str(Path.home() / ".assetera" / "datahub.db"),
        ),
        max_upload_bytes=int(os.getenv("DATA_MAX_UPLOAD_BYTES", str(200 * 1024 * 1024))),
    )


# Module-level singleton
_cfg: DataHubConfig | None = None


def cfg() -> DataHubConfig:
    global _cfg
    if _cfg is None:
        _cfg = get_config()
    return _cfg
