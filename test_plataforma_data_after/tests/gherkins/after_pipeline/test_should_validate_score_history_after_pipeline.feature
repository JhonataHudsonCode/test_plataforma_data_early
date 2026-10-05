# language: pt

Funcionalidade: Validação do índice score_history pós-pipeline

Cenário: Validar scores do histórico de hoje e ontem
  Dado um cliente habilitado na plataforma
  Quando o pipeline de processamento finalizar
  Então o índice {cliente}_score_history deve conter documentos para hoje e ontem
  E todos os documentos devem possuir date correspondente à data consultada
  E todos os documentos devem possuir _score e score positivos
  E os totais dos campos numéricos devem respeitar a variação máxima de 50%
