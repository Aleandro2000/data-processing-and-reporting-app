import csv

from src import db
from src.config import (
    ACTIVITY_CSV,
    ACTIVITY_CUTOFF,
    AS_OF_DATETIME,
    AS_OF_YEAR_MONTH,
    COLLECTIONS_LEGAL_CSV,
    MONTHLY_FALLBACK_DATETIME,
    OUTPUT_DIR,
    TARGET_QUEUES,
)

COLS = ["account_id", "name", "address", "latest_update_datetime", "queue", "status"]

ACTIVITY_SQL = """
INSERT INTO account_activity_latest
    (account_id, name, address, latest_update_datetime, queue, status)
WITH filtered AS (
    SELECT account, queue, status, changed_datetime
    FROM daily_status
    WHERE changed_datetime >= ?
),
ranked AS (
    SELECT account, queue, status, changed_datetime,
           ROW_NUMBER() OVER (
               PARTITION BY account ORDER BY changed_datetime DESC
           ) AS rn
    FROM filtered
)
SELECT a.id, a.name, a.address, r.changed_datetime, r.queue, r.status
FROM ranked r
JOIN accounts a ON a.id = r.account
WHERE r.rn = 1
"""

ASOF_SQL = """
INSERT INTO collections_legal_asof
    (account_id, name, address, asof_queue, asof_status,
     latest_change_datetime, change_queue, change_status)
WITH ranked AS (
    SELECT account, queue, status, changed_datetime,
           ROW_NUMBER() OVER (
               PARTITION BY account ORDER BY changed_datetime DESC
           ) AS rn
    FROM daily_status
    WHERE changed_datetime < ?
),
from_daily AS (
    SELECT account, queue, status, changed_datetime
    FROM ranked
    WHERE rn = 1 AND queue IN (?, ?)
),
no_daily AS (
    SELECT a.id AS account
    FROM accounts a
    WHERE NOT EXISTS (
        SELECT 1 FROM daily_status d
        WHERE d.account = a.id AND d.changed_datetime < ?
    )
),
from_monthly AS (
    SELECT m.account, m.queue, m.status, ? AS changed_datetime
    FROM monthly_status m
    JOIN no_daily n ON n.account = m.account
    WHERE m.year_month = ? AND m.queue IN (?, ?)
),
combined AS (
    SELECT * FROM from_daily
    UNION ALL
    SELECT * FROM from_monthly
)
SELECT a.id, a.name, a.address,
       c.queue, c.status, c.changed_datetime, c.queue, c.status
FROM combined c
JOIN accounts a ON a.id = c.account
"""


def write_csv(path, rows):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        for row in rows:
            w.writerow({c: row[c] for c in COLS})


def build_activity(conn):
    conn.execute("DELETE FROM account_activity_latest")
    conn.execute(ACTIVITY_SQL, (ACTIVITY_CUTOFF,))
    conn.commit()
    rows = conn.execute(
        """
        SELECT account_id, name, address, latest_update_datetime, queue, status
        FROM account_activity_latest
        ORDER BY account_id
        """
    ).fetchall()
    write_csv(ACTIVITY_CSV, rows)
    return len(rows)


def build_collections_legal(conn):
    params = (
        AS_OF_DATETIME,
        TARGET_QUEUES[0],
        TARGET_QUEUES[1],
        AS_OF_DATETIME,
        MONTHLY_FALLBACK_DATETIME,
        AS_OF_YEAR_MONTH,
        TARGET_QUEUES[0],
        TARGET_QUEUES[1],
    )
    conn.execute("DELETE FROM collections_legal_asof")
    conn.execute(ASOF_SQL, params)
    conn.commit()
    rows = conn.execute(
        """
        SELECT account_id, name, address,
               latest_change_datetime AS latest_update_datetime,
               asof_queue AS queue,
               asof_status AS status
        FROM collections_legal_asof
        ORDER BY account_id
        """
    ).fetchall()
    write_csv(COLLECTIONS_LEGAL_CSV, rows)
    return len(rows)


def process_all(conn):
    counts = db.table_counts(conn)
    if counts["accounts"] == 0 or counts["daily_status"] == 0:
        raise ValueError("run load first")

    n_act = build_activity(conn)
    n_col = build_collections_legal(conn)

    monthly_n = conn.execute(
        """
        SELECT COUNT(*) AS n FROM monthly_status
        WHERE year_month = ? AND queue IN (?, ?)
        """,
        (AS_OF_YEAR_MONTH, TARGET_QUEUES[0], TARGET_QUEUES[1]),
    ).fetchone()["n"]
    print(f"activity rows: {n_act}")
    print(f"collections/legal rows: {n_col} (monthly Nov had {monthly_n})")
    if n_col != monthly_n:
        print("daily vs monthly don't match exactly - I kept daily")

    print(f"wrote {ACTIVITY_CSV}")
    print(f"wrote {COLLECTIONS_LEGAL_CSV}")
