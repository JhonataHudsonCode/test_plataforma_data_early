.PHONY: install test-hml-credentials test-prod-credentials test-hml-database test-prod-database up down clean

PYTHON ?= python3.14
PYTEST_TARGETS ?= tests
PYTEST_K ?=

define pytest_k_args
$(if $(strip $(PYTEST_K)),-k "$(PYTEST_K)")
endef

install:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt


test-hml-credentials:
	TEST_ENV=hml CLIENT_SELECTION_SOURCE=credentials $(PYTHON) -m pytest $(PYTEST_TARGETS) $(call pytest_k_args)

test-prod-credentials:
	TEST_ENV=prod CLIENT_SELECTION_SOURCE=credentials $(PYTHON) -m pytest $(PYTEST_TARGETS) $(call pytest_k_args)

test-prod-database:
	TEST_ENV=prod CLIENT_SELECTION_SOURCE=database $(PYTHON) -m pytest $(PYTEST_TARGETS) $(call pytest_k_args)

test-hml-database:
	TEST_ENV=hml CLIENT_SELECTION_SOURCE=database $(PYTHON) -m pytest $(PYTEST_TARGETS) $(call pytest_k_args)

up:
	docker compose up -d postgres

down:
	docker compose down

clean:
	rm -rf .pytest_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
