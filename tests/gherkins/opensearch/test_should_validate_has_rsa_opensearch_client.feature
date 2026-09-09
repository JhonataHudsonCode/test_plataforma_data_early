# language: pt

Funcionalidade: Validação de RSA por cliente

Cenário: Validar o índice RSA no OpenSearch do cliente
    Dado que seleciono os clientes configurados para a execução
    E verifico se has_rsa está habilitado no Cognito
    Quando consulto o OpenSearch específico de cada cliente
    Então o índice RSA deve existir, ser atual e respeitar o mapping esperado