# QA Integration Tests

Repositório-base de testes de integração em Python + Pytest.

## Objetivo

Este projeto foi estruturado para servir como um repositório de testes de integração reutilizável, com:

- PostgreSQL
- OpenSearch
- suporte a múltiplas instâncias/conexões
- Pytest
- Allure Report
- execução local
- execução via Docker
- execução em pipeline
- separação entre conexão, queries, repositories e testes

Os testes **não executam SQL diretamente**. Eles apenas validam o retorno dos métodos da camada de repository.

## Arquitetura

```text
test_plataforma_data_early/
├── .github/
│   └── workflows/
│       └── integration-tests.yml
├── .vscode/
│   ├── extensions.json
│   ├── settings.json
│   └── tasks.json
├── src/
│   ├── config/
│   │   └── settings.py
│   ├── connections/
│   │   ├── base.py
│   │   ├── factory.py
│   │   ├── opensearch.py
│   │   └── postgres.py
│   ├── models/
│   │   └── table_metadata.py
│   ├── queries/
│   │   └── postgres_queries.py
│   └── repositories/
│       └── postgres_catalog_repository.py
├── tests/
│   ├── conftest.py
│   └── integration/
│       └── postgres/
│           ├── test_postgres_connection.py
│           └── test_postgres_pg_tables.py
├── .env.example
├── .gitignore
├── docker-compose.yml
├── Makefile
├── pyproject.toml
├── pytest.ini
└── requirements.txt
```

## Responsabilidades

### `src/config`

Centraliza configurações vindas de variáveis de ambiente.

### `src/connections`

Responsável apenas por criar, manter e fechar clientes/conexões.

### `src/queries`

Centraliza SQLs. Os testes não conhecem SQL.

### `src/repositories`

Executa queries e transforma os resultados em objetos de domínio.

### `tests`

Valida somente o comportamento público dos repositories/connections expostos pelas fixtures.

---

# Requisitos

- Python 3.10+
- Docker opcional
- Allure CLI opcional para abrir o relatório visualmente

## 1. Criar ambiente virtual

Linux/macOS:

```bash
python -m venv .venv
source .venv/bin/activate
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

## 2. Instalar dependências

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 3. Criar configuração local

Linux/macOS:

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

## 4. Subir PostgreSQL local

```bash
docker compose up -d postgres
```

O projeto usa por padrão:

```text
host: localhost
port: 5432
database: qa_db
user: qa_user
password: qa_password
```

## 5. Rodar os testes

```bash
pytest
```

Somente integração:

```bash
pytest -m integration
```

PostgreSQL:

```bash
pytest -m postgres
```

## Seleção de clientes e ambientes

Por padrão, os testes usam os clientes retornados pelo Cognito. Para usar a lista
de endpoints definida em `OCTOPUS_CLIENT_CREDENTIALS`, configure:

```bash
CLIENT_SELECTION_SOURCE=credentials
OCTOPUS_CLIENT_CREDENTIALS='{"ursula":{"endpoint":"https://octopus.ursula.clavissecurity.com","client_id":"clavis","username":"$URSULA_OPENSEARCH_USER","password":"$URSULA_OPENSEARCH_PASSWORD"},"comercial":{"endpoint":"https://demo.clavissecurity.com","client_id":"comercial","username":"$COMERCIAL_OPENSEARCH_USER","password":"$COMERCIAL_OPENSEARCH_PASSWORD"}}'
```

Os valores `$...` são resolvidos a partir do ambiente e não devem conter senhas
diretamente no arquivo versionado. `username` e `password` podem ser omitidos;
nesse caso são usados `OPENSEARCH_USER` e `OPENSEARCH_PASSWORD` do ambiente.
Os arquivos `.env_hml` e `.env_prod` podem fornecer configurações específicas:

```bash
make test
make test-credentials
make test-hml
make test-prod
make test-hml-credentials
make test-prod-credentials
```

O OpenSearch de produto continua usando `OPENSEARCH_HOST`. Os endpoints do JSON
são usados somente pelos testes que consultam o OpenSearch específico do cliente.
As flags e módulos continuam sendo consultados no database `cognito`; as tabelas
de activation keys, clients e alertClients usam uma conexão separada com o
database `clients`.

## 6. Allure

Os resultados são gravados automaticamente em:

```text
reports/allure-results
```

Para abrir:

```bash
allure serve reports/allure-results
```

Ou gerar HTML:

```bash
allure generate reports/allure-results -o reports/allure-report --clean
```

> `allure-pytest` gera os arquivos de resultado. Para abrir/gerar o HTML é necessário ter o Allure CLI instalado na máquina/agente.

---

# Testes incluídos

## Conectividade PostgreSQL

Valida o retorno de:

```python
repository.check_connection()
```

Internamente o repository executa:

```sql
SELECT 1 AS health;
```

O teste não conhece esse SQL.

## Validação de `pg_catalog.pg_tables`

O repository executa um `SELECT` na view:

```text
pg_catalog.pg_tables
```

Por padrão o teste procura:

```text
pg_catalog.pg_type
```

`pg_type` é uma tabela interna do PostgreSQL e torna o teste independente de dados de negócio.

O teste recebe um `TableMetadata` e valida somente o contrato retornado.

---

# Múltiplos bancos PostgreSQL

A configuração suporta prefixos.

Exemplo:

```env
SOURCE_PG_HOST=source-db
SOURCE_PG_PORT=5432
SOURCE_PG_DATABASE=source
SOURCE_PG_USER=user
SOURCE_PG_PASSWORD=password

