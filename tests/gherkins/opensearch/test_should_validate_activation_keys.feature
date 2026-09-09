# language: pt

Funcionalidade: Validação de chaves de ativação

Cenário: Validar chave de ativação por cliente
    Dado que seleciono os clientes configurados para a execução
    E verifico se has_bart está habilitado no Cognito
    Quando consulto a tabela activation_keys no database clients
    Então o cliente deve possuir a chave de ativação configurada