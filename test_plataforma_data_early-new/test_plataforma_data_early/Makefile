.PHONY: install test-hml test-hml-database test-prod clean

PYTHON ?= python3.14
PYTEST_TARGETS ?= tests
PYTEST_K ?=

define pytest_k_args
$(if $(strip $(PYTEST_K)),-k "$(PYTEST_K)")
endef

install:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt

test-hml:
	TEST_ENV=hml CLIENT_SELECTION_SOURCE=credentials $(PYTHON) -m pytest $(PYTEST_TARGETS) $(call pytest_k_args)

test-hml-database:
	TEST_ENV=hml CLIENT_SELECTION_SOURCE=database $(PYTHON) -m pytest $(PYTEST_TARGETS) $(call pytest_k_args)

test-prod:
	TEST_ENV=prod CLIENT_SELECTION_SOURCE=credentials $(PYTHON) -m pytest $(PYTEST_TARGETS) $(call pytest_k_args)

clean:
	rm -rf .pytest_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
