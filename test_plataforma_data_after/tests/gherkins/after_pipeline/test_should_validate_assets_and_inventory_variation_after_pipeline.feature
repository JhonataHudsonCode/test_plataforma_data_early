# language: pt

Funcionalidade: Validação dos índices históricos de ativos pós-pipeline

Cenário: Validar documentos e variações dos históricos de ativos
  Dado um cliente com has_asset habilitado
  Quando o pipeline de processamento finalizar
  Então os índices {cliente}_asset-historical-observability e {cliente}_asset-historical-software devem possuir documentos válidos
  E os mappings devem corresponder ao contrato esperado
  E os campos monitorados devem ser somados em todos os documentos de hoje e ontem
  E a variação entre os totais diários não deve exceder 50%
