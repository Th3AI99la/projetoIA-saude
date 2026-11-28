const SVG_NS = "http://www.w3.org/2000/svg";
const formato = new Intl.NumberFormat("pt-BR");
const movimentoReduzido = matchMedia("(prefers-reduced-motion: reduce)");
const animacoes = new WeakMap();

function quadro(limites, margem) {
  const [x1, y1, x2, y2] = limites;
  const largura = x2 - x1;
  const altura = y2 - y1;
  const espaco = Math.max(largura, altura) * margem;
  return [x1 - espaco, y1 - espaco, largura + 2 * espaco, altura + 2 * espaco];
}

function moverCamera(svg, destino) {
  const configuracao = destino.join(" ");
  if (svg.dataset.destino === configuracao) return;
  svg.dataset.destino = configuracao;
  cancelAnimationFrame(animacoes.get(svg));
  const original = svg.getAttribute("viewBox");
  if (!original || movimentoReduzido.matches) {
    svg.setAttribute("viewBox", configuracao);
    return;
  }

  const origem = original.split(" ").map(Number);
  const inicio = performance.now();
  function mover(agora) {
    const fracao = Math.min((agora - inicio) / 420, 1);
    if (fracao === 1) {
      svg.setAttribute("viewBox", configuracao);
      animacoes.delete(svg);
      return;
    }
    const progresso = fracao * fracao * (3 - 2 * fracao);
    const posicao = origem.map((valor, indice) => valor + (destino[indice] - valor) * progresso);
    svg.setAttribute("viewBox", posicao.join(" "));
    animacoes.set(svg, requestAnimationFrame(mover));
  }
  animacoes.set(svg, requestAnimationFrame(mover));
}

function faixa(quantidade) {
  if (quantidade == null) return "ausente";
  if (quantidade === 0) return "zero";
  if (quantidade < 5) return "baixa";
  if (quantidade < 20) return "media";
  if (quantidade < 50) return "alta";
  return "maxima";
}

function rotuloContagem(valor) {
  if (valor == null) return "Sem dado na semana";
  return formato.format(valor) + (valor === 1 ? " notificação" : " notificações");
}

function desenhar(svg, formas) {
  const grupo = svg.querySelector("[data-mapa-formas]");
  if (grupo.childElementCount) return;
  const caminhos = formas.map(forma => {
    const path = document.createElementNS(SVG_NS, "path");
    path.setAttribute("d", forma.caminho);
    path.setAttribute("role", "button");
    path.dataset.codigo = forma.codigo;
    path.classList.add("mapa-municipio");
    return path;
  });
  grupo.append(...caminhos);
}

