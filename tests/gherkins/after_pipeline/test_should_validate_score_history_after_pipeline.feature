# language: pt

Funcionalidade: OpenSearch de Produto

Cenário: Validar que indice score_history tenha dados do mes e ano atual e que contenha dados de score
  Dado um cliente habilitado na plataforma
  Então o índice {cliente}_score_history deve conter documentos recentes
  E os subscores dos módulos habilitados devem ser válidos
  E a variação entre documentos consecutivos deve respeitar o limite permitido