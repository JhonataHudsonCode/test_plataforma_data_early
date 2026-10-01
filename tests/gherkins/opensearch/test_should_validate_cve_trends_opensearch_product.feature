# language: pt

Funcionalidade: Validação do índice de produto cve_trends

Cenário: Validar tendências de CVEs
  Dado que o índice cve_trends está disponível no OpenSearch de produto
  Quando consulto todos os documentos do índice
  Então o primeiro documento deve respeitar o mapping esperado
  E cada documento deve possuir status ativo
