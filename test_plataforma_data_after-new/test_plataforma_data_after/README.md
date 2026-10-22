# Testes pós-pipeline da Plataforma Data

Suíte de testes de integração em Python que confirma se os dados publicados após o pipeline estão disponíveis e consistentes no PostgreSQL e no OpenSearch.

## O que é validado

- conectividade com PostgreSQL e OpenSearch;
- índices e documentos de hoje para ativos, compliance e políticas de software;
- classificação, score e variação de inventário de ativos;
- score history e comparativos global/setorial;
- OTO Dashboard para clientes SaaS.

O fluxo é `settings -> connection -> repository -> validator -> pytest -> Allure`.

## Pré-requisitos

- Python 3.14 (Python 3.10+ é compatível com o código, mas a imagem e a CI usam 3.14);
- acesso de rede aos ambientes PostgreSQL e OpenSearch;
- Docker Desktop, opcionalmente, para executar no contêiner.

## Configuração local

No PowerShell, a partir da raiz do projeto:

```powershell
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Edite `.env` com as credenciais reais. Ele nunca deve ser enviado ao Git. As variáveis obrigatórias são:

```text
PG_HOST, PG_PORT, PG_DATABASE, PG_USER, PG_PASSWORD, PG_CONNECT_TIMEOUT
OPENSEARCH_HOST, OPENSEARCH_PORT, OPENSEARCH_USER, OPENSEARCH_PASSWORD
OPENSEARCH_USE_SSL, OPENSEARCH_VERIFY_CERTS
```

O banco `cognito` usa as mesmas credenciais do PostgreSQL principal; apenas o nome do banco é alterado pela fixture.

## Execução

```powershell
# toda a suíte de integração
python -m pytest

# grupos específicos
python -m pytest -m postgres
python -m pytest -m opensearch
python -m pytest -m client_data
```

Os mesmos comandos estão disponíveis via `make test`, `make test-postgres`, `make test-opensearch` e `make test-after-pipeline` em ambientes com GNU Make.

## Concorrência de OpenSearch

Os comandos do Makefile usam dois workers do Pytest (`pytest-xdist`). Cada teste
que percorre `client_targets` processa até cinco clientes simultaneamente no
OpenSearch de produto (`OPENSEARCH_HOST`).

```env
OPENSEARCH_MAX_CONCURRENT_CLIENTS=5
PYTEST_XDIST_WORKERS=2
OPENSEARCH_PRODUCT_SERIAL=true
```

O valor permitido é de `1` a `5`; valores acima de cinco são limitados a cinco.
`PYTEST_XDIST_WORKERS` controla quantos cenários Pytest rodam em paralelo; o
valor padrão é `2`. Assim, com a configuração acima, no máximo dois cenários e
cinco clientes por cenário são executados em paralelo.

Quando `OPENSEARCH_PRODUCT_SERIAL=true`, todos os cenários que consultam o
OpenSearch de produto compartilhado são enviados ao mesmo worker e executados
um por vez, mesmo com dois workers ativos.

O resultado bruto do Allure fica em `reports/allure-results`. Para gerar a interface visual, instale o Allure CLI e execute:

```powershell
allure generate reports/allure-results --clean -o reports/allure-report
allure open reports/allure-report
```

O e-mail de relatório fica desligado por padrão. Para ativá-lo, defina `SEND_TEST_REPORT_EMAIL=true` e preencha as variáveis `SMTP_*` no `.env`.

## Docker

Depois de criar e preencher `.env`:

```powershell
docker compose run --rm tests
```

O diretório `reports` é montado no host, preservando os resultados Allure.

## GitHub Actions

O workflow manual [`.github/workflows/integration-tests.yml`](.github/workflows/integration-tests.yml) roda a suíte de integração e publica os resultados Allure como artefato. Antes de dispará-lo, cadastre os seguintes GitHub Secrets:

```text
PG_HOST, PG_PORT, PG_DATABASE, PG_USER, PG_PASSWORD, PG_CONNECT_TIMEOUT,
PG_TARGET_SCHEMA, PG_TARGET_TABLE,
OPENSEARCH_HOST, OPENSEARCH_PORT, OPENSEARCH_USER, OPENSEARCH_PASSWORD,
OPENSEARCH_USE_SSL, OPENSEARCH_VERIFY_CERTS
```

O workflow é manual para evitar chamadas aos ambientes compartilhados em todo push ou pull request.
