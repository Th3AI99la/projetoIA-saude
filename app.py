"""Painel local para explorar as previsões retrospectivas de dengue em Goiás."""

import os
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from painel_dados import (
    ALVO, COLUNA_CONTAGEM, COLUNA_MUNICIPIO, COLUNA_PREVISTA,
    COLUNA_SEGUINTE, COLUNA_SEMANA, carregar_painel,
)
from painel_interface import INTERFACE, busca_municipal, geografia, mapa_goias


RAIZ = Path(__file__).resolve().parent
NOME_CSV = "01_saude_dengue.csv"
ABADIA = "ABADIA DE GOIAS"
RIO_DOCE = "APARECIDA DO RIO DOCE"
SEMANA_EXEMPLO = pd.Timestamp("2025-01-06")
MESES = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")
ROTULOS = {0: "Sem aumento relevante", 1: "Aumento relevante"}
AZUL = "#73b2f2"
AMARELO = "#f1cd58"
CORAL = "#f0838a"
VERDE = "#73d7c4"
EIXO = "#c7d4e1"
NOMES_EXIBICAO = {ABADIA: "Abadia de Goiás", "GOIANIA": "Goiânia"}
ATRIBUTOS = {
    COLUNA_CONTAGEM: "Notificações na semana de referência",
    **{f"notificacoes_semana_menos_{i}": f"Notificações há {i} semana(s)" for i in range(1, 5)},
    "semana_ano": "Número da semana ISO",
    "notificacoes_ultimas_4_semanas": "Soma das últimas 4 semanas",
    "diferenca_semanal": "Diferença para a semana anterior",
    "razao_media_anterior": "Razão em relação à média das 4 semanas anteriores + 1",
}


def inteiro(valor):
    return f"{valor:,}".replace(",", ".")


def percentual(valor):
    return f"{valor:.2%}".replace(".", ",")


def numero(valor):
    return f"{valor:.4f}".rstrip("0").rstrip(".").replace(".", ",")


def data(valor):
    return valor.strftime("%d/%m/%Y")


def periodo_semana(inicio):
    fim = inicio + pd.Timedelta(days=6)
    mes_final = MESES[fim.month - 1]
    if inicio.month == fim.month:
        return f"{inicio.day:02d}–{fim.day:02d} {mes_final} {fim.year}"
    mes_inicial = MESES[inicio.month - 1]
    ano_inicial = f" {inicio.year}" if inicio.year != fim.year else ""
    return f"{inicio.day:02d} {mes_inicial}{ano_inicial} – {fim.day:02d} {mes_final} {fim.year}"


def nome_municipio(valor):
    if valor in NOMES_EXIBICAO:
        return NOMES_EXIBICAO[valor]
    return " ".join(p.lower() if p in {"DE", "DO", "DA", "DOS", "DAS"} else p.capitalize() for p in valor.split())


def base_local():
    caminho = os.environ.get("DENGUE_CSV")
    if caminho:
        return Path(caminho).expanduser().resolve()
    opcoes = (RAIZ / "rafa" / NOME_CSV, RAIZ / "dados" / NOME_CSV)
    return next((opcao for opcao in opcoes if opcao.is_file()), opcoes[0])


@st.cache_resource(show_spinner="Treinando a árvore e preparando a avaliação retrospectiva…", max_entries=2)
def painel_em_cache(caminho, modificado_ns, tamanho):
    return carregar_painel(caminho)


def cabecalho(destino, painel=None):
    indicadores = ""
    if painel is not None:
        medidas, matriz = painel.metricas, painel.matriz
        total_positivos = matriz["vp"] + matriz["fn"]
        indicadores = f"""
            <section class="dengue-metrics" aria-label="Indicadores da árvore no teste de 2025">
              <article><p>Aumentos detectados</p><strong>{inteiro(matriz["vp"])}</strong><small>de {inteiro(total_positivos)} observados</small></article>
              <article><p>Recall</p><strong>{percentual(medidas["recall"])}</strong><small>aumentos observados que detectamos</small></article>
              <article><p>Precisão</p><strong>{percentual(medidas["precisao"])}</strong><small>de sinais confirmados</small></article>
              <article><p>F1</p><strong>{percentual(medidas["f1"])}</strong><small>precisão e recall</small></article>
            </section>
        """
    destino.html(f"""
        <header class="dengue-header">
          <div class="dengue-brand">
            <h1>Dengue em Goiás</h1>
            <p>Monitoramento de notificações</p>
            <small>Projeto Integrador · UEG · Teste de 2025</small>
          </div>
          {indicadores}
        </header>
    """)


