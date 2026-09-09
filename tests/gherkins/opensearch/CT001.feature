# language: pt

Funcionalidade: OpenSearch Cliente

Cenário: Validar a existência do Índice RSA no OpenSearch
    Dado que realizo uma consulta na tabela de clientes
    E o campo has_rsa do clientes está habilitado
    Quando realizo uma requisição ao OpenSearch
    Então deve existir um índice RSA correspondente à data atual