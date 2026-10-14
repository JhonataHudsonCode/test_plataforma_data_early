# language: pt

Funcionalidade: OpenSearch de Produto

Cenário: Validar que índice de produto cve_trends existe e tenha documentos com status ativo
  Dado que o índice cve_trends está disponível no OpenSearch de produto
  Quando consulto todos os documentos do índice
  Então o primeiro documento deve respeitar o mapping esperado
  E cada documento deve possuir status ativo