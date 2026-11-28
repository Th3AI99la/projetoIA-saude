export default function ({ parentElement, data }) {
  const lista = parentElement.querySelector(".dengue-metrics");
  const modal = parentElement.querySelector(".dengue-modal");
  const modelo = parentElement.querySelector("[data-template-indicador]");
  const titulo = modal.querySelector("#dengue-indicador-titulo");
  const explicacao = modal.querySelector("#dengue-indicador-explicacao");
  const calculo = modal.querySelector("[data-calculo]");
  const nota = modal.querySelector("[data-nota]");

  if (!lista.childElementCount) {
    lista.append(...data.map(() => modelo.content.cloneNode(true)));
  }
  for (const [indice, botao] of Array.from(lista.children).entries()) {
    const indicador = data[indice];
    botao.querySelector(".dengue-metric-label").textContent = indicador.titulo;
    botao.querySelector("strong").textContent = indicador.valor;
    botao.querySelector("small").textContent = indicador.resumo;
    botao.onclick = () => {
      titulo.textContent = indicador.titulo;
      explicacao.textContent = indicador.explicacao;
      calculo.textContent = indicador.calculo;
      nota.textContent = indicador.nota;
      modal.showModal();
    };
  }
  lista.hidden = false;
  modal.onclick = event => {
    if (event.target === modal) modal.close();
  };
}