def selecionar_municipio(municipio):
    st.session_state["municipio"] = municipio
    st.session_state["mapa_em_foco"] = True


def selecionar_exemplo(municipio, semana):
    selecionar_municipio(municipio)
    st.session_state["semana"] = semana


def casos_e_curiosidades(painel):
    casos = [
        ("Acerto do relatório", ABADIA, SEMANA_EXEMPLO, "check_circle"),
        ("Falso negativo do relatório", RIO_DOCE, SEMANA_EXEMPLO, "science"),
    ]
    comparaveis = painel.teste.dropna(subset=[COLUNA_SEGUINTE])
    if comparaveis.empty:
        return casos
    variacao = comparaveis[COLUNA_SEGUINTE] - comparaveis[COLUNA_CONTAGEM]
    falsos_positivos = comparaveis[COLUNA_PREVISTA].eq(1) & comparaveis[ALVO].eq(0)
    quedas = variacao.loc[falsos_positivos & variacao.lt(0)]
    destaques = [("Maior volume semanal", comparaveis[COLUNA_CONTAGEM].idxmax(), "monitoring")]
    if variacao.max() > 0:
        destaques.append(("Maior salto em uma semana", variacao.idxmax(), "trending_up"))
    if not quedas.empty:
        destaques.append(("Falso alarme seguido de queda", quedas.idxmin(), "trending_down"))
    for titulo, indice, icone in destaques:
        linha = comparaveis.loc[indice]
        casos.append((titulo, linha[COLUNA_MUNICIPIO], linha[COLUNA_SEMANA], icone))
    return casos


def barra_lateral(painel, municipio):
    def processar_busca():
        escolhido = st.session_state["busca_municipal"].get("municipio")
        if escolhido in painel.municipios:
            selecionar_municipio(escolhido)

    with st.sidebar:
        st.header("Explorar Goiás")
        busca_municipal(
            key="busca_municipal",
            data={
                "selecionado": nome_municipio(municipio),
                "municipios": [{"valor": nome, "rotulo": nome_municipio(nome)} for nome in painel.municipios],
            },
            on_municipio_change=processar_busca,
        )
        with st.container(key="curiosidades"):
            st.subheader("Casos e curiosidades")
            for titulo, cidade, semana, icone in casos_e_curiosidades(painel):
                if semana not in painel.semanas(cidade):
                    continue
                caso = painel.consultar(cidade, semana)
                futuro = "—" if caso.notificacoes_semana_seguinte is None else inteiro(caso.notificacoes_semana_seguinte)
                st.button(
                    titulo, icon=f":material/{icone}:", on_click=selecionar_exemplo,
                    args=(cidade, semana), width="stretch",
                )
                st.caption(
                    f"{nome_municipio(cidade)} · {periodo_semana(semana)}  \n"
                    f"{inteiro(caso.notificacoes_semana_atual)} → {futuro} notificações"
                )
        st.caption("Os indicadores no topo resumem todo o teste de 2025.")


def tema_grafico(grafico, altura):
    return grafico.properties(height=altura).configure(background="transparent", font="Poppins").configure_view(stroke=None).configure_axis(
        gridColor="#2b3e54", domainColor="#40546b", tickColor="#40546b", labelColor=EIXO, titleColor=EIXO,
        labelFontSize=11, titleFontSize=11, labelPadding=5,
    ).configure_legend(labelColor=EIXO, titleColor=EIXO)


def grafico_classes(semana):
    aumentos = int(semana[ALVO].sum())
    total = len(semana)
    distribuicao = pd.DataFrame({
        "Classe": [ROTULOS[0], ROTULOS[1]],
        "Municípios": [total - aumentos, aumentos],
    })
    distribuicao["Proporção"] = distribuicao["Municípios"] / total
    rosca = alt.Chart(distribuicao).mark_arc(innerRadius=43, outerRadius=65, cornerRadius=3, padAngle=.035).encode(
        theta="Municípios:Q",
        color=alt.Color("Classe:N", scale=alt.Scale(domain=list(ROTULOS.values()), range=[AZUL, CORAL]), legend=None),
        tooltip=["Classe:N", "Municípios:Q", alt.Tooltip("Proporção:Q", format=".1%")],
    )
    centro = alt.Chart(pd.DataFrame({"Total": [inteiro(total)], "Unidade": ["municípios"]}))
    valor = centro.mark_text(dy=-5, fontSize=23, fontWeight=700, color="#eef4fb").encode(text="Total:N")
    unidade = centro.mark_text(dy=15, fontSize=10, color=EIXO).encode(text="Unidade:N")
    return tema_grafico(rosca + valor + unidade, 158)


