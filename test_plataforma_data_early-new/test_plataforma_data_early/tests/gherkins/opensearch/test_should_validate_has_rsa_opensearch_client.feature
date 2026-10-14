# language: pt

Funcionalidade: OpenSearch do Cliente

Cenário: Validar o índice RSA no OpenSearch do cliente
    Dado que seleciono os clientes configurados para a execução
    E verifico se has_rsa está habilitado no Cognito
    Quando consulto o OpenSearch específico de cada cliente
    Então o índice RSA deve existir, conter dados, ser atual e respeitar o mapping esperado