function periodo(parentElement, data, acionar) {
  const campo = parentElement.querySelector("#periodo-mapa");
  const lista = parentElement.querySelector("#periodo-opcoes");
  const rotulo = parentElement.querySelector("#periodo-valor");
  const anterior = parentElement.querySelector("[data-periodo-anterior]");
  const proximo = parentElement.querySelector("[data-periodo-proximo]");
  const indice = data.semanas.findIndex(item => item.valor === data.semana);
  const valores = data.semanas.map(item => item.valor).join(",");
  let digitado = "";
  let ultimaTecla = 0;

  function fechar() {
    lista.hidden = true;
    campo.setAttribute("aria-expanded", "false");
    campo.removeAttribute("aria-activedescendant");
    lista.querySelector("[data-ativa=true]")?.removeAttribute("data-ativa");
    digitado = "";
  }

  if (lista.dataset.opcoes !== valores) {
    fechar();
    lista.replaceChildren(...data.semanas.map((item, posicao) => {
      const opcao = document.createElement("li");
      opcao.id = "periodo-opcao-" + posicao;
      opcao.className = "opcao-selecao";
      opcao.dataset.posicao = String(posicao);
      opcao.setAttribute("role", "option");
      opcao.textContent = item.rotulo;
      return opcao;
    }));
    lista.dataset.opcoes = valores;
  }
  const opcoes = [...lista.children];
  rotulo.textContent = data.semanas[indice].rotulo;
  for (const [posicao, opcao] of opcoes.entries()) {
    opcao.setAttribute("aria-selected", String(posicao === indice));
  }

  function destacar(posicao) {
    const opcao = opcoes[Math.max(0, Math.min(posicao, opcoes.length - 1))];
    lista.querySelector("[data-ativa=true]")?.removeAttribute("data-ativa");
    opcao.dataset.ativa = "true";
    campo.setAttribute("aria-activedescendant", opcao.id);
    if (opcao.offsetTop < lista.scrollTop) lista.scrollTop = opcao.offsetTop;
    if (opcao.offsetTop + opcao.offsetHeight > lista.scrollTop + lista.clientHeight) {
      lista.scrollTop = opcao.offsetTop + opcao.offsetHeight - lista.clientHeight;
    }
  }

  function abrir() {
    const caixa = campo.getBoundingClientRect();
    const abaixo = innerHeight - caixa.bottom - 14;
    const acima = caixa.top - 14;
    const sobe = abaixo < 190 && acima > abaixo;
    lista.dataset.acima = String(sobe);
    lista.style.setProperty("--altura-lista", Math.max(80, sobe ? acima : abaixo) + "px");
    lista.hidden = false;
    campo.setAttribute("aria-expanded", "true");
    destacar(indice);
  }

  function selecionar(posicao) {
    fechar();
    if (posicao !== indice) acionar("semana", data.semanas[posicao].valor);
  }

  campo.onclick = () => lista.hidden ? abrir() : fechar();
  campo.onblur = event => {
    if (event.relatedTarget && !campo.parentElement.contains(event.relatedTarget)) fechar();
  };
  lista.onmousedown = event => {
    if (event.target.closest("[role=option]")) event.preventDefault();
  };
  lista.onclick = event => {
    const opcao = event.target.closest("[role=option]");
    if (opcao) selecionar(Number(opcao.dataset.posicao));
  };
  campo.onkeydown = event => {
    const ativa = lista.querySelector("[data-ativa=true]");
    const posicao = ativa ? Number(ativa.dataset.posicao) : indice;
    const saltos = { ArrowUp: -1, ArrowDown: 1, PageUp: -10, PageDown: 10 };
    if (event.key === "Escape" && !lista.hidden) {
      event.preventDefault();
      fechar();
    } else if (event.key === "Tab") {
      fechar();
    } else if ((event.key === "Enter" || event.key === " ") && !lista.hidden) {
      event.preventDefault();
      selecionar(posicao);
    } else if (Object.hasOwn(saltos, event.key) || event.key === "Home" || event.key === "End") {
      event.preventDefault();
      const estavaFechada = lista.hidden;
      if (estavaFechada) abrir();
      if (event.key === "Home") destacar(0);
      else if (event.key === "End") destacar(opcoes.length - 1);
      else if (!estavaFechada) destacar(posicao + saltos[event.key]);
    } else if (/^\d$/.test(event.key) && !event.ctrlKey && !event.metaKey && !event.altKey) {
      if (lista.hidden) abrir();
      const agora = performance.now();
      digitado = agora - ultimaTecla < 700 ? digitado + event.key : event.key;
      ultimaTecla = agora;
      const sugestao = opcoes.findIndex(opcao => opcao.textContent.startsWith(digitado));
      if (sugestao >= 0) destacar(sugestao);
    }
  };

  const fecharAoClicarFora = event => {
    if (!lista.hidden && !campo.parentElement.contains(event.target)) fechar();
  };
  document.addEventListener("pointerdown", fecharAoClicarFora, true);
  anterior.disabled = indice <= 0;
  proximo.disabled = indice >= data.semanas.length - 1;
  anterior.onclick = () => selecionar(indice - 1);
  proximo.onclick = () => selecionar(indice + 1);
  return () => document.removeEventListener("pointerdown", fecharAoClicarFora, true);
}

