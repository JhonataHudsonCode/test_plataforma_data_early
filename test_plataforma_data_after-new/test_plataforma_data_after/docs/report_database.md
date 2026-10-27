## Persistência dos resultados em PostgreSQL

Early e After podem salvar os resultados dos relatórios em um banco PostgreSQL
dedicado ao término da execução. A persistência é desativada por padrão. Em
`.env.hml` ou `.env.prod`, configure as variáveis abaixo sem versionar os arquivos
que contenham credenciais:

```env
REPORT_DB_ENABLED=false
REPORT_DB_HOST=
REPORT_DB_PORT=5432
REPORT_DB_DATABASE=
REPORT_DB_USER=
REPORT_DB_PASSWORD=
REPORT_DB_SCHEMA=qa_reports
REPORT_DB_CONNECT_TIMEOUT=10
```

Antes de habilitar, execute manualmente `sql/report_database_schema.sql` no
banco escolhido. Para outro schema, ajuste o SQL e `REPORT_DB_SCHEMA` para o
mesmo nome. Após conferir permissões e credenciais, altere `REPORT_DB_ENABLED`
para `true` no ambiente desejado.

No encerramento, o processo controlador grava em uma transação: a execução,
os cenários observados pelo Pytest e as mensagens dos relatórios individuais.
Uma falha de conexão ou de gravação faz a execução terminar com código de erro
e não interfere na geração dos relatórios TXT/HTML. Em `--collect-only` não há
gravação no banco. Execuções interrompidas antes do `sessionfinish` não são
salvas; testes parametrizados com o mesmo nome de arquivo de report podem
compartilhar evidências, pois os relatórios atuais são nomeados pela função.
