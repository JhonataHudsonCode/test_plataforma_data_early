# language: pt

Funcionalidade: OpenSearch Cliente

Cenário: Validar a existência do Índice "axur" no OpenSearch
    Dado que realizo uma consulta na tabela de clientes
    E o campo has_axur do clientes está habilitado
    Quando realizo uma requisição ao OpenSearch
    Então deve existir um índice "axur" correspondente à data atual