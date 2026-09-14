# language: pt

Funcionalidade: Validação pós-pipeline de compliance

Cenário: Validar dados de compliance do Wazuh
  Dado um cliente com has_wazuh habilitado
  Quando o pipeline de processamento finalizar
  Então os índices asset-compliance e asset-policy-compliance devem conter documentos de hoje
