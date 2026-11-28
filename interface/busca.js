function normalizar(texto) {
  return texto.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase().trim();
}

export default function ({ parentElement, data, setTriggerValue }) {
  const campo = parentElement.querySelector("#busca-cidade");
  const lista = parentElement.querySelector("#busca-resultados");
  const vazio = parentElement.querySelector(".busca-vazia");
  const municipios = data.municipios.map(item => ({
    ...item,
    nome: normalizar(item.valor),
    busca: normalizar(item.rotulo),
  }));

  function fechar() {
    lista.hidden = vazio.hidden = true;
    campo.setAttribute("aria-expanded", "false");
    campo.removeAttribute("aria-activedescendant");
  }

  function selecionar(opcao) {
    campo.value = opcao.textContent;
    fechar();
    setTriggerValue("municipio", opcao.dataset.valor);
  }

  function sugerir() {
    const consulta = normalizar(campo.value);
    fechar();
    lista.replaceChildren();
    if (!consulta) return;

    function prioridade(item) {
      if (item.nome === consulta || item.busca === consulta) return 0;
      return item.nome.startsWith(consulta) || item.busca.startsWith(consulta) ? 1 : 2;
    }

    const resultados = municipios.filter(item => item.nome.includes(consulta) || item.busca.includes(consulta))
      .sort((a, b) => prioridade(a) - prioridade(b))
      .slice(0, 7);
    for (const [indice, municipio] of resultados.entries()) {
      const opcao = document.createElement("li");
      opcao.id = "busca-opcao-" + indice;
      opcao.className = "opcao-selecao";
      opcao.setAttribute("role", "option");
      opcao.setAttribute("aria-selected", "false");
      opcao.dataset.valor = municipio.valor;
      opcao.textContent = municipio.rotulo;
      opcao.onmousedown = event => event.preventDefault();
      opcao.onclick = () => selecionar(opcao);
      lista.append(opcao);
    }
    lista.hidden = resultados.length === 0;
    vazio.hidden = !lista.hidden;
    campo.setAttribute("aria-expanded", String(!lista.hidden));
  }

  if (campo.dataset.selecionado !== data.selecionado) {
    campo.value = data.selecionado;
    campo.dataset.selecionado = data.selecionado;
    fechar();
  }
  campo.onfocus = () => campo.select();
  campo.oninput = sugerir;
  campo.onblur = fechar;
  campo.onkeydown = event => {
    if (event.key === "Escape") fechar();
    if (lista.hidden) return;
    const opcoes = [...lista.children];
    const ativo = opcoes.findIndex(opcao => opcao.getAttribute("aria-selected") === "true");
    if (event.key === "Enter") {
      event.preventDefault();
      selecionar(opcoes[Math.max(ativo, 0)]);
    }
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const proximo = event.key === "ArrowDown" ? Math.min(ativo + 1, opcoes.length - 1) : Math.max(ativo - 1, 0);
      for (const [indice, opcao] of opcoes.entries()) {
        opcao.setAttribute("aria-selected", String(indice === proximo));
      }
      campo.setAttribute("aria-activedescendant", opcoes[proximo].id);
      opcoes[proximo].scrollIntoView({ block: "nearest" });
    }
  };
}
