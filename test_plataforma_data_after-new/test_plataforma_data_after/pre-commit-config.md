s# Pre-Commit

Este tutorial ensina como instalar e usar o pre-commit com o gitleaks para checagem de credencial antes de commitar

## Pré-requisitos

Primeiramente, clone esse repositório e abra um terminal na pasta clonada

Você precisa ter o homebrew
https://brew.sh/

## Instalação
  
  - Instale o pre-commit:
  ```brew install pre-commit```

  - Instale o gitleaks:
  ```brew install gitleaks```

  - Com o terminal na pasta raiz do repositório octopus, instale o script do pre-commit:
  ```pre-commit install```
  
## Uso

  Após instalado, ao commitar, você verá que o gitleaks irá rodar antes e detectar credenciais, parando o commit caso encontre.

## Contribuição

  Quer contribuir? Coloque também o pre-commit com o gitleaks no seu projeto e ajude a manter ele mais seguro!
