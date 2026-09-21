# Testes de dados — Early

## 1. Visão geral

O projeto **early** valida a disponibilidade e o contrato dos dados que a plataforma já deve expor. Ele identifica indisponibilidade de integrações, ausência de índices, documentos, mappings ou registros de suporte antes de uma etapa posterior do processamento.

## 2. Quando executar

Execute antes ou no início do fluxo de validação de dados. O foco é responder: “os dados e integrações necessários estão disponíveis e íntegros?”

| Área | Evidência validada |
| --- | --- |
| Cognito e base clients | Flags do cliente, activation keys, `clients` e `alertClients` |
| OpenSearch do cliente | `rsa`, `rules`, `elastalert_status` e `axur` |
| OpenSearch de produto | Vulnerabilidades, EPSS, histórico de vulnerabilidades e `cve_trends` |

## 3. Arquitetura

```text
Teste de integração
        ↓
Validator
        ↓
Repository
        ↓
Cognito / PostgreSQL / OpenSearch
        ↓
ClientValidationReport → TXT, HTML, e-mail e Allure
```

- `tests/`: pontos de entrada e composição dos reports.
- `src/validators/`: regras de negócio e mensagens de validação.
- `src/repositories/`: consultas a banco e OpenSearch.
- `src/models/`: contratos esperados, principalmente mappings.
- `src/queries/`: SQLs centralizados.
- `src/services/`: reports e envio de e-mail.

### Arquivos de configuração da execução

| Arquivo | Função |
| --- | --- |
| `src/config/settings.py` | Lê e valida variáveis de ambiente, incluindo conexões, ambiente selecionado e clientes por credencial. Também expõe os objetos de configuração usados pelas fixtures. |
| `tests/conftest.py` | Centraliza fixtures do Pytest para conexões e repositories. Inicia a pasta de reports, consolida os resultados ao fim da sessão e controla o envio de e-mail em caso de falha. |
| `pytest.ini` | Define descoberta dos testes, marcadores (`integration`, `postgres`, `opensearch` e outros) e opções padrão do Pytest, como a geração de resultados do Allure. |

## 4. Catálogo de testes

| Teste | Principal validação |
| --- | --- |
| RSA | Flag `has_rsa`, índice `rsa`, documento recente e mapping |
| Alertas | Flag `has_alerts`, índice `elastalert_status` e mapping |
| Regras | Índice `rules`, documentos e mapping |
| Vulnerabilidades | `vulnerability-was`, `vulnerability-vm` e `vulnerability-vm-new` |
| EPSS | Índice de produto `epss` e mapping |
| Histórico | `{cliente}_vulnerability-historical`, documentos recentes e mapping |
| CVE trends | Índice global `cve_trends` e mapping |
| Axur | Flag `has_axur`, índice `axur` e mapping |
| Wazuh API | Comunicação e autenticação dos endpoints externo e interno na porta `55000` |
| Chaves | Chaves de ativação e chave Wazuh no database `clients` |
| Clientes | Registros e datas nas tabelas `clients` e `alertClients` |

Os cenários BDD ficam em `tests/gherkins/` e são anexados aos reports automaticamente.

## 5. Regras de validação

Conforme o índice ou tabela, o projeto valida:

- flag habilitada no Cognito;
- existência de índice, tabela, registro e documentos;
- mapping esperado;
- data de criação ou campo de data/timestamp;
- dados obrigatórios preenchidos;
- busca de índices com data em formatos diferentes, quando aplicável;
- comparação com documento do dia anterior em índices históricos.

Mensagens de erro devem ser incluídas em `failures`. Validações aprovadas devem ser incluídas em `details`; dados não aplicáveis devem ser incluídos em `infos`.

## 6. Configuração e execução

Crie `.env` a partir de `.env.example` e configure PostgreSQL, OpenSearch, SMTP e ambiente. Para configurações por ambiente, use `.env.hml` ou `.env.prod`.

```bash
make install
make test
make test-hml
make test-prod
make test-credentials
make test-client-data
make test-wazuh
```

Para selecionar clientes pelos endpoints configurados, use:

```bash
CLIENT_SELECTION_SOURCE=credentials
```

Com essa opção, `OCTOPUS_CLIENT_CREDENTIALS` define os clientes e endpoints. As flags continuam sendo consultadas no Cognito.

O teste da API Wazuh usa uma configuração independente, sem consultar os alvos do Octopus:

```bash
WAZUH_CREDENTIALS='{"clavis":{"endpoint":"https://wazuh.externo","internal_endpoint":"https://wazuh.interno:55000","username":"$WAZUH_CLAVIS_USER","password":"$WAZUH_CLAVIS_PASSWORD"}}'
```

O endpoint externo usa sua porta configurada; o `internal_endpoint` deve informar a porta `55000`. Apenas comunicação e autenticação são validadas.

## 7. Reports e e-mail

Cada teste gera:

```text
reports/client-validation/<nome_do_teste>.txt
reports/client-validation/<nome_do_teste>.html
```

Ao final da execução é gerado também:

```text
reports/client-validation/relatorio_geral.txt
reports/client-validation/relatorio_geral.html
```

Os reports separam `Falhas`, `Informativos` e `Aprovados`. Um mesmo cliente pode aparecer em mais de uma seção: uma falha não oculta as validações que foram aprovadas.

O e-mail é enviado apenas quando existe falha em um report ou quando a execução termina com erro sem report associado. Para boa entrega, o domínio de `SMTP_FROM` deve possuir SPF, DKIM e DMARC configurados.

## 8. Como evoluir um teste

1. Defina o contrato esperado em `src/models/`.
2. Implemente a regra no validator apropriado.
3. Use repositories para acessar sistemas externos; não escreva SQL no teste.
4. Adicione ou ajuste o cenário BDD com o mesmo nome da função de teste.
5. Registre falhas em `failures` e sucessos em `details`.
6. Execute o teste isolado antes de incluí-lo na execução completa.
