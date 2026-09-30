import argparse
import sys

from src import db
from src.config import PERFORMANCE_REPORT
from src.load import load_all
from src.performance import run_performance
from src.transform import process_all


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["load", "process", "perf", "all"])
    args = parser.parse_args()

    try:
        if args.command in ("load", "all"):
            conn = db.init_db(reset=True)
            load_all(conn)
            conn.close()

        if args.command in ("process", "all"):
            conn = db.connect()
            process_all(conn)
            conn.close()

        if args.command in ("perf", "all"):
            conn = db.connect()
            run_performance(conn, PERFORMANCE_REPORT)
            conn.close()
    except Exception as e:
        print("error:", e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
