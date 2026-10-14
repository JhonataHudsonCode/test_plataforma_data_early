# language: pt

Funcionalidade: Validação de comunicação com a API Wazuh

Cenário: Autenticar o endpoint interno Wazuh de cliente SaaS elegível
  Dado que cliente possui client_type saas, octopus_endpoint preenchido e has_wazuh habilitado
  Entao realizo autenticação no Wazuh do cliente
  