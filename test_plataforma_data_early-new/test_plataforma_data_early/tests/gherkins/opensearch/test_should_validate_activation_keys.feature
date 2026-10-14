# language: pt

Funcionalidade: Base dados Assets 

Cenário: Validar chave de ativação por cliente
    Dado que seleciono os clientes configurados para a execução
    E verifico se has_bart está habilitado no Cognito
    Quando consulto a tabela activation_keys no database assets
    Então o cliente deve possuir activation_key_id com chave cadastrada