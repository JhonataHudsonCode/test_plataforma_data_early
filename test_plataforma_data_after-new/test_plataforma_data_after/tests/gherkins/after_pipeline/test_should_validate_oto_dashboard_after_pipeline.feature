# language: pt

Funcionalidade: OpenSearch de Produto

Cenário: Realizar comparação percentual para os atributos monitorados para os documentos do indice OTO Dashboard
  Dado um cliente SaaS
  Quando o índice _oto_dashboard_* deve possuir documentos recentes e mapping válido
  E as métricas e scores devem respeitar os limites de variação em relação ao documento do dia anterior