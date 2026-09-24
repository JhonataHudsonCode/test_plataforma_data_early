# language: pt

Funcionalidade: Validação do índice diário de ativos pós-pipeline

Cenário: Validar os documentos do índice de ativos da data atual
  Dado um cliente com has_asset habilitado
  Quando o pipeline de processamento finalizar
  Então deve existir um índice {cliente}_asset-{data atual}
  E todos os documentos retornados devem possuir @timestamp da data atual
  E o mapping do índice deve respeitar o contrato esperado
