# language: pt

Funcionalidade: OpenSearch Produto

Cenário: Validar a existência do Índice "axur" no OpenSearch
    Dado que realizo uma consulta na tabela de clientes
    E o campo has_axur do clientes está habilitado
    Quando realizo uma requisição ao OpenSearch
    Então deve existir um índice "{client}_asset" correspondente à data atual
    E deve existir um índice "{client}_asset-historical-observability" correspondente à data atual
    E deve existir um índice "{client}_asset-historical-software" correspondente à data atual
    