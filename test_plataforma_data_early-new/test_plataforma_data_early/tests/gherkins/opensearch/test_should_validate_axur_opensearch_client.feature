# language: pt

Funcionalidade: OpenSearch do Cliente

Cenário: Validar índice axur e que contenha documentos de pelo menos 3 meses atrás
    Dado que seleciono os clientes configurados para a execução
    E verifico se has_axur está habilitado no Cognito
    Quando consulto todos os documentos do índice Axur
    Então o mapping do primeiro documento deve respeitar o contrato esperado
    E deve existir ao menos um documento com @timestamp de 3 meses atrás