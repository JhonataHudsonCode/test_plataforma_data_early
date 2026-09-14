# language: pt

Funcionalidade: Validação pós-pipeline do OTO Dashboard

Cenário: Validar métricas do OTO Dashboard
  Dado um cliente SaaS
  Quando o pipeline de processamento finalizar
  Então o índice oto_dashboard deve conter documentos de hoje
  E as métricas não devem apresentar variação brusca
