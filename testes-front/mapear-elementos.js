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

  function caminhoRelativo(ancora, elemento) {
    const partes = [];
    let atual = elemento;

    while (atual && atual !== ancora && atual.nodeType === Node.ELEMENT_NODE) {
      const tag = atual.localName;
      let posicao = 1;
      let anterior = atual.previousElementSibling;

      while (anterior) {
        if (anterior.localName === tag) {
          posicao++;
        }

        anterior = anterior.previousElementSibling;
      }

      partes.unshift(`${tag}[${posicao}]`);
      atual = atual.parentElement;
    }

    if (atual !== ancora) return null;
    return partes.length ? `/${partes.join('/')}` : '';
  }

  function gerarXPath(elemento) {
    const tag = elemento.localName;
    const texto = (elemento.innerText || elemento.textContent || '')
      .replace(/\s+/g, ' ')
      .trim();

    // Prefere o texto visível mesmo quando o elemento também possui id.
    if (texto) {
      const xpathTexto = `//${tag}[contains(normalize-space(.), ${literalXPath(texto)})]`;
      const locator = xpathQueLocalizaElemento(xpathTexto, elemento);
      if (locator) return locator;
    }

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

    for (const atributo of atributos) {
      const valor = elemento.getAttribute(atributo);
      if (!valor) continue;

      const xpath = `//${tag}[@${atributo}=${literalXPath(valor)}]`;
      const locator = xpathQueLocalizaElemento(xpath, elemento);
      if (locator) return locator;
    }

    // Procura o ancestral mais próximo com atributo estável ou texto único.
    let ancora = elemento.parentElement;
    while (ancora && ancora !== document.body) {
      const caminho = caminhoRelativo(ancora, elemento);
      if (caminho) {
        for (const atributo of atributos) {
          const valor = ancora.getAttribute(atributo);
          if (!valor) continue;

          const xpathAncora = `//${ancora.localName}[@${atributo}=${literalXPath(valor)}]`;
          const xpathRelativo = `${xpathAncora}${caminho}`;
          const locator = xpathQueLocalizaElemento(xpathRelativo, elemento);
          if (locator) return locator;
        }

        const textoAncora = (ancora.innerText || ancora.textContent || '')
          .replace(/\s+/g, ' ')
          .trim();
        if (textoAncora) {
          const xpathTextoAncora =
            `//${ancora.localName}[normalize-space(.)=${literalXPath(textoAncora)}]`;
          const xpathRelativo = `${xpathTextoAncora}${caminho}`;
          const locator = xpathQueLocalizaElemento(xpathRelativo, elemento);
          if (locator) return locator;
        }
      }
      ancora = ancora.parentElement;
    }

    // Fallback relativo ao body: mantém o XPath começando com // e evita /html.
    const caminhoBody = caminhoRelativo(document.body, elemento);
    return caminhoBody ? `//body${caminhoBody}` : `//${tag}`;
  }

  function gerarNomeSugerido(elemento) {
    const texto = (elemento.innerText || elemento.textContent || '')
      .replace(/\s+/g, ' ')
      .trim();
    const identificador = texto ||
      elemento.getAttribute('aria-label') ||
      elemento.getAttribute('title') ||
      elemento.id ||
      elemento.getAttribute('data-testid') ||
      elemento.getAttribute('data-test');

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

  function baixarMapeamentoYaml() {
    if (mapeamentos.size === 0) {
      console.log('⚠️ Nenhum elemento foi mapeado ainda.');
      return;
    }

    const conteudo = gerarConteudoYaml();
    const arquivo = new Blob([conteudo], { type: 'text/yaml;charset=utf-8' });
    const url = URL.createObjectURL(arquivo);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'mapeamento.yml';
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    console.log(`✅ Arquivo ${link.download} gerado com ${mapeamentos.size} elemento(s).`);
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
    const texto = (elemento.innerText || elemento.textContent || '')
      .replace(/\s+/g, ' ')
      .trim();
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
  window.pararMapeamento = (baixarArquivo = true) => {
    document.removeEventListener('pointermove', acompanharCursor, true);
    document.removeEventListener('click', selecionar, true);
    window.removeEventListener('scroll', reposicionarDestaque, true);
    window.removeEventListener('resize', reposicionarDestaque);
    blocoSelecao?.remove();
    blocoSelecao = null;
    elementoDestacado = null;
    if (baixarArquivo) baixarMapeamentoYaml();
    delete window.baixarMapeamentoYaml;
    delete window.pararMapeamento;
    console.log('🛑 Mapeamento encerrado.');
  };

  console.log('✅ Mapeamento ativo. Passe o cursor para destacar e clique no elemento desejado.');
  console.log('Execute baixarMapeamentoYaml() para baixar sem encerrar ou pararMapeamento() para finalizar e baixar o YAML.');
})();
