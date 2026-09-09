# language: pt

Funcionalidade: Validação de alertas por cliente

Cenário: Validar o índice de alertas no OpenSearch do cliente
    Dado que seleciono os clientes configurados para a execução
    E verifico se has_alerts está habilitado no Cognito
    Quando consulto o OpenSearch específico de cada cliente
    Então o índice elastalert_status deve existir, ser atual e respeitar o mapping esperado