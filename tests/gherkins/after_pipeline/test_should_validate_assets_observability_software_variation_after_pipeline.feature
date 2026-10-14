# language: pt

Funcionalidade: OpenSearch do Produto

Cenário: Realizar comparação percentual entre os documentos de ontem e hoje do indice _asset-historical-observability e _asset-historical-software
  Dado um cliente com has_asset habilitado
  Então o índice  _asset-historical-observability e _asset-historical-software deve possuir documentos de ontem e de hoje
  E os valores monitorados não devem variar mais que o limite permitido de 50%
  E os mappings devem corresponder ao contrato esperado