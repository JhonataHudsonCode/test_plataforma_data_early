# Testes de dados — After

## 1. Visão geral

O projeto **after** valida o resultado gerado depois do pipeline de dados. Além de confirmar que os índices existem, ele verifica documentos recentes, mappings, creation date, variações entre dias e métricas produzidas pela plataforma.

## 2. Quando executar

Execute após a conclusão do pipeline. O foco é responder: “o pipeline gerou os índices e métricas esperados, com dados atuais e consistentes?”

| Área | Evidência validada |
| --- | --- |
| Ativos | Índices de ativos, históricos e inventário |
| Compliance | `asset-compliance` e `asset-policy-compliance` |
| Software | `authorized-software` e `mandatory-software` |
| Scores | `score_history` e documentos do OTO Dashboard |
| Ambiente | Aliases e índices de destino do OpenSearch |

## 3. Arquitetura

```text
Teste pós-pipeline
        ↓
ProductDataValidator / OpenSearchAliasesValidator
        ↓
Repositories
        ↓
Cognito / OpenSearch
        ↓
ClientValidationReport → TXT, HTML, e-mail e Allure
```

- `tests/integration/client_data/`: executa os cenários pós-pipeline.
- `src/validators/after_pipeline/`: coordena validações por módulo.
- `src/validators/after_pipeline/oto_dashboard/`: valida cada seção do documento OTO Dashboard.
- `src/repositories/`: consulta índices, documentos, mappings, aliases e metadados.
- `src/models/opensearch_product/`: contratos de mapping.
- `src/services/`: reports e e-mail.

## 4. Catálogo de testes

| Teste | Principal validação |
| --- | --- |
| Ativos | `{cliente}_asset*`, `asset-historical-observability` e `asset-historical-software` |
| Compliance | `{cliente}_asset-compliance` e `asset-policy-compliance` |
| Políticas de software | `{cliente}_authorized-software` e `mandatory-software` |
| Score history | `{cliente}_score_history`, scores e variações recentes |
| OTO Dashboard | `{cliente}_oto_dashboard*`, mapping e seções do documento |
| Aliases | Todos os aliases do ambiente e seus índices de destino |

Os cenários BDD ficam em `tests/gherkins/after_pipeline/` e são anexados aos reports automaticamente.

## 5. Regras de validação

Conforme o cenário, o projeto valida:

- flag ou tipo de cliente no Cognito;
- índice existente, documentos e mapping esperado;
- timestamp, `date`, `lastupdated` ou creation date;
- localização de índices diários com formatos diferentes de data;
- documento do dia anterior ao documento mais recente, quando a comparação é necessária;
- variação máxima de 50% para métricas aplicáveis;
- scores numéricos, válidos e dentro do limite de variação configurado;
- prefixo do alias igual ao prefixo do índice de destino.

Se não houver documento de hoje, o report registra a falha e mantém as demais validações usando o documento mais recente quando o cenário permitir.

## 6. Configuração e execução

O projeto usa as variáveis de ambiente do repositório pai. Configure OpenSearch, banco Cognito, SMTP e a seleção de clientes antes de executar.

```bash
make install
make test-after-pipeline
make test-after-pipeline PYTHON=python3.14
make test-client-data
```

O marcador `after_pipeline` seleciona somente os testes executados após o pipeline.

## 7. Reports e e-mail

Cada teste gera:

```text
reports/client-validation/<nome_do_teste>.txt
reports/client-validation/<nome_do_teste>.html
```

Ao final da execução também são gerados:

```text
reports/client-validation/relatorio_geral.txt
reports/client-validation/relatorio_geral.html
```

Os reports classificam mensagens em `Falhas`, `Informativos` e `Aprovados`. A versão HTML e o e-mail usam estilos inline, compatíveis com clientes de e-mail.

O e-mail só é enviado se houver falhas ou se o pytest terminar com erro sem report associado. SPF, DKIM e DMARC do domínio de `SMTP_FROM` continuam necessários para reduzir classificação como spam.

## 8. Como evoluir um teste

1. Defina o mapping esperado em `src/models/opensearch_product/`.
2. Adicione a regra ao validator do módulo correspondente.
3. Reaproveite métodos do repository para localizar índices e documentos; não faça consultas diretas no teste.
4. Para uma nova seção do OTO Dashboard, crie um validator para o objeto pai e registre a ordem em `validation_order.json`.
5. Atualize o BDD com o mesmo nome da função de teste.
6. Separe `errors`, `infos` e `details` para que o report reflita o resultado corretamente.

