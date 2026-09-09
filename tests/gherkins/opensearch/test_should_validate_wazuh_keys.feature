# language: pt

Funcionalidade: Validação de chaves do Wazuh

Cenário: Validar chave necessária para o Wazuh por cliente
    Dado que seleciono os clientes configurados para a execução
    E verifico se has_wazuh está habilitado no Cognito
    Quando consulto a tabela activation_keys no database clients
    Então o cliente deve possuir a chave configurada