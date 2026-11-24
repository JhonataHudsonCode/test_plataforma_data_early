# Validações da tela Softwares

`elementos_softwares.yml` mantém o catálogo de seletores, rótulos e tipos dos componentes. A classe `SoftwaresPage` carrega esse catálogo, resolve os locators do Playwright e centraliza as asserções de visibilidade.

O script `mapear-elementos.js`, executado no Console do navegador, copia novos itens no formato YAML `locator`, `text` e `type`. O Page Object interpreta esses itens como XPath quando o campo `strategy` não está definido.

Na geração do XPath, o script prioriza atributos únicos (`id`, `data-testid`, `aria-label`, `title` e outros) e depois texto único. Se precisar de um caminho relativo, ancora-o em um ancestral; o fallback parte de `//body`, nunca de `/html`.

No projeto Playwright que executa os testes, instale `yaml` caso ainda não esteja disponível:

```bash
npm install --save-dev yaml
```

Exemplo de uso em um teste Playwright:

```js
import { test } from '@playwright/test';
import { SoftwaresPage } from './softwares.page.js';

test('exibe os componentes da tela Softwares', async ({ page }) => {
  const softwares = new SoftwaresPage(page);
  await page.goto('/softwares');
  await softwares.validarElementosVisiveis();
});
```

Para validar um subconjunto, passe as chaves do YAML:

```js
await softwares.validarElementosVisiveis([
  'hosts_monitorados',
  'visao_geral_dos_softwares',
  'grafico_visao_geral',
]);
```

Os seletores de classes `.sc-*` e posições `nth` foram transcritos dos `expect` da imagem. Eles podem precisar de atualização se a estrutura ou a ordem dos componentes da aplicação mudar.
