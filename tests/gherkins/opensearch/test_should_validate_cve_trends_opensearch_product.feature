# language: pt

Funcionalidade: Validação do índice de produto cve_trends

Cenário: Validar tendências de CVEs
  Dado que o índice cve_trends está disponível no OpenSearch de produto
  Então ele deve possuir documentos e mapping válido
