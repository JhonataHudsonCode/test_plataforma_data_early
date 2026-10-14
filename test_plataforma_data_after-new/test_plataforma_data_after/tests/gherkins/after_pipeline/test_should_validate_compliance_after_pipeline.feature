# language: pt

Funcionalidade: OpenSearch de Produto

Cenário: Realizar comparação percentual nos documentos de ontem e de hoje dos indices asset-compliance e asset-policy-compliance 
  Dado um cliente com has_wazuh habilitado
  Então os índices _asset-compliance e asset-policy-compliance devem possuir documentos de ontem e de hoje
  E os valores monitorados não devem variar mais que o limite permitido de 50%
  E os mappings devem corresponder ao contrato esperado