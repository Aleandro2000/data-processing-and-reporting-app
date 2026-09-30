# Data Processing and Reporting

My solution for the assessment. Loads CSVs into SQLite, writes the two report
CSVs, and times one query before/after some tweaks.

## Setup

```bash
make setup
```

Uses Polars to read the CSVs.

## Run

```bash
make run
```

Or step by step:

```bash
.venv/bin/python main.py load
.venv/bin/python main.py process
.venv/bin/python main.py perf
```

## Outputs

- outputs/accounts_activity_since_2025.csv - activity on/after 2025-01-01
- outputs/latest_change_collections_legal.csv - COLLECTIONS/LEGAL as of 2025-11-27
- outputs/PERFORMANCE_REPORT.txt - timing notes (required TXT)
- LOGICAL_STEPS.txt - short logical notes (required TXT)
- SOLUTION_NOTES.pdf - full write-up (load, reports, performance, why/how). Enough on its own if you only read one doc.

## Notes

Source files are under data/. After load, the rest is SQLite.
Odd timestamps (short EU dates / Excel serials) get fixed on load.
db/reporting.db is local and gitignored.
