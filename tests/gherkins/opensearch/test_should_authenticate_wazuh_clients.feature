# language: pt

Funcionalidade: Validação de comunicação com a API Wazuh

Cenário: Autenticar o endpoint interno Wazuh de cliente SaaS elegível
  Dado que WAZUH_USERNAME, WAZUH_PASSWORD, WAZUH_ENDPOINT e WAZUH_INTERNAL_ENDPOINT foram configurados
  E que os clientes são consultados na base Cognito
  Quando o cliente possui client_type saas, octopus_endpoint preenchido e has_wazuh habilitado
  E o octopus_endpoint corresponde ao WAZUH_ENDPOINT
  Então o endpoint interno Wazuh deve autenticar na porta 55000
