# language: pt

Funcionalidade: Validação de Axur por cliente

Cenário: Validar o índice Axur no OpenSearch do cliente
    Dado que seleciono os clientes configurados para a execução
    E verifico se has_axur está habilitado no Cognito
    Quando consulto todos os documentos do índice Axur
    Então o mapping do primeiro documento deve respeitar o contrato esperado
    E todos os documentos devem possuir @timestamp dos últimos sete dias
