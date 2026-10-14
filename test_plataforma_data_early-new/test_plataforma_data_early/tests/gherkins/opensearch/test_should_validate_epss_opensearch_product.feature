# language: pt

Funcionalidade: OpenSearch do Produto

Cenário: Validar data de criação do indice EPSS
    Dado que que o indice epss esta disponível    
    Então ele deve possuir docuemntos e mapping valido
    E a data de criação deve corresponder a data de execução