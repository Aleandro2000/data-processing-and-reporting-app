from pathlib import Path
from datetime import datetime, timedelta

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_DIR = ROOT / "db"
DB_PATH = DB_DIR / "reporting.db"
OUTPUT_DIR = ROOT / "outputs"

ACCOUNTS_CSV = DATA_DIR / "accounts.csv"
DAILY_GLOB = "daily_*.csv"
MONTHLY_GLOB = "monthly_*.csv"

ACTIVITY_CUTOFF = "2025-01-01 00:00:00"
AS_OF_DATETIME = "2025-11-27 00:00:00"
TARGET_QUEUES = ("COLLECTIONS", "LEGAL")

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
_as_of = datetime.strptime(AS_OF_DATETIME, DATETIME_FORMAT)
AS_OF_YEAR_MONTH = _as_of.strftime("%Y-%m")
MONTHLY_FALLBACK_DATETIME = (_as_of - timedelta(seconds=1)).strftime(DATETIME_FORMAT)

ACTIVITY_CSV = OUTPUT_DIR / "accounts_activity_since_2025.csv"
COLLECTIONS_LEGAL_CSV = OUTPUT_DIR / "latest_change_collections_legal.csv"
PERFORMANCE_REPORT = OUTPUT_DIR / "PERFORMANCE_REPORT.txt"

PERF_RUNS = 10
CACHE_SIZE_KIB = -20000
