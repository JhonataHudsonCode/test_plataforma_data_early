# language: pt

Funcionalidade: OpenSearch Produto

Cenário: Validar a existência do Índice "axur" no OpenSearch
    Dado que realizo uma consulta na tabela de clientes
    E o campo has_axur do clientes está habilitado
    Quando realizo uma requisição ao OpenSearch
    Então deve existir um índice "{client}_vulnerability-was" correspondente à data atual
    E deve existir um índice "{client}_vulnerability-vm" correspondente à data atual
    E deve existir um índice "{client}_vulnerability-vm-new" correspondente à data atual
    