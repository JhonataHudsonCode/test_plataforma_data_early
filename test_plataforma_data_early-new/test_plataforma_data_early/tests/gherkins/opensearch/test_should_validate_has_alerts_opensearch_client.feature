# language: pt

Funcionalidade: OpenSearch do Cliente

Cenário: Validar índice elastalert_status no OpenSearch do cliente
    Dado que seleciono os clientes configurados para a execução
    E verifico se has_alerts está habilitado no Cognito
    Quando consulto o OpenSearch específico de cada cliente
    Então o índice elastalert_status deve existir, ser atual e respeitar o mapping esperado