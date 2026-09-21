# language: pt

Funcionalidade: Validação de comunicação com a API Wazuh

Cenário: Autenticar endpoints Wazuh configurados
  Dado que as credenciais Wazuh foram configuradas
  Quando os endpoints configurados são consultados
  Então os endpoints externo e interno devem aceitar a autenticação