def grafico_sinais(semana):
    previstos = int(semana[COLUNA_PREVISTA].sum())
    observados = int(semana[ALVO].sum())
    medidas = pd.DataFrame({"Série": ["Previsão", "Observação"], "Municípios": [previstos, observados]})
    linhas = alt.Chart(medidas).encode(
        x=alt.X("Municípios:Q", title=None, axis=alt.Axis(tickMinStep=1, tickCount=4),
                scale=alt.Scale(domain=[0, max(previstos, observados, 1) * 1.22])),
        y=alt.Y("Série:N", sort=["Previsão", "Observação"], title=None, axis=alt.Axis(ticks=False, domain=False)),
        tooltip=["Série:N", "Municípios:Q"],
    )
    cores = alt.Scale(domain=["Previsão", "Observação"], range=[AZUL, CORAL])
    barras = linhas.mark_bar(size=23, cornerRadiusEnd=2).encode(color=alt.Color("Série:N", scale=cores, legend=None))
    valores = linhas.mark_text(align="left", dx=7, color="#eef4fb", fontSize=13).encode(text="Municípios:Q")
    return tema_grafico(barras + valores, 145)


def grafico_historico(painel, caso):
    inicio = caso.semana_referencia - pd.Timedelta(weeks=12)
    regiao = painel.historico
    selecao = regiao[COLUNA_MUNICIPIO].eq(caso.municipio) & regiao[COLUNA_SEMANA].between(inicio, caso.semana_seguinte)
    serie = regiao.loc[selecao, [COLUNA_SEMANA, COLUNA_CONTAGEM]].rename(
        columns={COLUNA_SEMANA: "Semana", COLUNA_CONTAGEM: "Notificações"},
    )
    serie["Papel"] = "Histórico"
    serie.loc[serie["Semana"].eq(caso.semana_referencia), "Papel"] = "Semana de referência"
    serie.loc[serie["Semana"].eq(caso.semana_seguinte), "Papel"] = "Semana observada"
    serie["Data"] = serie["Semana"].dt.strftime("%d/%m")
    cores = alt.Scale(domain=["Histórico", "Semana de referência", "Semana observada"], range=[AZUL, AMARELO, VERDE])
    barras = alt.Chart(serie).mark_bar(cornerRadiusEnd=2).encode(
        x=alt.X("Data:O", sort=serie["Data"].tolist(), title=None, axis=alt.Axis(labelAngle=0, labelOverlap=True)),
        y=alt.Y("Notificações:Q", title=None, axis=alt.Axis(tickMinStep=1)),
        color=alt.Color("Papel:N", scale=cores, legend=None),
        tooltip=["Papel:N", alt.Tooltip("Semana:T", format="%d/%m/%Y"), "Notificações:Q"],
    )
    return tema_grafico(barras, 255)


def renderizar_mapa(painel, semana, caso, semanas):
    cadastrados = painel.teste[["codigo_municipio", COLUNA_MUNICIPIO]].drop_duplicates()
    por_codigo = dict(zip(cadastrados["codigo_municipio"].astype(str), cadastrados[COLUNA_MUNICIPIO]))
    por_nome = {nome: codigo for codigo, nome in por_codigo.items()}
    contagens = dict(zip(semana["codigo_municipio"].astype(str), semana[COLUNA_CONTAGEM].map(int)))
    formas, limites = geografia()
    datas = {dia.date().isoformat(): dia for dia in semanas}

    def processar_acao():
        acao = st.session_state["mapa_goias"].get("acao")
        if not isinstance(acao, dict):
            return
        tipo, valor = acao.get("tipo"), acao.get("valor")
        if tipo == "goias":
            st.session_state["mapa_em_foco"] = False
        elif isinstance(valor, str):
            if tipo == "municipio" and valor in por_codigo:
                selecionar_municipio(por_codigo[valor])
            elif tipo == "semana" and valor in datas:
                st.session_state["semana"] = datas[valor]

    mapa_goias(
        key="mapa_goias",
        data={
            "formas": formas,
            "limites": limites,
            "municipios": {
                codigo: {"nome": nome_municipio(nome), "total": contagens.get(codigo)}
                for codigo, nome in por_codigo.items()
            },
            "codigo": por_nome[caso.municipio],
            "foco": st.session_state.get("mapa_em_foco", False),
            "semana": caso.semana_referencia.date().isoformat(),
            "semanas": [{"valor": iso, "rotulo": periodo_semana(dia)} for iso, dia in datas.items()],
        },
        on_acao_change=processar_acao,
    )


