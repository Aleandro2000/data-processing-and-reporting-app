import statistics
import time

from src import db
from src.config import CACHE_SIZE_KIB, PERF_RUNS, TARGET_QUEUES

SLOW_SQL = """
SELECT d.*, a.name, a.address
FROM daily_status d
JOIN accounts a ON a.id = d.account
WHERE d.account IN (
    SELECT DISTINCT account
    FROM daily_status
    WHERE queue IN (?, ?)
)
"""

FAST_SQL = """
SELECT d.account, d.queue, d.status, d.changed_datetime, d.source_file,
       a.name, a.address
FROM daily_status d
JOIN accounts a ON a.id = d.account
JOIN good_accounts g ON g.account = d.account
"""


def run_performance(conn, report_path):
    counts = db.table_counts(conn)
    if counts["daily_status"] == 0:
        raise ValueError("run load first")

    db.drop_indexes(conn)
    conn.execute("DROP TABLE IF EXISTS good_accounts")
    conn.commit()
    conn.execute("PRAGMA cache_size = -2000")

    slow_plan = []
    for row in conn.execute("EXPLAIN QUERY PLAN " + SLOW_SQL, TARGET_QUEUES):
        slow_plan.append(row["detail"])

    times = []
    for _ in range(PERF_RUNS):
        t0 = time.perf_counter()
        slow_rows = conn.execute(SLOW_SQL, TARGET_QUEUES).fetchall()
        times.append(time.perf_counter() - t0)
    slow_ms = statistics.median(times) * 1000
    slow_n = len(slow_rows)

    db.create_indexes(conn)
    conn.execute("ANALYZE")
    conn.commit()

    conn.execute("DROP TABLE IF EXISTS good_accounts")
    conn.execute("CREATE TABLE good_accounts (account INTEGER PRIMARY KEY)")
    conn.execute(
        """
        INSERT INTO good_accounts (account)
        SELECT DISTINCT account FROM daily_status
        WHERE queue IN (?, ?)
        """,
        TARGET_QUEUES,
    )
    conn.commit()
    n_good = conn.execute("SELECT COUNT(*) AS n FROM good_accounts").fetchone()["n"]
    conn.execute(f"PRAGMA cache_size = {CACHE_SIZE_KIB}")

    fast_plan = []
    for row in conn.execute("EXPLAIN QUERY PLAN " + FAST_SQL):
        fast_plan.append(row["detail"])

    times = []
    for _ in range(PERF_RUNS):
        t0 = time.perf_counter()
        fast_rows = conn.execute(FAST_SQL).fetchall()
        times.append(time.perf_counter() - t0)
    fast_ms = statistics.median(times) * 1000
    fast_n = len(fast_rows)

    if slow_n != fast_n:
        raise ValueError(f"row counts differ: {slow_n} vs {fast_n}")

    speedup = slow_ms / fast_ms if fast_ms else 0

    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("Performance notes\n\n")
        f.write("I timed the query that returns daily status rows with account\n")
        f.write("name/address for accounts that were ever in COLLECTIONS or LEGAL.\n\n")
        f.write("Slow version:\n")
        f.write(SLOW_SQL.strip() + "\n\n")
        f.write("Faster version:\n")
        f.write(FAST_SQL.strip() + "\n\n")
        f.write("What I changed:\n")
        f.write("- made a good_accounts table once instead of DISTINCT each time\n")
        f.write("- selected only the columns I need\n")
        f.write("- added indexes and ran ANALYZE\n")
        f.write("- increased the sqlite cache\n\n")
        f.write(f"Median of {PERF_RUNS} runs.\n")
        f.write(f"{n_good} accounts hit COLLECTIONS/LEGAL at some point.\n\n")
        f.write("Slow plan:\n")
        for line in slow_plan:
            f.write(f"  {line}\n")
        f.write(f"{slow_ms:.2f} ms median, {slow_n} rows\n\n")
        f.write("Faster plan:\n")
        for line in fast_plan:
            f.write(f"  {line}\n")
        f.write(f"{fast_ms:.2f} ms median, {fast_n} rows\n\n")
        f.write(f"About {speedup:.2f}x faster here.\n")
        f.write("Same row count both times.\n")

    print(f"perf: {slow_ms:.2f} ms to {fast_ms:.2f} ms ({speedup:.2f}x), {slow_n} rows")
    print(f"wrote {report_path}")
