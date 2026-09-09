.PHONY: install test test-hml test-prod test-credentials test-hml-credentials test-prod-credentials test-postgres report open-report serve-report up down clean

install:
	python3.14 -m pip install --upgrade pip
	pip install -r requirements.txt

test:
	TEST_ENV=hml CLIENT_SELECTION_SOURCE=database pytest

test-hml:
	TEST_ENV=hml CLIENT_SELECTION_SOURCE=database pytest

test-prod:
	TEST_ENV=prod CLIENT_SELECTION_SOURCE=database pytest

test-credentials:
	TEST_ENV=hml CLIENT_SELECTION_SOURCE=credentials pytest

test-hml-credentials:
	TEST_ENV=hml CLIENT_SELECTION_SOURCE=credentials pytest

test-prod-credentials:
	TEST_ENV=prod CLIENT_SELECTION_SOURCE=credentials pytest

test-postgres:
	pytest -m postgres

open-report:
	xdg-open reports/test-report.html

serve-report:
	python -m http.server 8000 --directory reports

up:
	docker compose up -d postgres

down:
	docker compose down

clean:
	rm -rf .pytest_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +