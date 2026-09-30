import re
from datetime import datetime, timedelta

import polars as pl

from src import db
from src.config import ACCOUNTS_CSV, DAILY_GLOB, DATA_DIR, DATETIME_FORMAT, MONTHLY_GLOB

EXCEL_EPOCH = datetime(1899, 12, 30)


def parse_datetime(raw):
    if raw is None:
        raise ValueError("empty datetime")
    text = str(raw).strip()
    if not text or text.lower() in ("null", "none", "nan"):
        raise ValueError("empty datetime")

    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%d-%m-%y %H:%M",
        "%d-%m-%y %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
    ):
        try:
            dt = datetime.strptime(text, fmt)
            weird = fmt != DATETIME_FORMAT
            return dt.strftime(DATETIME_FORMAT), weird
        except ValueError:
            pass

    if re.fullmatch(r"\d+(\.\d+)?", text):
        dt = EXCEL_EPOCH + timedelta(days=float(text))
        dt = dt.replace(microsecond=0)
        return dt.strftime(DATETIME_FORMAT), True

    raise ValueError(f"bad datetime: {text!r}")


def load_accounts(conn):
    df = pl.read_csv(ACCOUNTS_CSV)
    df = (
        df.rename({"account_id": "id"})
        .with_columns(
            pl.col("id").cast(pl.Int64),
            pl.col("name").cast(pl.Utf8).str.strip_chars(),
            pl.col("address").cast(pl.Utf8).str.strip_chars(),
        )
        .select(["id", "name", "address"])
    )
    rows = list(df.iter_rows())
    conn.executemany(
        "INSERT INTO accounts (id, name, address) VALUES (?, ?, ?)",
        rows,
    )
    conn.commit()
    print(f"accounts: {len(rows)}")
    return {int(r[0]) for r in rows}


def load_daily(conn, valid_accounts):
    files = sorted(DATA_DIR.glob(DAILY_GLOB))
    if not files:
        raise FileNotFoundError("no daily_*.csv files")

    frames = []
    for path in files:
        df = pl.read_csv(path, infer_schema_length=0)
        df = df.with_columns(pl.lit(path.name).alias("source_file"))
        frames.append(df.select(["account", "queue", "status", "changed_datetime", "source_file"]))

    daily = pl.concat(frames)
    prepared = []
    fixed = 0
    skipped = 0

    for account, queue, status, changed, source in daily.iter_rows():
        try:
            acc = int(str(account).strip())
        except (TypeError, ValueError):
            skipped += 1
            continue
        if acc not in valid_accounts:
            skipped += 1
            continue

        q = str(queue).strip().upper() if queue is not None else ""
        s = str(status).strip().upper() if status is not None else ""
        if not q or not s:
            skipped += 1
            continue

        try:
            dt, weird = parse_datetime(changed)
        except ValueError:
            skipped += 1
            continue
        if weird:
            fixed += 1

        prepared.append((acc, q, s, dt, source))

    conn.executemany(
        """
        INSERT INTO daily_status (account, queue, status, changed_datetime, source_file)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(account, changed_datetime) DO NOTHING
        """,
        prepared,
    )
    conn.commit()
    n = conn.execute("SELECT COUNT(*) AS n FROM daily_status").fetchone()["n"]
    print(f"daily: {n} rows ({fixed} datetimes fixed, {skipped} skipped)")
    return fixed


def load_monthly(conn, valid_accounts):
    files = sorted(DATA_DIR.glob(MONTHLY_GLOB))
    if not files:
        raise FileNotFoundError("no monthly_*.csv files")

    prepared = []
    skipped = 0

    for path in files:
        m = re.match(r"^monthly_(\d{6})\.csv$", path.name)
        if not m:
            raise ValueError(f"weird monthly filename: {path.name}")
        token = m.group(1)
        year_month = f"{token[0:4]}-{token[4:6]}"
        month_num = int(token[4:6])

        df = pl.read_csv(path, infer_schema_length=0)
        for account, queue, status, month in df.select(
            ["account", "queue", "status", "month"]
        ).iter_rows():
            try:
                acc = int(str(account).strip())
            except (TypeError, ValueError):
                skipped += 1
                continue
            if acc not in valid_accounts:
                skipped += 1
                continue

            q = str(queue).strip().upper() if queue is not None else ""
            s = str(status).strip().upper() if status is not None else ""
            if not q or not s:
                skipped += 1
                continue

            prepared.append((acc, q, s, year_month, month_num, path.name))

    conn.executemany(
        """
        INSERT INTO monthly_status
            (account, queue, status, year_month, month_num, source_file)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(account, year_month) DO NOTHING
        """,
        prepared,
    )
    conn.commit()
    n = conn.execute("SELECT COUNT(*) AS n FROM monthly_status").fetchone()["n"]
    print(f"monthly: {n} rows ({skipped} skipped)")


def load_all(conn):
    valid = load_accounts(conn)
    fixed = load_daily(conn, valid)
    load_monthly(conn, valid)
    db.create_indexes(conn)
    db.analyze(conn)

    counts = db.table_counts(conn)
    if counts["accounts"] == 0 or counts["daily_status"] == 0:
        raise ValueError(f"load looks empty: {counts}")
    fk = conn.execute(
        """
        SELECT COUNT(*) AS n FROM daily_status d
        LEFT JOIN accounts a ON a.id = d.account
        WHERE a.id IS NULL
        """
    ).fetchone()["n"]
    if fk:
        raise ValueError(f"fk problems in daily_status: {fk}")

    print(f"load done, fixed {fixed} odd datetimes")
