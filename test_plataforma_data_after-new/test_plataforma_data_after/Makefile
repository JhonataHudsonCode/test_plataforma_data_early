.PHONY: install test-hml-credentials test-prod-credentials test-hml-database test-prod-database up down clean

PYTHON ?= python3.14
PYTEST_TARGETS ?= tests
PYTEST_K ?=
PYTEST_WORKERS ?=
PYTEST_PARALLEL ?=
PYTEST_DIST ?= load

# PYTEST_PARALLEL define se todos os testes selecionados rodam em processos
# paralelos. PYTEST_K filtra os nomes antes de iniciar a execução.
define pytest_parallel_args
$(shell $(PYTHON) -c "from dotenv import dotenv_values; env=dotenv_values('$(1)'); enabled=('$(PYTEST_PARALLEL)' or env.get('PYTEST_PARALLEL', 'false')).strip().lower() in {'1', 'true', 'yes', 'on'}; workers='$(PYTEST_WORKERS)' or env.get('PYTEST_WORKERS', '2'); print(f'-n {workers} --dist=$(PYTEST_DIST)' if enabled else '')")
endef

define pytest_k_args
$(if $(strip $(PYTEST_K)),-k "$(PYTEST_K)")
endef

install:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt


test-hml-credentials:
	TEST_ENV=hml CLIENT_SELECTION_SOURCE=credentials $(PYTHON) -m pytest $(PYTEST_TARGETS) $(call pytest_k_args) $(call pytest_parallel_args,.env.hml)

test-prod-credentials:
	TEST_ENV=prod CLIENT_SELECTION_SOURCE=credentials $(PYTHON) -m pytest $(PYTEST_TARGETS) $(call pytest_k_args) $(call pytest_parallel_args,.env.prod)

test-prod-database:
	TEST_ENV=prod CLIENT_SELECTION_SOURCE=database $(PYTHON) -m pytest $(PYTEST_TARGETS) $(call pytest_k_args) $(call pytest_parallel_args,.env.prod)

test-hml-database:
	TEST_ENV=hml CLIENT_SELECTION_SOURCE=database $(PYTHON) -m pytest $(PYTEST_TARGETS) $(call pytest_k_args) $(call pytest_parallel_args,.env.hml)

up:
	docker compose up -d postgres

down:
	docker compose down

clean:
	rm -rf .pytest_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
