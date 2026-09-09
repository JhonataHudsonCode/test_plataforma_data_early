# language: pt

Funcionalidade: OpenSearch Cliente

Cenário: Validar a existência do Índice "elastalert_status" no OpenSearch
    Dado que realizo uma consulta na tabela de clientes
    E o campo has_alerts do clientes está habilitado
    Quando realizo uma requisição ao OpenSearch
    Então deve existir um índice "elastalert_status" correspondente à data atual