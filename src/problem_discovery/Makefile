# Run from src/problem_discovery — no PYTHONPATH needed for targets using run_signal.py
VENV := .venv
PY := $(VENV)/bin/python
ST := $(VENV)/bin/streamlit

.PHONY: venv install setup db-up migrate streamlit signal-help

venv:
	python3 -m venv $(VENV)

install: venv
	$(VENV)/bin/pip install -U pip
	$(VENV)/bin/pip install -r requirements.txt

setup: install
	@test -f .env || cp .env.example .env
	@echo "Ready. Next: make db-up && make migrate && make streamlit"

# Start Postgres+pgvector (from repo root that contains docker-compose.yml)
db-up:
	@if [ -f ../../docker-compose.yml ]; then \
		docker compose -f ../../docker-compose.yml up -d; \
	elif [ -f ../../../docker-compose.yml ]; then \
		docker compose -f ../../../docker-compose.yml up -d; \
	else \
		echo "docker-compose.yml not found; start Postgres yourself and set DATABASE_URL in .env"; \
	fi

migrate: install
	$(PY) run_signal.py migrate

streamlit: install
	$(ST) run streamlit_app.py

signal-help: install
	$(PY) run_signal.py --help
