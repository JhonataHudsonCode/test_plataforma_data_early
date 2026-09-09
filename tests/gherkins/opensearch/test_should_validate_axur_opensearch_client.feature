# language: pt

Funcionalidade: Validação de Axur por cliente

Cenário: Validar o índice Axur no OpenSearch do cliente
    Dado que seleciono os clientes configurados para a execução
    E verifico se has_axur está habilitado no Cognito
    Quando consulto o OpenSearch específico de cada cliente
    Então o índice axur deve existir, ser atual e respeitar o mapping esperado