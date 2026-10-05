# language: pt

Funcionalidade: Validação da comunicação com OpenSearch de clientes SaaS

Cenário: Validar a comunicação com o OpenSearch dos clientes SaaS
    Dado que obtenho os clientes cadastrados na base Cognito
    Quando filtro os clientes cujo client_type é saas
    E consulto o OpenSearch de cada cliente pelo seu octopus_endpoint
    Então todos os clientes SaaS devem possuir um endpoint configurado e responder à comunicação
