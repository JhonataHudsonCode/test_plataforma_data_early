# language: pt

Funcionalidade: Validação dos índices de ativos pós-pipeline

Cenário: Validar documentos e variações de ativos
  Dado um cliente com has_asset habilitado
  Quando o pipeline de processamento finalizar
  Então os índices {cliente}_asset*, asset-historical-observability e asset-historical-software devem possuir documentos válidos
  E os mappings devem corresponder ao contrato esperado
  E os valores monitorados não devem variar mais que o limite permitido
