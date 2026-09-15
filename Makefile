.PHONY: install test test-hml test-prod test-credentials test-hml-credentials test-prod-credentials test-postgres report open-report serve-report up down clean

PYTHON ?= python

install:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt

test:
	TEST_ENV=hml CLIENT_SELECTION_SOURCE=database $(PYTHON) -m pytest

test-hml:
	TEST_ENV=hml CLIENT_SELECTION_SOURCE=database $(PYTHON) -m pytest

test-prod:
	TEST_ENV=prod CLIENT_SELECTION_SOURCE=database $(PYTHON) -m pytest

test-credentials:
	TEST_ENV=hml CLIENT_SELECTION_SOURCE=credentials $(PYTHON) -m pytest

test-hml-credentials:
	TEST_ENV=hml CLIENT_SELECTION_SOURCE=credentials $(PYTHON) -m pytest

test-prod-credentials:
	TEST_ENV=prod CLIENT_SELECTION_SOURCE=credentials $(PYTHON) -m pytest

test-postgres:
	$(PYTHON) -m pytest -m postgres

open-report:
	xdg-open reports/test-report.html

serve-report:
	$(PYTHON) -m http.server 8000 --directory reports

up:
	docker compose up -d postgres

down:
	docker compose down

clean:
	rm -rf .pytest_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
