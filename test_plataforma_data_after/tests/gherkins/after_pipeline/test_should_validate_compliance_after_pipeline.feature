# language: pt

Funcionalidade: Validação dos índices de compliance pós-pipeline

Cenário: Validar documentos e mapping de compliance
  Dado um cliente com has_wazuh habilitado
  Quando o pipeline de processamento finalizar
  Então os índices {cliente}_asset-compliance e asset-policy-compliance devem possuir documentos e creation date válidos
  E os mappings devem corresponder ao contrato esperado
