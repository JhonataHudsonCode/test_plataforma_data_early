# language: pt

Funcionalidade: OpenSearch de clientes

Cenário: Validar a comunicação com o OpenSearch dos clientes SaaS
    Dado que obtenho os clientes cadastrados na base Cognito
    Quando filtro os clientes por saas na coluna client_type
    E consulto o OpenSearch de cada cliente pelo seu octopus_endpoint
    Então todos os clientes SaaS devem possuir um endpoint configurado e responder à autenticação