.PHONY: install test test-postgres report open-report serve-report up down clean

install:
	python3.14 -m pip install --upgrade pip
	pip install -r requirements.txt

test:
	pytest

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