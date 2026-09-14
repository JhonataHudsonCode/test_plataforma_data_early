# language: pt

Funcionalidade: Validação pós-pipeline de softwares

Cenário: Validar softwares obrigatórios e homologados
  Dado um cliente com has_asset habilitado
  Quando o pipeline de processamento finalizar
  Então os índices authorized-software e mandatory-software devem conter documentos de hoje
