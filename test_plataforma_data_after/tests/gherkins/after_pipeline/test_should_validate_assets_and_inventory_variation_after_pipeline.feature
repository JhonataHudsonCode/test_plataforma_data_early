# language: pt

Funcionalidade: Validação pós-pipeline de ativos

Cenário: Validar ativos, classificação e histórico
  Dado um cliente com has_asset habilitado
  Quando o pipeline de processamento finalizar
  Então os índices de ativos devem conter documentos de hoje
  E o inventário não deve ter queda brusca em relação a ontem
  E a classificação e os scores dos ativos devem estar preenchidos
