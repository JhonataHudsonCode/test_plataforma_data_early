# language: pt

Funcionalidade: Validação das políticas de software pós-pipeline

Cenário: Validar documentos e mapping de políticas de software
  Dado um cliente com has_asset habilitado
  Quando o pipeline de processamento finalizar
  Então os índices {cliente}_authorized-software e mandatory-software devem possuir documentos válidos
  E os mappings devem corresponder ao contrato esperado
