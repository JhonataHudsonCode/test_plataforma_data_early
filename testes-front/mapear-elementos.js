(() => {
  window.pararMapeamento?.();

  function literalXPath(valor) {
    if (!valor.includes("'")) return `'${valor}'`;
    if (!valor.includes('"')) return `"${valor}"`;

    const partes = valor.split("'");
    const argumentos = [];

    partes.forEach((parte, indice) => {
      if (parte) argumentos.push(`'${parte}'`);
      if (indice < partes.length - 1) argumentos.push(`"'"`);
    });

    if (argumentos.length === 1) argumentos.push("''");
    return `concat(${argumentos.join(', ')})`;
  }

  function xpathAbsoluto(elemento) {
    const partes = [];

    while (elemento && elemento.nodeType === Node.ELEMENT_NODE) {
      const tag = elemento.localName;
      let posicao = 1;
      let anterior = elemento.previousElementSibling;

      while (anterior) {
        if (anterior.localName === tag) {
          posicao++;
        }

        anterior = anterior.previousElementSibling;
      }

      partes.unshift(`${tag}[${posicao}]`);
      elemento = elemento.parentElement;
    }

    return '/' + partes.join('/');
  }

  function gerarXPath(elemento) {
    const tag = elemento.localName;
    const atributos = [
      'id',
      'data-testid',
      'data-test',
      'name',
      'aria-label',
      'placeholder',
      'title',
    ];

    for (const atributo of atributos) {
      const valor = elemento.getAttribute(atributo);
      if (!valor) continue;

      const xpath = `//${tag}[@${atributo}=${literalXPath(valor)}]`;
      const resultado = document.evaluate(
        xpath,
        document,
        null,
        XPathResult.ORDERED_NODE_SNAPSHOT_TYPE,
        null,
      );

      if (resultado.snapshotLength === 1) {
        return xpath;
      }
    }

    return xpathAbsoluto(elemento);
  }

  async function selecionar(evento) {
    evento.preventDefault();
    evento.stopPropagation();
    evento.stopImmediatePropagation();

    const elemento = evento.target;
    const nome = prompt(
      'Digite o nome do elemento no YAML:',
      elemento.id || elemento.localName,
    );

    if (!nome?.trim()) {
      console.log('⚠️ Mapeamento cancelado para este elemento.');
      return;
    }

    const xpath = gerarXPath(elemento);
    // JSON.stringify produz aspas e escapes válidos para o valor YAML.
    const linhaYaml = `${JSON.stringify(nome.trim())}: ${JSON.stringify(xpath)}`;

    console.log('🎯 Elemento:', elemento);
    console.log('📋 YAML:');
    console.log(linhaYaml);

    try {
      await navigator.clipboard.writeText(linhaYaml);
      console.log('✅ Linha YAML copiada para a área de transferência.');
    } catch {
      console.log('⚠️ Copie a linha YAML exibida acima manualmente.');
    }
  }

  document.addEventListener('click', selecionar, true);

  window.pararMapeamento = () => {
    document.removeEventListener('click', selecionar, true);
    delete window.pararMapeamento;
    console.log('🛑 Mapeamento encerrado.');
  };

  console.log('✅ Mapeamento ativo. Clique no elemento desejado.');
  console.log('Para encerrar, execute: pararMapeamento()');
})();