def resultado(caso):
    acertou = caso.classe_prevista == caso.classe_observada
    tipo = "Acerto" if acertou else ("Falso negativo" if caso.classe_observada == 1 else "Falso positivo")
    estado = "acerto" if acertou else "erro"
    st.html(f"""
        <div class="dengue-outcome {estado}">
          <div class="dengue-outcome-title">
            <div class="dengue-outcome-periodo">
              <small>Semana seguinte</small>
              <strong>{periodo_semana(caso.semana_seguinte)}</strong>
            </div>
            <span class="dengue-outcome-status">{tipo}</span>
          </div>
          <div class="dengue-comparison">
            <div><small>Previsão da árvore</small><strong>{ROTULOS[caso.classe_prevista]}</strong></div>
            <div><small>Resultado observado</small><strong>{ROTULOS[caso.classe_observada]}</strong></div>
          </div>
        </div>
    """)
    proxima = caso.notificacoes_semana_seguinte
    observada = "—" if proxima is None else inteiro(proxima)
    delta = None if proxima is None else f"{proxima - caso.notificacoes_semana_atual:+d}"
    st.metric("Notificações · semana analisada → semana seguinte", f"{inteiro(caso.notificacoes_semana_atual)} → {observada}", delta=delta, delta_color="off")
    if proxima is None:
        st.caption("O CSV informa a classe observada. A contagem da semana seguinte está fora do recorte.")
    st.caption("Aumento relevante: pelo menos 3 notificações a mais e crescimento de pelo menos 25%.")


def explorar(painel):
    municipio = st.session_state.get("municipio")
    if municipio not in painel.municipios:
        municipio = ABADIA if ABADIA in painel.municipios else painel.municipios[0]
        st.session_state["mapa_em_foco"] = False
    st.session_state["municipio"] = municipio
    semanas = painel.semanas(municipio)
    referencia = st.session_state.get("semana")
    if referencia not in semanas:
        referencia = SEMANA_EXEMPLO if SEMANA_EXEMPLO in semanas else semanas[-1]
    st.session_state["semana"] = referencia

    barra_lateral(painel, municipio)
    caso = painel.consultar(municipio, referencia)
    semana = painel.teste.loc[painel.teste[COLUNA_SEMANA].eq(referencia)]
    mapa, detalhes = st.columns((1.35, 1), gap="small", border=True)
    with mapa:
        st.subheader("Mapa de Goiás")
        renderizar_mapa(painel, semana, caso, semanas)

    with detalhes:
        st.subheader("Previsão e observação")
        st.markdown(f"**{nome_municipio(caso.municipio)}** · {periodo_semana(referencia)}")
        resultado(caso)
        st.subheader("Notificações ao longo do tempo")
        st.altair_chart(grafico_historico(painel, caso), width="stretch", theme=None, alt="Evolução semanal de notificações do município selecionado")
        st.html("""
            <div class="dengue-legend"><span class="legenda-historico"><i></i>Histórico</span><span class="legenda-referencia"><i></i>Referência</span><span class="legenda-observada"><i></i>Observada após a previsão</span></div>
        """)
        with st.expander("Ver o caminho da árvore", icon=":material/route:"):
            st.caption("Cada condição compara um valor do histórico com o limiar aprendido pela árvore.")
            if caso.regras:
                passos = [
                    {"Etapa": i, "Entrada": ATRIBUTOS[regra.entrada], "Valor no caso": numero(regra.valor),
                     "Condição seguida": f"{regra.operador} {numero(regra.limite)}"}
                    for i, regra in enumerate(caso.regras, start=1)
                ]
                st.dataframe(pd.DataFrame(passos), hide_index=True, width="stretch")
            else:
                st.caption("A árvore atribuiu a classe diretamente, sem divisões.")
            st.markdown(f"**Classe na folha:** {caso.classe_prevista} — {ROTULOS[caso.classe_prevista]}.")

    classes, sinais = st.columns(2, gap="small", border=True)
    with classes:
        st.subheader("Classes observadas")
        st.altair_chart(grafico_classes(semana), width="stretch", theme=None, alt="Distribuição das classes observadas nos municípios da semana")
        st.html("""
            <div class="dengue-legend"><span class="legenda-historico"><i></i>Sem aumento</span><span class="legenda-aumento"><i></i>Com aumento</span></div>
        """)
    with sinais:
        st.subheader("Aumentos por semana")
        st.altair_chart(grafico_sinais(semana), width="stretch", theme=None, alt="Municípios com aumento previsto e observado na semana alvo")
        st.caption(f"Semana de {periodo_semana(caso.semana_seguinte)} · municípios do teste")

