# language: pt

Funcionalidade: Validação global de aliases do OpenSearch

Cenário: Validar o destino de todos os aliases do ambiente
  Dado que os aliases do ambiente foram consultados no OpenSearch
  Então cada alias deve apontar para um índice com o mesmo prefixo
