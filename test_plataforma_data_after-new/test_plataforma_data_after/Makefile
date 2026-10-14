.PHONY: install test test-hml test-prod test-credentials test-hml-credentials test-prod-credentials test-client-data test-client-data-credentials test-after-pipeline test-postgres open-report serve-report up down clean

PYTHON ?= python3.14

install:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt


test-hml-credentials:
	TEST_ENV=hml CLIENT_SELECTION_SOURCE=credentials $(PYTHON) -m pytest tests

test-prod-credentials:
	TEST_ENV=prod CLIENT_SELECTION_SOURCE=credentials $(PYTHON) -m pytest

test-prod-database:
	TEST_ENV=hmlprod CLIENT_SELECTION_SOURCE=database $(PYTHON) -m pytest

test-hml-database:
	TEST_ENV=hml CLIENT_SELECTION_SOURCE=database $(PYTHON) -m pytest

up:
	docker compose up -d postgres

down:
	docker compose down

clean:
	rm -rf .pytest_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +