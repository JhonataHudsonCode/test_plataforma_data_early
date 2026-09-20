# language: pt

Funcionalidade: Validação do índice OTO Dashboard pós-pipeline

Cenário: Validar métricas do documento OTO Dashboard
  Dado um cliente SaaS
  Quando o pipeline de processamento finalizar
  Então o índice {cliente}_oto_dashboard* deve possuir documentos recentes e mapping válido
  E as métricas e scores devem respeitar os limites de variação configurados
