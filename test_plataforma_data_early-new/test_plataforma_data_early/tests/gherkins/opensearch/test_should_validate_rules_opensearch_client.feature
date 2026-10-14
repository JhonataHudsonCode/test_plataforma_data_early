# language: pt

Funcionalidade: OpenSearch do Cliente

Cenário: Validar documentos e mapping de regras do indice Rules
    Dado que seleciono os clientes configurados para a execução
    E verifico se has_alerts está habilitado no Cognito
    Quando consulto o OpenSearch específico de cada cliente
    Então o índice rules deve possuir documentos e respeitar o mapping esperado
    E todos os documentos retornados devem ter @timestamp da data atual