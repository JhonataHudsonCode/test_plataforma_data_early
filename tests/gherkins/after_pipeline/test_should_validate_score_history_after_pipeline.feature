# language: pt

Funcionalidade: Validação pós-pipeline de score

Cenário: Validar score e comparativos
  Dado um cliente habilitado na plataforma
  Quando o pipeline de processamento finalizar
  Então o score_history deve conter documento de hoje e do mês corrente
  E os subscores dos módulos habilitados devem ser válidos
  E os comparativos global e setorial devem estar calculados
