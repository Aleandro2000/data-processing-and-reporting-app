PYTHON ?= python3
VENV ?= .venv
PIP := $(VENV)/bin/pip
PY := $(VENV)/bin/python

.PHONY: setup run clean load process perf

setup:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install -r requirements.txt

load:
	$(PY) main.py load

process:
	$(PY) main.py process

perf:
	$(PY) main.py perf

run:
	$(PY) main.py all

clean:
	rm -f db/reporting.db db/reporting.db-wal db/reporting.db-shm
	rm -f outputs/*.csv outputs/*.txt
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
