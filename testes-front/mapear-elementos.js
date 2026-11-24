(() => {
  window.pararMapeamento?.();
  let blocoSelecao;
  let elementoDestacado;
  let sequenciaNomes = 0;

  function obterBlocoSelecao() {
    if (blocoSelecao) return blocoSelecao;

    blocoSelecao = document.createElement('div');
    blocoSelecao.setAttribute('aria-hidden', 'true');
    Object.assign(blocoSelecao.style, {
      position: 'fixed',
      display: 'none',
      pointerEvents: 'none',
      zIndex: '2147483647',
      boxSizing: 'border-box',
      border: '2px solid #38bdf8',
      borderRadius: '4px',
      background: 'rgba(56, 189, 248, 0.12)',
      boxShadow: '0 0 0 3px rgba(56, 189, 248, 0.28), 0 0 18px rgba(56, 189, 248, 0.65)',
    });
    document.documentElement.appendChild(blocoSelecao);
    return blocoSelecao;
  }

  function destacar(elemento) {
    if (!(elemento instanceof Element) || elemento === blocoSelecao) return;

    elementoDestacado = elemento;
    const retangulo = elemento.getBoundingClientRect();
    const bloco = obterBlocoSelecao();
    Object.assign(bloco.style, {
      display: 'block',
      left: `${retangulo.left}px`,
      top: `${retangulo.top}px`,
      width: `${retangulo.width}px`,
      height: `${retangulo.height}px`,
    });
  }

  function acompanharCursor(evento) {
    destacar(evento.target);
  }

  function reposicionarDestaque() {
    if (elementoDestacado?.isConnected) destacar(elementoDestacado);
  }

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

  function gerarNomeSugerido(elemento) {
    const identificador =
      elemento.id ||
      elemento.getAttribute('data-testid') ||
      elemento.getAttribute('data-test') ||
      elemento.getAttribute('aria-label') ||
      elemento.getAttribute('title') ||
      elemento.localName;
    const base = identificador
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/[^a-zA-Z0-9_-]+/g, '_')
      .replace(/^_+|_+$/g, '')
      .toLowerCase() || 'elemento';

    sequenciaNomes++;
    return `${base}_${sequenciaNomes}`;
  }

  async function selecionar(evento) {
    evento.preventDefault();
    evento.stopPropagation();
    evento.stopImmediatePropagation();

    const elemento = evento.target;
    destacar(elemento);
    const nomeSugerido = gerarNomeSugerido(elemento);
    const nomeDigitado = prompt('Digite o nome do elemento no YAML:', nomeSugerido);
    const nome = nomeDigitado?.trim() || nomeSugerido;

    if (!nomeDigitado?.trim()) {
      console.log(`ℹ️ Usando o nome sugerido: ${nome}`);
    }

    const xpath = gerarXPath(elemento);
    const texto = (elemento.innerText || elemento.textContent || '')
      .replace(/\s+/g, ' ')
      .trim();
    // JSON.stringify produz strings entre aspas válidas para valores YAML.
    const linhaYaml = [
      `${JSON.stringify(nome)}:`,
      `  locator: ${JSON.stringify(xpath)}`,
      `  text: ${JSON.stringify(texto)}`,
      `  type: ${JSON.stringify(elemento.localName)}`,
    ].join('\n');

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

  document.addEventListener('pointermove', acompanharCursor, true);
  document.addEventListener('click', selecionar, true);
  window.addEventListener('scroll', reposicionarDestaque, true);
  window.addEventListener('resize', reposicionarDestaque);

  window.pararMapeamento = () => {
    document.removeEventListener('pointermove', acompanharCursor, true);
    document.removeEventListener('click', selecionar, true);
    window.removeEventListener('scroll', reposicionarDestaque, true);
    window.removeEventListener('resize', reposicionarDestaque);
    blocoSelecao?.remove();
    blocoSelecao = null;
    elementoDestacado = null;
    delete window.pararMapeamento;
    console.log('🛑 Mapeamento encerrado.');
  };

  console.log('✅ Mapeamento ativo. Passe o cursor para destacar e clique no elemento desejado.');
  console.log('Para encerrar, execute: pararMapeamento()');
})();
