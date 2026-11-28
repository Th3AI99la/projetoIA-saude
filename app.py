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
from painel_interface import INTERFACE, busca_municipal, catalogo_brasoes, geografia, indicadores, mapa_goias


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
NOMES_EXIBICAO = {ABADIA: "Abadia de Goiás", "COCALZINHO DE GOIAS": "Cocalzinho de Goiás", "GOIANIA": "Goiânia"}
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


def cabecalho(painel):
    medidas, matriz = painel.metricas, painel.matriz
    detectados = inteiro(matriz["vp"])
    observados = inteiro(matriz["vp"] + matriz["fn"])
    total_sinais = matriz["vp"] + matriz["fp"]
    sinalizados = inteiro(total_sinais)
    recall = percentual(medidas["recall"])
    precisao = percentual(medidas["precisao"])
    f1 = percentual(medidas["f1"])

    indicadores(key="indicadores_dengue", data=[
        {
            "titulo": "Aumentos detectados",
            "valor": detectados,
            "resumo": f"de {observados} observados",
            "explicacao": "Contamos um acerto quando a árvore sinaliza aumento relevante e a semana seguinte registra esse aumento.",
            "calculo": f"{detectados} registros com sinal e aumento observado",
            "nota": "Cada registro representa um município em uma semana. Na matriz de confusão, esses acertos são os verdadeiros positivos.",
        },
        {
            "titulo": "Recall",
            "valor": recall,
            "resumo": "aumentos observados que detectamos",
            "explicacao": "De todos os aumentos relevantes que ocorreram, qual proporção a árvore conseguiu sinalizar?",
            "calculo": f"{detectados} ÷ {observados} × 100 = {recall}",
            "nota": f"Os outros {inteiro(matriz['fn'])} aumentos ficaram sem sinal. São os falsos negativos.",
        },
        {
            "titulo": "Precisão",
            "valor": precisao,
            "resumo": "proporção de sinais corretos",
            "explicacao": "Entre as semanas sinalizadas pela árvore, quantas tiveram aumento relevante observado?",
            "calculo": f"{detectados} ÷ {sinalizados} × 100 = {precisao}" if total_sinais else "0% por convenção",
            "nota": (f"Houve {inteiro(matriz['fp'])} sinais sem aumento relevante observado. São os falsos positivos."
                     if total_sinais else "Com zero sinalizações, a divisão para calcular a precisão fica indefinida."),
        },
        {
            "titulo": "F1",
            "valor": f1,
            "resumo": "equilíbrio entre precisão e recall",
            "explicacao": "O F1 resume em um número tanto a proporção de sinais corretos quanto a proporção de aumentos detectados.",
            "calculo": "2 × (precisão × recall) ÷ (precisão + recall)",
            "nota": f"Com precisão de {precisao} e recall de {recall}, o F1 foi {f1}. O cálculo usa as proporções antes do arredondamento.",
        },
    ])


