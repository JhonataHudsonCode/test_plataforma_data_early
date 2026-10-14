# language: pt

Funcionalidade: Base de dados Assets

Cenário: Validar chave necessária para o Wazuh por cliente
    Dado que seleciono os clientes configurados para a execução
    E verifico se has_wazuh está habilitado no Cognito
    Quando consulto a tabela wazuh_keys no database Assets
    Então o cliente deve possuir activation_password com valor configurado