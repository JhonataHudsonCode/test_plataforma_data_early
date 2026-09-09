# language: pt

Funcionalidade: Validação de clients e alertClients

Cenário: Validar registros e timestamps por cliente
    Dado que seleciono os clientes configurados para a execução
    E verifico se has_bart está habilitado no Cognito
    Quando consulto as tabelas clients e alertClients no database clients
    Então createdAt e updatedAt devem possuir dados