TARGET_PG_HOST=target-db
TARGET_PG_PORT=5432
TARGET_PG_DATABASE=target
TARGET_PG_USER=user
TARGET_PG_PASSWORD=password
```

No Python:

```python
from src.config.settings import PostgresSettings
from src.connections.postgres import PostgresConnection

source_settings = PostgresSettings.from_env("SOURCE_PG")
target_settings = PostgresSettings.from_env("TARGET_PG")

source = PostgresConnection(source_settings)
target = PostgresConnection(target_settings)
```

Isso permite usar o mesmo padrão em cenários ETL, por exemplo:

```text
Source DB -> Transformação -> Target DB
```

---

# OpenSearch

A base de conexão já está incluída.

Variáveis:

```env
OPENSEARCH_HOST=localhost
OPENSEARCH_PORT=9200
OPENSEARCH_USER=admin
OPENSEARCH_PASSWORD=admin
OPENSEARCH_USE_SSL=false
OPENSEARCH_VERIFY_CERTS=false
```

Exemplo:

```python
from src.config.settings import OpenSearchSettings
from src.connections.opensearch import OpenSearchConnection

settings = OpenSearchSettings.from_env()
connection = OpenSearchConnection(settings)

client = connection.client
```

Para criar testes de OpenSearch, mantenha o mesmo padrão:

```text
connection -> repository -> test
```

Não coloque chamadas ao OpenSearch diretamente no teste.

---

# Pipeline

Um exemplo de GitHub Actions está em:

```text
.github/workflows/integration-tests.yml
```

A pipeline:

1. inicia PostgreSQL;
2. instala Python;
3. instala dependências;
4. executa Pytest;
5. gera `allure-results`;
6. publica os resultados como artifact.

A mesma estrutura pode ser transportada para:

- GitLab CI
- Azure DevOps
- Jenkins
- Bitbucket Pipelines

---

# Boas práticas adotadas

## SOLID

- **SRP:** conexão, SQL, repository, configuração e teste possuem responsabilidades separadas.
- **OCP:** novos tipos de conexão podem ser adicionados sem alterar os testes existentes.
- **LSP:** conexões seguem o contrato `BaseConnection`.
- **ISP:** o contrato de conexão é pequeno.
- **DIP:** repositories recebem a conexão por injeção de dependência.

## DRY

- conexão é criada em fixture;
- SQL centralizado;
- configuração centralizada;
- execução de query reutilizada dentro do repository.

## KISS

Não há framework interno complexo. O fluxo é:

```text
Settings
   ↓
Connection
   ↓
Repository
   ↓
Pytest
   ↓
Allure
```

---

# Regra para evolução do repositório

Para cada nova tecnologia:

```text
src/connections/<tecnologia>.py
src/queries/<tecnologia>_queries.py
src/repositories/<tecnologia>_repository.py
tests/integration/<tecnologia>/
```

Exemplo futuro:

```text
src/connections/mysql.py
src/connections/sqlserver.py
src/connections/s3.py

src/repositories/mysql_repository.py
src/repositories/sqlserver_repository.py
src/repositories/opensearch_repository.py

tests/integration/mysql/
tests/integration/sqlserver/
tests/integration/opensearch/
```

Esse padrão mantém o repositório escalável sem transformar os arquivos de teste em scripts de infraestrutura.