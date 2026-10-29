# language: pt

Funcionalidade: OpenSearch de Produto

Cenário: Realizar comparação percentual para os atributos monitorados para os documentos do indice OTO Dashboard
  Dado um cliente SaaS
  Quando consulto o índice {cliente}_oto_dashboard pelos timestamps de hoje e ontem
  Então o mapping e as datas dos documentos retornados devem ser válidos
  E comparo os percentuais dos pares com horários de até uma hora de diferença
  E identifico no relatório os documentos sem correspondência