export default function ({ parentElement, data, setTriggerValue }) {
  const svg = parentElement.querySelector(".mapa-svg");
  const previa = parentElement.querySelector(".mapa-previa");
  const voltar = parentElement.querySelector("[data-mapa-voltar]");
  const contexto = parentElement.querySelector("[data-mapa-legenda-contexto]");
  const acionar = (tipo, valor = null) => setTriggerValue("acao", { tipo, valor });
  const formaAtual = data.formas.find(forma => forma.codigo === data.codigo);
  const foco = data.foco && Boolean(formaAtual);
  const atual = data.municipios[data.codigo];

  const limparPeriodo = periodo(parentElement, data, acionar);
  desenhar(svg, data.formas);
  svg.dataset.foco = String(foco);
  svg.setAttribute("aria-label", foco ? "Limites de " + atual.nome : "Municípios de Goiás");
  previa.hidden = true;
  const cena = (foco ? data.codigo : "goias") + data.semana;
  if (contexto.dataset.cena && contexto.dataset.cena !== cena && !movimentoReduzido.matches) {
    contexto.parentElement.animate(
      [{ opacity: .45, transform: "translateY(4px)" }, { opacity: 1, transform: "translateY(0)" }],
      { duration: 200, easing: "ease-out" },
    );
  }
  contexto.dataset.cena = cena;
  parentElement.querySelector("[data-mapa-titulo]").textContent = foco ? atual.nome : "Goiás inteiro";
  contexto.textContent = foco ? rotuloContagem(atual.total) : "";
  parentElement.querySelector(".mapa-instrucao").textContent = foco
    ? "As informações do município aparecem ao lado ou abaixo do mapa."
    : "Clique em um município para aproximar e abrir seus dados.";

  const restaurarFoco = !foco && document.activeElement === voltar;
  voltar.hidden = !foco;
  voltar.onclick = () => acionar("goias");
  voltar.onkeydown = event => {
    if (event.key === "Escape") acionar("goias");
  };
  // O destaque de foco do navegador acompanha o elemento durante o zoom.
  if (foco && svg.contains(document.activeElement)) voltar.focus({ preventScroll: true });
  moverCamera(svg, foco ? quadro(formaAtual.limites, .19) : quadro(data.limites, .035));

  const formas = [...svg.querySelectorAll("path[data-codigo]")];
  for (const forma of formas) {
    const codigo = forma.dataset.codigo;
    const municipio = data.municipios[codigo];
    const selecionado = codigo === data.codigo;
    const visivel = !foco || selecionado;
    forma.dataset.visivel = String(visivel);
    forma.dataset.faixa = faixa(municipio?.total);
    forma.setAttribute("aria-label", (municipio?.nome ?? "Município " + codigo) + " · " + rotuloContagem(municipio?.total));
    forma.setAttribute("aria-pressed", String(selecionado));
    forma.setAttribute("aria-hidden", String(!visivel));
    forma.setAttribute("aria-disabled", String(foco || !municipio));
    if (foco) forma.removeAttribute("tabindex");
    else forma.setAttribute("tabindex", selecionado ? "0" : "-1");
  }
  if (restaurarFoco) formas.find(forma => forma.dataset.codigo === data.codigo)?.focus({ preventScroll: true });

  svg.onmousedown = event => {
    if (event.button === 0 && event.target.matches("path[data-codigo]")) event.preventDefault();
  };
  svg.onclick = event => {
    const codigo = event.target.dataset.codigo;
    if (data.municipios[codigo] && !foco) acionar("municipio", codigo);
  };
  svg.onpointerover = event => {
    const municipio = data.municipios[event.target.dataset.codigo];
    if (!municipio || foco || event.pointerType === "touch") return;
    previa.textContent = municipio.nome + " · " + rotuloContagem(municipio.total);
    previa.hidden = false;
  };
  svg.onpointerout = () => { previa.hidden = true; };
  svg.onkeydown = event => {
    const codigo = event.target.dataset.codigo;
    if (foco || !data.municipios[codigo]) return;
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      acionar("municipio", codigo);
    }
    const direcoes = { ArrowLeft: -1, ArrowUp: -1, ArrowRight: 1, ArrowDown: 1 };
    if (direcoes[event.key]) {
      event.preventDefault();
      const novo = (formas.indexOf(event.target) + direcoes[event.key] + formas.length) % formas.length;
      formas[novo].focus();
    }
  };

  const legenda = parentElement.querySelector("[data-mapa-faixas]");
  if (!legenda.childElementCount) {
    const faixas = { zero: "0", baixa: "1–4", media: "5–19", alta: "20–49", maxima: "50+", ausente: "Sem dado" };
    for (const [nivel, texto] of Object.entries(faixas)) {
      const item = document.createElement("li");
      const amostra = document.createElement("i");
      amostra.dataset.faixa = nivel;
      item.append(amostra, texto);
      legenda.append(item);
    }
  }
  return limparPeriodo;
}
