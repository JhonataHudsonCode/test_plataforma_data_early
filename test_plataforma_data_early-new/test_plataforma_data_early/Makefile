.PHONY: install test-hml test-hml-database test-prod test-hml-parallel test-hml-database-parallel test-prod-parallel clean

PYTHON ?= python3.14
PYTEST_WORKERS ?=
PYTEST_DIST ?= load

# Lê o valor do .env do ambiente selecionado. Um valor informado na chamada
# (ex.: make PYTEST_WORKERS=4 test-prod-parallel) tem precedência.
define pytest_workers
$(shell $(PYTHON) -c "from dotenv import dotenv_values; print('$(PYTEST_WORKERS)' or dotenv_values('$(1)').get('PYTEST_WORKERS', '2'))")
endef

install:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt

test-hml:
	TEST_ENV=hml CLIENT_SELECTION_SOURCE=credentials $(PYTHON) -m pytest tests

test-hml-database:
	TEST_ENV=hml CLIENT_SELECTION_SOURCE=database $(PYTHON) -m pytest tests

test-prod:
	TEST_ENV=prod CLIENT_SELECTION_SOURCE=credentials $(PYTHON) -m pytest tests

test-hml-parallel:
	TEST_ENV=hml CLIENT_SELECTION_SOURCE=credentials $(PYTHON) -m pytest tests -n $(call pytest_workers,.env.hml) --dist=$(PYTEST_DIST)

test-hml-database-parallel:
	TEST_ENV=hml CLIENT_SELECTION_SOURCE=database $(PYTHON) -m pytest tests -n $(call pytest_workers,.env.hml) --dist=$(PYTEST_DIST)

test-prod-parallel:
	TEST_ENV=prod CLIENT_SELECTION_SOURCE=credentials $(PYTHON) -m pytest tests -n $(call pytest_workers,.env.prod) --dist=$(PYTEST_DIST)

clean:
	rm -rf .pytest_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
