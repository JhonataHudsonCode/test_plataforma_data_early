# language: pt

Funcionalidade: Validação do índice diário de ativos pós-pipeline

Cenário: Validar os documentos atuais do índice de ativos
  Dado um cliente com has_asset habilitado
  Quando o pipeline de processamento finalizar
  Então o índice {cliente}_asset deve retornar documentos da data atual
  E todos os documentos retornados devem possuir @timestamp da data atual
  E o mapping do índice deve respeitar o contrato esperado
