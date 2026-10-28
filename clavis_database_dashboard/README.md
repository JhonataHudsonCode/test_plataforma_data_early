# Dashboard de resultados de testes Clavis

Aplicação independente em Python, Streamlit e Pandas que consulta os resultados
persistidos pelo Early e pelo After. A tela possui uma visão geral e uma aba
**Validações**, organizada por tipo, cenário, resultado e cliente/destinatário.

## Pré-requisitos

- Python 3.10 ou superior.
- Acesso de leitura ao banco PostgreSQL de relatórios e ao schema `qa_reports`.
- Tabelas `qa_test_runs`, `qa_test_scenarios` e `qa_test_results` criadas pelos
  scripts dos projetos de testes e ao menos uma execução persistida para ver dados.

## Instalação

Linux/macOS:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Crie um arquivo `.env` com os dados de uma conta PostgreSQL dedicada, com permissão de
leitura no schema de relatórios. Não use a conta que grava os resultados e não
versione o arquivo `.env`. O dashboard utiliza transações de somente leitura;
as permissões do usuário no banco devem reforçar essa restrição.

```env
REPORT_DB_HOST=localhost
REPORT_DB_PORT=5432
REPORT_DB_DATABASE=qa_reports
REPORT_DB_USER=usuario_leitura
REPORT_DB_PASSWORD=preencha_localmente
REPORT_DB_SCHEMA=qa_reports
REPORT_DB_CONNECT_TIMEOUT=10
DASHBOARD_TIMEZONE=America/Sao_Paulo
```

As configurações identificam o mesmo banco e schema usados pelos testes com
`REPORT_DB_*`. Aqui não é necessário configurar `REPORT_DB_ENABLED`: o dashboard
só lê registros já gravados.

## Executar

No diretório deste projeto, com o ambiente virtual ativado:

```bash
streamlit run app.py
```

O Streamlit informará a URL local no terminal. Os filtros de datas usam o fuso
`DASHBOARD_TIMEZONE`; o período inicial é dos últimos 30 dias até hoje, inclusive.
As datas consultam o horário de início da execução. Filtros vazios incluem todas
as opções.

## Indicadores da primeira versão

- Execuções e cenários distintos nos dados filtrados.
- Clientes distintos identificados nos resultados filtrados.
- Validações aprovadas, falhas e informativas: combinações distintas de cenário,
  destinatário, categoria e status, evitando contar mensagens repetidas como
  validações separadas. Um cliente pode ter mais de um status em etapas diferentes.
- Tabela de cenários com tempo, status do Pytest e identificação da execução.

Filtrar por cliente, categoria ou status restringe os registros que alimentam
os indicadores; cenários sem mensagens não aparecem quando esses filtros estão
ativos. Resultados globais, como OpenSearch central, aparecem por destinatário,
mas não são contados como clientes. O serviço de persistência atual também pode
agrupar mensagens de vários clientes sob um destinatário global; nesses casos o
dashboard mostra os dados exatamente como foram gravados.

A primeira versão carrega em memória as mensagens do período selecionado. Para
históricos muito grandes, reduza o período; paginação e agregações no banco podem
ser adicionadas depois. A interface não tem autenticação de usuários: use-a em
ambiente controlado e não a exponha publicamente sem proteção adicional.

## Testes locais

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Os testes de análise usam dados fictícios e não acessam o PostgreSQL.