def selecionar_municipio(municipio):
    st.session_state["municipio"] = municipio


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
        st.button(
            "Goiás inteiro", icon=":material/map:", on_click=selecionar_municipio,
            args=(None,), width="stretch", type="primary" if municipio is None else "secondary",
        )
        busca_municipal(
            key="busca_municipal",
            data={
                "selecionado": nome_municipio(municipio) if municipio is not None else "",
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


def grafico_comparativo(medidas, unidade, cores):
    ordem = medidas["Série"].tolist()
    maior = max(medidas[unidade].max(), 1)
    linhas = alt.Chart(medidas).encode(
        x=alt.X(f"{unidade}:Q", title=None, axis=alt.Axis(tickMinStep=1, tickCount=4, format="d"),
                scale=alt.Scale(domain=[0, maior * 1.22])),
        y=alt.Y("Série:N", sort=ordem, title=None, axis=alt.Axis(ticks=False, domain=False)),
        tooltip=["Série:N", f"{unidade}:Q"],
    )
    escala = alt.Scale(domain=ordem, range=cores[:len(ordem)])
    barras = linhas.mark_bar(size=23, cornerRadiusEnd=2).encode(color=alt.Color("Série:N", scale=escala, legend=None))
    valores = linhas.mark_text(align="left", dx=7, color="#eef4fb", fontSize=13).encode(text=f"{unidade}:Q")
    return tema_grafico(barras + valores, 145)


def comparacao_estado(semana, seguinte):
    st.subheader("Municípios com aumento relevante")
    st.markdown(f"**Goiás inteiro** · Semana seguinte de {periodo_semana(seguinte)}")
    medidas = pd.DataFrame({
        "Série": ["Sinalizados", "Com aumento"],
        "Municípios": [int(semana[COLUNA_PREVISTA].sum()), int(semana[ALVO].sum())],
    })
    st.altair_chart(
        grafico_comparativo(medidas, "Municípios", [AZUL, CORAL]), width="stretch", theme=None,
        alt="Quantidade de municípios sinalizados pela árvore e com aumento relevante observado",
    )
    st.caption(
        f"Entre os {inteiro(len(semana))} municípios avaliados, a primeira barra mostra quantos a árvore sinalizou. "
        "A segunda mostra quantos registraram aumento relevante na semana seguinte."
    )


def comparacao_municipio(caso):
    st.subheader("Notificações entre semanas")
    st.markdown(f"**{nome_municipio(caso.municipio)}**")
    st.caption(f"{periodo_semana(caso.semana_referencia)} → {periodo_semana(caso.semana_seguinte)}")
    atual, seguinte = caso.notificacoes_semana_atual, caso.notificacoes_semana_seguinte
    medidas = pd.DataFrame({
        "Série": ["Semana analisada", "Semana seguinte"],
        "Notificações": pd.array([atual, seguinte], dtype="Int64"),
    }).dropna(subset=["Notificações"])
    st.altair_chart(
        grafico_comparativo(medidas, "Notificações", [AMARELO, VERDE]), width="stretch", theme=None,
        alt="Contagens registradas de notificações nas duas semanas do município selecionado",
    )
    previsao = ROTULOS[caso.classe_prevista].lower()
    observacao = ROTULOS[caso.classe_observada].lower()
    st.markdown(f"A árvore indicou **{previsao}**. A base registrou a classe **{observacao}**.")
    if seguinte is None:
        st.caption("A base informa o resultado observado, e a contagem da semana seguinte está fora do recorte.")
    else:
        st.caption("Aumentos relevantes exigem pelo menos 3 notificações a mais e crescimento de pelo menos 25%.")


def grafico_historico(painel, municipio, referencia, seguinte):
    inicio = referencia - pd.Timedelta(weeks=12)
    regiao = painel.historico
    selecao = regiao[COLUNA_SEMANA].between(inicio, seguinte)
    if municipio is not None:
        selecao &= regiao[COLUNA_MUNICIPIO].eq(municipio)
    serie = regiao.loc[selecao, [COLUNA_SEMANA, COLUNA_CONTAGEM]].rename(
        columns={COLUNA_SEMANA: "Semana", COLUNA_CONTAGEM: "Notificações"},
    )
    if municipio is None:
        serie = serie.groupby("Semana", as_index=False)["Notificações"].sum()
    serie["Papel"] = "Histórico"
    serie.loc[serie["Semana"].eq(referencia), "Papel"] = "Semana de referência"
    serie.loc[serie["Semana"].eq(seguinte), "Papel"] = "Semana observada"
    serie["Data"] = serie["Semana"].dt.strftime("%d/%m")
    cores = alt.Scale(domain=["Histórico", "Semana de referência", "Semana observada"], range=[AZUL, AMARELO, VERDE])
    barras = alt.Chart(serie).mark_bar(cornerRadiusEnd=2).encode(
        x=alt.X("Data:O", sort=serie["Data"].tolist(), title=None, axis=alt.Axis(labelAngle=0, labelOverlap=True)),
        y=alt.Y("Notificações:Q", title=None, axis=alt.Axis(tickMinStep=1)),
        color=alt.Color("Papel:N", scale=cores, legend=None),
        tooltip=["Papel:N", alt.Tooltip("Semana:T", format="%d/%m/%Y"), "Notificações:Q"],
    )
    return tema_grafico(barras, 255)


def renderizar_mapa(painel, semana, municipio, referencia, semanas):
    cadastrados = painel.teste[["codigo_municipio", COLUNA_MUNICIPIO]].drop_duplicates()
    por_codigo = dict(zip(cadastrados["codigo_municipio"].astype(str), cadastrados[COLUNA_MUNICIPIO]))
    por_nome = {nome: codigo for codigo, nome in por_codigo.items()}
    codigo = por_nome.get(municipio)
    fonte_brasao = catalogo_brasoes().get(codigo)
    brasao = {"arquivo": f"app/static/brasoes/{codigo}.webp", "fonte": fonte_brasao["fonte"]} if fonte_brasao else None
    contagens = dict(zip(semana["codigo_municipio"].astype(str), semana[COLUNA_CONTAGEM].map(int)))
    formas, limites = geografia()
    datas = {dia.date().isoformat(): dia for dia in semanas}

    def processar_acao():
        acao = st.session_state["mapa_goias"].get("acao")
        if not isinstance(acao, dict):
            return
        tipo, valor = acao.get("tipo"), acao.get("valor")
        if tipo == "goias":
            selecionar_municipio(None)
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
            "codigo": codigo,
            "foco": municipio is not None,
            "brasao": brasao,
            "total_estado": sum(contagens.values()),
            "semana": referencia.date().isoformat(),
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


def resumo_estado(semana, seguinte):
    total = inteiro(len(semana))
    previstos = inteiro(int(semana[COLUNA_PREVISTA].sum()))
    observados = inteiro(int(semana[ALVO].sum()))
    st.html(f"""
        <div class="dengue-outcome estadual">
          <div class="dengue-outcome-title">
            <div class="dengue-outcome-periodo">
              <small>Semana seguinte</small>
              <strong>{periodo_semana(seguinte)}</strong>
            </div>
            <span class="dengue-outcome-status">{total} municípios avaliados</span>
          </div>
          <div class="dengue-comparison">
            <div><small>Municípios com sinal de aumento</small><strong>{previstos}</strong></div>
            <div><small>Municípios com aumento observado</small><strong>{observados}</strong></div>
          </div>
        </div>
    """)
    atual = int(semana[COLUNA_CONTAGEM].sum())
    contagens = semana[COLUNA_SEGUINTE]
    futura = inteiro(int(contagens.sum())) if contagens.notna().all() else "—"
    st.metric("Notificações em Goiás · semana analisada → semana seguinte", f"{inteiro(atual)} → {futura}")
    if futura == "—":
        st.caption("O total da semana seguinte exige a contagem de todos os municípios avaliados.")


def explorar(painel):
    municipio = st.session_state.get("municipio")
    if municipio not in painel.municipios:
        municipio = None
    semanas = painel.semanas(municipio)
    referencia = st.session_state.get("semana")
    if referencia not in semanas:
        referencia = SEMANA_EXEMPLO if SEMANA_EXEMPLO in semanas else semanas[-1]
    st.session_state["semana"] = referencia

    barra_lateral(painel, municipio)
    caso = painel.consultar(municipio, referencia) if municipio is not None else None
    seguinte = referencia + pd.Timedelta(weeks=1)
    semana = painel.teste.loc[painel.teste[COLUNA_SEMANA].eq(referencia)]
    mapa, detalhes = st.columns((1.35, 1), gap="small", border=True)
    with mapa:
        st.subheader("Mapa de Goiás")
        renderizar_mapa(painel, semana, municipio, referencia, semanas)

    with detalhes:
        if caso is None:
            st.subheader("Resumo estadual")
            st.markdown(f"**Goiás inteiro** · {periodo_semana(referencia)}")
            resumo_estado(semana, seguinte)
        else:
            st.subheader("Previsão e observação")
            st.markdown(f"**{nome_municipio(municipio)}** · {periodo_semana(referencia)}")
            resultado(caso)
        st.subheader("Notificações ao longo do tempo")
        st.altair_chart(
            grafico_historico(painel, municipio, referencia, seguinte), width="stretch", theme=None,
            alt="Evolução semanal de notificações no território selecionado",
        )
        st.html("""
            <div class="dengue-legend"><span class="legenda-historico"><i></i>Histórico</span><span class="legenda-referencia"><i></i>Referência</span><span class="legenda-observada"><i></i>Observada após a previsão</span></div>
        """)
        if caso is not None:
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
        st.subheader("Classes observadas em Goiás")
        st.altair_chart(grafico_classes(semana), width="stretch", theme=None, alt="Distribuição das classes observadas nos municípios da semana")
        st.html("""
            <div class="dengue-legend"><span class="legenda-historico"><i></i>Sem aumento</span><span class="legenda-aumento"><i></i>Com aumento</span></div>
        """)
    with sinais:
        if caso is None:
            comparacao_estado(semana, seguinte)
        else:
            comparacao_municipio(caso)

def avaliar(painel):
    matriz = painel.matriz
    metricas = painel.metricas
    config = painel.configuracao
    registros_teste = len(painel.teste)
    aumentos = matriz["vp"] + matriz["fn"]
    sinais = matriz["vp"] + matriz["fp"]

    st.subheader("Por que o seletor mostra 2025?")
    st.markdown(
        "A base cobre **2019 a 2025**. O seletor abre as semanas reservadas para testar a árvore "
        "depois do treino e da escolha da configuração."
    )
    st.html(f"""
        <ol class="dengue-periodos" aria-label="Etapas da avaliação cronológica">
          <li>
            <span class="dengue-periodo-anos">2019–2023</span><strong>Treino</strong>
            <p>A árvore aprende com o histórico.</p><small>{inteiro(painel.registros_treino)} registros</small>
          </li>
          <li>
            <span class="dengue-periodo-anos">2024</span><strong>Validação</strong>
            <p>Comparamos configurações e escolhemos a árvore.</p><small>{inteiro(painel.registros_validacao)} registros</small>
          </li>
          <li class="dengue-periodo-teste">
            <span class="dengue-periodo-anos">2025</span><strong>Teste</strong>
            <p>Conferimos as previsões com o que ocorreu.</p>
            <small>{inteiro(registros_teste)} registros em {inteiro(len(painel.semanas(None)))} semanas</small>
          </li>
        </ol>
    """)
    st.caption("A separação em ordem cronológica segue o exemplo do dicionário de dados da disciplina.")

    origem, alvo = st.columns(2, gap="small", border=True)
    with origem:
        st.subheader("De onde vêm os dados")
        st.markdown(
            "Os registros originais vêm da **Secretaria de Estado da Saúde de Goiás**. "
            "O painel lê o CSV didático, que já vem com as notificações agrupadas pela data da notificação."
        )
        st.markdown(
            f"O CSV tem **{inteiro(painel.registros_csv)} registros**. Cada linha reúne **um município e uma "
            "semana civil**, de segunda a domingo. Uma contagem zero representa uma semana sem registro no arquivo."
        )
        st.caption("[Fonte original · Dados Abertos Goiás](https://dadosabertos.go.gov.br/pt_BR/dataset/dengue)")
    with alvo:
        st.subheader("O que a árvore prevê")
        st.markdown(
            "Com o histórico disponível até a **semana analisada**, a árvore decide se deve **sinalizar um "
            "aumento relevante na semana seguinte**."
        )
        st.html("""
            <div class="dengue-criterio" aria-label="Critério didático de aumento relevante">
              <div><strong>+3 notificações</strong><span>no mínimo</span></div>
              <b>e</b>
              <div><strong>25% ou mais</strong><span>de crescimento</span></div>
            </div>
        """)
        st.caption("De 4 para 7 notificações, são 3 a mais e 75% de crescimento. Esse exemplo atende aos dois critérios.")

    st.subheader("Como ler o desempenho no teste")
    st.caption(f"Em {inteiro(registros_teste)} registros de município e semana, {inteiro(aumentos)} tiveram aumento relevante observado.")
    st.html(f"""
        <section class="dengue-metrics dengue-avaliacao-metricas" aria-label="O que significam as métricas no teste">
          <article><p>Recall · aumentos detectados</p><strong>{percentual(metricas["recall"])}</strong>
            <small>A árvore detectou {inteiro(matriz["vp"])} dos {inteiro(aumentos)} aumentos observados.</small></article>
          <article><p>Precisão · sinais corretos</p><strong>{percentual(metricas["precisao"])}</strong>
            <small>Em {inteiro(sinais)} sinalizações, {inteiro(matriz["vp"])} tiveram aumento observado.</small></article>
          <article><p>F1 · equilíbrio</p><strong>{percentual(metricas["f1"])}</strong>
            <small>Combina precisão e recall. Cai quando uma dessas medidas é baixa.</small></article>
          <article><p>Acurácia · acertos totais</p><strong>{percentual(metricas["acuracia"])}</strong>
            <small>{inteiro(matriz["vn"] + matriz["vp"])} acertos em {inteiro(registros_teste)} registros, com e sem aumento.</small></article>
        </section>
    """)

    esquerda, direita = st.columns((1.2, 1), gap="small", border=True)
    with esquerda:
        st.subheader("Matriz de confusão")
        st.caption("As linhas mostram o que ocorreu. As colunas mostram o que a árvore previu.")
        st.html(f"""
            <table class="dengue-matrix">
              <thead><tr><th scope="col">Resultado observado</th><th scope="col">Sem sinal</th><th scope="col">Com sinal</th></tr></thead>
              <tbody>
                <tr><th scope="row">Sem aumento relevante</th><td class="correto"><strong>{inteiro(matriz["vn"])}</strong><small>Acertos sem aumento</small></td><td class="incorreto"><strong>{inteiro(matriz["fp"])}</strong><small>Falsos positivos</small></td></tr>
                <tr><th scope="row">Com aumento relevante</th><td class="incorreto"><strong>{inteiro(matriz["fn"])}</strong><small>Falsos negativos</small></td><td class="correto"><strong>{inteiro(matriz["vp"])}</strong><small>Aumentos detectados</small></td></tr>
              </tbody>
            </table>
        """)
    with direita:
        st.subheader("O que significam os erros")
        st.markdown(
            f"**{inteiro(matriz['fn'])} falsos negativos.** Houve aumento relevante, e a árvore deixou a semana sem sinal. "
            "Em uma triagem baseada nesses sinais, esses aumentos poderiam passar despercebidos."
        )
        st.markdown(
            f"**{inteiro(matriz['fp'])} falsos positivos.** A árvore sinalizou semanas que ficaram sem aumento relevante. "
            "Isso aumenta o volume de situações para revisar."
        )
        st.caption("O painel é uma demonstração acadêmica. Os sinais servem para praticar a revisão de notificações históricas.")

    with st.expander("Como o CSV foi preparado"):
        st.markdown(
            "- A preparação didática reuniu notificações entre 2019 e 2025 por município e semana civil. "
            "Preencheu semanas sem registro com zero e retirou as semanas nas pontas sem histórico suficiente "
            "ou sem uma semana posterior observada.\n"
            "- O painel retira o código 520000, reservado para município ignorado, e ordena os dados no tempo. Na passagem entre "
            "treino, validação e teste, ficam de fora as linhas cuja semana-alvo atravessa a divisão.\n"
            "- O aumento registrado na semana seguinte serve para conferir a previsão. Quando a semana analisada "
            "tem zero notificações, a taxa didática de crescimento usa 1 como denominador mínimo."
        )
    with st.expander("Entradas e configuração da árvore"):
        st.markdown(
            "A árvore compara cada entrada com um limite aprendido no treino. Ela segue uma sequência de perguntas "
            "até indicar **sem aumento relevante** ou **aumento relevante**."
        )
        st.markdown("\n".join(f"- {ATRIBUTOS[entrada]}" for entrada in painel.entradas))
        st.caption(
            f"Na validação, comparamos {config['total_configuracoes']} configurações pelo F1. "
            f"A selecionada alcançou {percentual(config['f1_validacao'])}, com profundidade máxima de "
            f"{config['profundidade']}, mínimo de {config['minimo_por_folha']} registros por folha e {config['pesos']}."
        )
        st.markdown(
            "Em **Explorar município**, abra **Ver o caminho da árvore** para conferir quais condições "
            "foram usadas na previsão da cidade e da semana selecionadas."
        )
    with st.expander("Como o mapa e os gráficos são calculados"):
        st.markdown(
            "- **Mapa.** A cor representa a contagem de notificações na semana analisada. O código IBGE "
            "liga cada contagem ao contorno do município.\n"
            "- **Histórico.** Cada barra corresponde a uma semana. Na visão Goiás inteiro, a barra soma "
            "as notificações dos municípios naquela semana.\n"
            "- **Comparação.** Para um município, são duas contagens de notificações, da semana analisada e "
            "da seguinte. Para Goiás inteiro, as barras contam municípios sinalizados e municípios com aumento observado."
        )


def main():
    st.set_page_config(page_title="Monitoramento de dengue em Goiás", layout="wide")
    st.html(INTERFACE / "tailwind.css")
    st.html(RAIZ / "painel.css")
    topo = st.empty()
    topo.html(INTERFACE / "indicadores.html")
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

    with topo.container():
        cabecalho(painel)
    municipio, avaliacao = st.tabs(["Explorar município", "Avaliação do modelo"])
    with municipio:
        explorar(painel)
    with avaliacao:
        avaliar(painel)
    st.html('<footer class="dengue-source">Fontes · Base didática 01_saude_dengue.csv · Malha municipal: IBGE</footer>')


if __name__ == "__main__":
    main()
