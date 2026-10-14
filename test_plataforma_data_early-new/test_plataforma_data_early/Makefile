.PHONY: install test test-hml test-prod test-credentials test-hml-credentials test-prod-credentials test-postgres report open-report serve-report up down clean

install:
	python3.14 -m pip install --upgrade pip
	pip install -r requirements.txt

test-hml:
	TEST_ENV=hml CLIENT_SELECTION_SOURCE=credentials pytest tests

test-hml-database:
	TEST_ENV=hml CLIENT_SELECTION_SOURCE=database pytest tests

test-prod:
	TEST_ENV=prod CLIENT_SELECTION_SOURCE=credentials pytest tests

clean:
	rm -rf .pytest_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +