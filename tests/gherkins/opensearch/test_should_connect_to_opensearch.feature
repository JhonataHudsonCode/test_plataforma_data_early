# language: pt

Funcionalidade: Validação da comunicação com OpenSearch central

Cenário: Validar a comunicação com o OpenSearch central
    Dado que a configuração do OpenSearch central está disponível
    Quando realizo uma requisição de comunicação ao OpenSearch
    Então o OpenSearch central deve responder com sucesso
