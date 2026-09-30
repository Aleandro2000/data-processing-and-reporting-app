import sqlite3
from pathlib import Path

from src.config import CACHE_SIZE_KIB, DB_DIR, DB_PATH, OUTPUT_DIR

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    address TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS daily_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account INTEGER NOT NULL REFERENCES accounts(id),
    queue TEXT NOT NULL,
    status TEXT NOT NULL,
    changed_datetime TEXT NOT NULL,
    source_file TEXT NOT NULL,
    UNIQUE (account, changed_datetime)
);

CREATE TABLE IF NOT EXISTS monthly_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account INTEGER NOT NULL REFERENCES accounts(id),
    queue TEXT NOT NULL,
    status TEXT NOT NULL,
    year_month TEXT NOT NULL,
    month_num INTEGER NOT NULL,
    source_file TEXT NOT NULL,
    UNIQUE (account, year_month)
);

CREATE TABLE IF NOT EXISTS account_activity_latest (
    account_id INTEGER PRIMARY KEY REFERENCES accounts(id),
    name TEXT NOT NULL,
    address TEXT NOT NULL,
    latest_update_datetime TEXT NOT NULL,
    queue TEXT NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS collections_legal_asof (
    account_id INTEGER PRIMARY KEY REFERENCES accounts(id),
    name TEXT NOT NULL,
    address TEXT NOT NULL,
    asof_queue TEXT NOT NULL,
    asof_status TEXT NOT NULL,
    latest_change_datetime TEXT NOT NULL,
    change_queue TEXT NOT NULL,
    change_status TEXT NOT NULL
);
"""

INDEXES = """
CREATE INDEX IF NOT EXISTS idx_daily_account_dt ON daily_status(account, changed_datetime);
CREATE INDEX IF NOT EXISTS idx_daily_dt ON daily_status(changed_datetime);
CREATE INDEX IF NOT EXISTS idx_daily_queue ON daily_status(queue);
CREATE INDEX IF NOT EXISTS idx_monthly_ym ON monthly_status(account, year_month);
"""


def connect(path=None):
    path = path or DB_PATH
    DB_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(f"PRAGMA cache_size = {CACHE_SIZE_KIB}")
    return conn


def init_db(reset=True):
    if reset:
        for suffix in ("", "-wal", "-shm"):
            p = Path(str(DB_PATH) + suffix) if suffix else DB_PATH
            if p.exists():
                p.unlink()
    conn = connect()
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def create_indexes(conn):
    conn.executescript(INDEXES)
    conn.commit()


def drop_indexes(conn):
    for name in (
        "idx_daily_account_dt",
        "idx_daily_dt",
        "idx_daily_queue",
        "idx_monthly_ym",
    ):
        conn.execute(f"DROP INDEX IF EXISTS {name}")
    conn.commit()


def analyze(conn):
    conn.execute("ANALYZE")
    conn.commit()


def table_counts(conn):
    out = {}
    for t in (
        "accounts",
        "daily_status",
        "monthly_status",
        "account_activity_latest",
        "collections_legal_asof",
    ):
        out[t] = conn.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()["n"]
    return out