def avaliar(painel):
    esquerda, direita = st.columns((1.2, 1), gap="medium")
    matriz = painel.matriz
    with esquerda:
        with st.container(border=True, key="matriz_confusao"):
            st.subheader("Matriz de confusão")
            st.caption(f"Teste retrospectivo de 2025 · {inteiro(len(painel.teste))} registros município-semana")
            st.html(f"""
                <table class="dengue-matrix">
                  <thead><tr><th scope="col">Classe observada</th><th scope="col">Previsão 0</th><th scope="col">Previsão 1</th></tr></thead>
                  <tbody>
                    <tr><th scope="row">0 · Sem aumento</th><td class="correto"><strong>{inteiro(matriz["vn"])}</strong><small>Verdadeiros negativos</small></td><td class="incorreto"><strong>{inteiro(matriz["fp"])}</strong><small>Falsos positivos</small></td></tr>
                    <tr><th scope="row">1 · Aumento</th><td class="incorreto"><strong>{inteiro(matriz["fn"])}</strong><small>Falsos negativos</small></td><td class="correto"><strong>{inteiro(matriz["vp"])}</strong><small>Verdadeiros positivos</small></td></tr>
                  </tbody>
                </table>
            """)
    with direita:
        with st.container(border=True, key="configuracao_modelo"):
            config = painel.configuracao
            st.subheader("Árvore de decisão")
            st.markdown(
                "Treino de **2019 a 2023**, seleção na validação de **2024** e teste retrospectivo de **2025**."
            )
            st.markdown(
                f"Foram avaliadas **{config['total_configuracoes']} configurações**. "
                f"A árvore selecionada usa **{config['entradas']} entradas**, profundidade máxima **{config['profundidade']}**, "
                f"mínimo de **{config['minimo_por_folha']} registros por folha** e {config['pesos']}."
            )
            st.caption(
                f"F1 na validação: {percentual(config['f1_validacao'])}. "
                f"Acurácia no teste: {percentual(painel.metricas['acuracia'])}."
            )
    st.caption("A avaliação mede o aumento de notificações definido na disciplina. Os resultados servem para análise acadêmica.")


def main():
    st.set_page_config(page_title="Monitoramento de dengue em Goiás", layout="wide")
    st.html(INTERFACE / "tailwind.css")
    st.html(RAIZ / "painel.css")
    topo = st.empty()
    cabecalho(topo)
    caminho = base_local()
    try:
        arquivo = caminho.stat()
        painel = painel_em_cache(caminho, arquivo.st_mtime_ns, arquivo.st_size)
    except FileNotFoundError:
        st.error(f"Base semanal não encontrada. Coloque {NOME_CSV} em rafa/ ou dados/, ou informe o caminho em DENGUE_CSV.")
        st.stop()
    except (OSError, ValueError) as erro:
        st.error(f"Não foi possível usar a base semanal: {erro}")
        st.stop()

    cabecalho(topo, painel)
    municipio, avaliacao = st.tabs(["Explorar município", "Avaliação do modelo"])
    with municipio:
        explorar(painel)
    with avaliacao:
        avaliar(painel)
    st.html('<footer class="dengue-source">Fontes · Base didática 01_saude_dengue.csv · Malha municipal: IBGE</footer>')


if __name__ == "__main__":
    main()
