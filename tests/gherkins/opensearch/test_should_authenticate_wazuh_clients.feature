# language: pt

Funcionalidade: Validação de comunicação com a API Wazuh

Cenário: Autenticar endpoints Wazuh configurados
  Dado que as credenciais Wazuh foram configuradas
  Quando a API é consultada na porta 55000
  Então os endpoints externo e interno devem aceitar a autenticação
