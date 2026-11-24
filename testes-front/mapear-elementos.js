(() => {
  window.pararMapeamento?.(false);
  let blocoSelecao;
  let elementoDestacado;
  let sequenciaNomes = 0;
  const mapeamentos = new Map();

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

  function xpathQueLocalizaElemento(xpath, elemento) {
    const resultado = document.evaluate(
      xpath,
      document,
      null,
      XPathResult.ORDERED_NODE_SNAPSHOT_TYPE,
      null,
    );

    for (let indice = 0; indice < resultado.snapshotLength; indice++) {
      if (resultado.snapshotItem(indice).isSameNode(elemento)) {
        return xpath;
      }
    }

    return null;
  }

  function obterTextoDoElemento(elemento) {
    const copia = elemento.localName === 'div' && elemento.querySelector('ul > li')
      ? elemento.cloneNode(true)
      : elemento;

    if (copia !== elemento) {
      copia.querySelectorAll('ul').forEach(lista => lista.remove());
    }

    return (copia.innerText || copia.textContent || '')
      .replace(/\s+/g, ' ')
      .trim();
  }

  function primeiraClasse(elemento) {
    return (elemento.getAttribute('class') || '').trim().split(/\s+/)[0] || '';
  }

  function gerarXPath(elemento) {
    const tag = elemento.localName;
    const texto = obterTextoDoElemento(elemento);
    const atributos = [
      'id',
      'data-testid',
      'data-test',
      'name',
      'aria-label',
      'placeholder',
      'title',
      'role',
    ];

    // Para componentes styled-components, usa somente a primeira classe do className.
    const classeElemento = primeiraClasse(elemento);
    if (classeElemento) {
      const condicaoTexto = texto
        ? `[contains(normalize-space(.), ${literalXPath(texto)})]`
        : '';
      const xpathClasse =
        `//${tag}[contains(@class, ${literalXPath(classeElemento)})]${condicaoTexto}`;
      const locator = xpathQueLocalizaElemento(xpathClasse, elemento);
      if (locator) return locator;
    }

    // Se o elemento não tem classe, ancora no ancestral styled-components mais próximo.
    let ancestral = elemento.parentElement;
    while (ancestral && ancestral !== document.body) {
      const classeAncestral = primeiraClasse(ancestral);
      if (classeAncestral) {
        let restante = `//${tag}`;
        if (texto) {
          restante += `[contains(normalize-space(.), ${literalXPath(texto)})]`;
        } else {
          const atributo = atributos.find(nome => elemento.getAttribute(nome));
          if (atributo) {
            restante += `[@${atributo}=${literalXPath(elemento.getAttribute(atributo))}]`;
          }
        }

        const xpathAncorado =
          `//${ancestral.localName}[contains(@class, ${literalXPath(classeAncestral)})]${restante}`;
        const locator = xpathQueLocalizaElemento(xpathAncorado, elemento);
        if (locator) return locator;
      }
      ancestral = ancestral.parentElement;
    }

    // Fallbacks para elementos sem classe styled-components.
    if (texto) {
      const xpathTexto = `//${tag}[contains(normalize-space(.), ${literalXPath(texto)})]`;
      const locator = xpathQueLocalizaElemento(xpathTexto, elemento);
      if (locator) return locator;
    }

    for (const atributo of atributos) {
      const valor = elemento.getAttribute(atributo);
      if (!valor) continue;

      const xpath = `//${tag}[@${atributo}=${literalXPath(valor)}]`;
      const locator = xpathQueLocalizaElemento(xpath, elemento);
      if (locator) return locator;
    }

    // Mantém o locator curto quando não houver classe nem outro identificador.
    return elemento === document.body ? '//body' : `//body//${tag}`;
  }

  function gerarNomeSugerido(elemento) {
    const texto = obterTextoDoElemento(elemento);
    const identificador = texto ||
      elemento.getAttribute('aria-label') ||
      elemento.getAttribute('title') ||
      elemento.id ||
      elemento.getAttribute('data-testid') ||
      elemento.getAttribute('data-test') ||
      primeiraClasse(elemento);

    if (!identificador) {
      sequenciaNomes++;
      return `${elemento.localName}Elemento${sequenciaNomes}`;
    }

    const palavras = identificador
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .match(/[a-zA-Z0-9]+/g) || [];
    const base = palavras
      .map((palavra, indice) => {
        const normalizada = palavra.toLowerCase();
        return indice === 0
          ? normalizada
          : normalizada.charAt(0).toUpperCase() + normalizada.slice(1);
      })
      .join('') || 'elemento';

    sequenciaNomes++;
    const tipo = elemento.localName;
    return `${tipo}${base.charAt(0).toUpperCase()}${base.slice(1)}`;
  }

  function gerarConteudoYaml() {
    return [...mapeamentos.entries()].map(([nome, elemento]) => [
      `${/^[A-Za-z_][A-Za-z0-9_-]*$/.test(nome) ? nome : JSON.stringify(nome)}:`,
      `  locator: ${JSON.stringify(elemento.locator)}`,
      `  text: ${JSON.stringify(elemento.text)}`,
      `  type: ${JSON.stringify(elemento.type)}`,
    ].join('\n')).join('\n\n');
  }

  function gerarConteudoNomesAssertions() {
    return [...mapeamentos.keys()].map(nome => `${nome}:Assertions`).join('\n');
  }

  function gerarConteudoInstanciasAssertions() {
    return [...mapeamentos.keys()]
      .map(nome => `this.${nome} = new Assertions(page, this.elementos.${nome})`)
      .join('\n');
  }

  function baixarArquivoTexto(nomeArquivo, conteudo, tipo) {
    const arquivo = new Blob([conteudo], { type: tipo });
    const url = URL.createObjectURL(arquivo);
    const link = document.createElement('a');
    link.href = url;
    link.download = nomeArquivo;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function baixarMapeamentoYaml() {
    if (mapeamentos.size === 0) {
      console.log('⚠️ Nenhum elemento foi mapeado ainda.');
      return;
    }
    baixarArquivoTexto('mapeamento.yml', gerarConteudoYaml(), 'text/yaml;charset=utf-8');
    console.log(`✅ mapeamento.yml gerado com ${mapeamentos.size} elemento(s).`);
  }

  function baixarArquivosMapeamento() {
    if (mapeamentos.size === 0) {
      console.log('⚠️ Nenhum elemento foi mapeado ainda.');
      return;
    }

    const arquivos = [
      ['mapeamento.yml', gerarConteudoYaml(), 'text/yaml;charset=utf-8'],
      ['elementos_assertions.txt', gerarConteudoNomesAssertions(), 'text/plain;charset=utf-8'],
      ['instancias_assertions.txt', gerarConteudoInstanciasAssertions(), 'text/plain;charset=utf-8'],
    ];
    arquivos.forEach(([nome, conteudo, tipo], indice) => {
      window.setTimeout(() => baixarArquivoTexto(nome, conteudo, tipo), indice * 400);
    });
    console.log(`✅ Gerando os três arquivos com ${mapeamentos.size} elemento(s).`);
  }

  async function selecionar(evento) {
    evento.preventDefault();
    evento.stopPropagation();
    evento.stopImmediatePropagation();

    const elemento = evento.target;
    destacar(elemento);
    const nomeSugerido = gerarNomeSugerido(elemento);
    const nomeDigitado = prompt('Digite o nome do elemento no YAML:', nomeSugerido);
    let nome = nomeDigitado?.trim() || nomeSugerido;

    if (!nomeDigitado?.trim()) {
      console.log(`ℹ️ Usando o nome sugerido: ${nome}`);
    }

    if (mapeamentos.has(nome)) {
      const base = nome;
      let sufixo = 2;
      while (mapeamentos.has(`${base}_${sufixo}`)) sufixo++;
      nome = `${base}_${sufixo}`;
      console.log(`ℹ️ Nome repetido; usando: ${nome}`);
    }

    const xpath = gerarXPath(elemento);
    const texto = obterTextoDoElemento(elemento);
    mapeamentos.set(nome, {
      locator: xpath,
      text: texto,
      type: elemento.localName,
    });
    const conteudoYaml = gerarConteudoYaml();

    console.log('🎯 Elemento:', elemento);
    console.log(`📋 ${mapeamentos.size} elemento(s) acumulado(s). YAML atualizado:`);
    console.log(conteudoYaml);

    try {
      await navigator.clipboard.writeText(conteudoYaml);
      console.log('✅ YAML completo copiado para a área de transferência.');
    } catch {
      console.log('⚠️ Não foi possível copiar; o YAML completo está no console.');
    }
  }

  document.addEventListener('pointermove', acompanharCursor, true);
  document.addEventListener('click', selecionar, true);
  window.addEventListener('scroll', reposicionarDestaque, true);
  window.addEventListener('resize', reposicionarDestaque);

  window.baixarMapeamentoYaml = baixarMapeamentoYaml;
  window.baixarArquivosMapeamento = baixarArquivosMapeamento;
  window.pararMapeamento = (baixarArquivo = true) => {
    document.removeEventListener('pointermove', acompanharCursor, true);
    document.removeEventListener('click', selecionar, true);
    window.removeEventListener('scroll', reposicionarDestaque, true);
    window.removeEventListener('resize', reposicionarDestaque);
    blocoSelecao?.remove();
    blocoSelecao = null;
    elementoDestacado = null;
    if (baixarArquivo) baixarArquivosMapeamento();
    delete window.baixarMapeamentoYaml;
    delete window.baixarArquivosMapeamento;
    delete window.pararMapeamento;
    console.log('🛑 Mapeamento encerrado.');
  };

  console.log('✅ Mapeamento ativo. Passe o cursor para destacar e clique no elemento desejado.');
  console.log('Execute baixarArquivosMapeamento() para baixar os três arquivos ou pararMapeamento() para encerrar e baixá-los.');
})();
