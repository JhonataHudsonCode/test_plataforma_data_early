# language: pt

Funcionalidade: Validação do índice score_history pós-pipeline

Cenário: Validar scores do histórico recente
  Dado um cliente habilitado na plataforma
  Quando o pipeline de processamento finalizar
  Então o índice {cliente}_score_history deve conter documentos recentes
  E os subscores dos módulos habilitados devem ser válidos
  E a variação entre documentos consecutivos deve respeitar o limite permitido
