# language: pt

Funcionalidade: Validação de Axur por cliente

Cenário: Validar o índice Axur no OpenSearch do cliente
    Dado que seleciono os clientes configurados para a execução
    E verifico se has_axur está habilitado no Cognito
    Quando consulto documentos do índice Axur entre hoje e três meses atrás
    Então deve existir ao menos um documento no intervalo consultado
    E todos os documentos retornados devem possuir @timestamp nesse intervalo
    E o mapping do primeiro documento retornado deve respeitar o contrato esperado
