import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { parse } from 'yaml';
import { expect } from '@playwright/test';

const ELEMENTS_FILE = fileURLToPath(new URL('./elementos_softwares.yml', import.meta.url));

/** Page Object for the Softwares screen. Selectors and labels live in the YAML catalog. */
export class SoftwaresPage {
  constructor(page, elementsFile = ELEMENTS_FILE) {
    this.page = page;
    const definition = parse(readFileSync(elementsFile, 'utf8'));
    const source = definition.elementos ?? definition;
    this.elements = Object.fromEntries(
      Object.entries(source).filter(([, value]) => value && typeof value === 'object' && value.locator),
    );
  }

  element(name) {
    const definition = this.elements[name];
    if (!definition) {
      throw new Error(`Elemento '${name}' não está definido em elementos_softwares.yml`);
    }

    // O script de mapeamento gera locator/text/type; XPath é a estratégia padrão.
    const strategy = definition.strategy ?? 'locator';
    const options = definition.exact ? { exact: true } : undefined;
    let locator;
    switch (strategy) {
      case 'getByText':
        locator = this.page.getByText(definition.locator, options);
        break;
      case 'getByTitle':
        locator = this.page.getByTitle(definition.locator, options);
        break;
      case 'getByRole':
        locator = this.page.getByRole(definition.locator);
        break;
      case 'locator':
        locator = this.page.locator(definition.locator);
        if (definition.has_text) {
          const hasText = definition.exact
            ? new RegExp(`^${escapeRegExp(definition.has_text)}$`)
            : definition.has_text;
          locator = locator.filter({ hasText });
        }
        break;
      default:
        throw new Error(`Estratégia '${strategy}' inválida para '${name}'`);
    }

    return Number.isInteger(definition.nth) ? locator.nth(definition.nth) : locator;
  }

  async validarVisivel(name) {
    await expect(this.element(name), `Elemento esperado: ${name}`).toBeVisible();
  }

  async validarElementosVisiveis(names = Object.keys(this.elements)) {
    for (const name of names) {
      await this.validarVisivel(name);
    }
  }
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}
