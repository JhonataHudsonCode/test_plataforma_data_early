# language: pt

Funcionalidade: Validação do índice de produto EPSS

Cenário: Validar dados de probabilidade de exploração
  Dado que o índice epss está disponível no OpenSearch de produto
  Então ele deve possuir documentos e mapping válido
  E a data de criação deve corresponder à execução
