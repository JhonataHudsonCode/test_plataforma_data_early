# language: pt

Funcionalidade: Base de dados Clients

Cenário: Validar registros createdAt e updatedAt por cliente
    Dado que seleciono os clientes configurados para a execução
    E verifico se has_bart está habilitado no Cognito
    Quando consulto as tabelas clients e alertClients no database clients
    Então createdAt e updatedAt devem possuir dados