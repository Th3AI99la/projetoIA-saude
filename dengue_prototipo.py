"""
Protótipo experimental — Projeto Integrador de IA (UEG, Câmpus Trindade)
Monitoramento de notificações de dengue em Goiás (Projeto 1).

Reproduz o experimento descrito no relatório final do grupo:
  1. prepara os dados (retira o código 520000, calcula soma, diferença e razão);
  2. separa por ano civil da semana de referência (2019–2023 / 2024 / 2025),
     retirando as linhas cuja semana-alvo termina no período seguinte;
  3. treina as 48 configurações da árvore de decisão e escolhe a melhor pelo F1
     da classe 1 na validação (2024);
  4. ajusta a regressão logística de referência (6 entradas padronizadas,
     pesos balanceados);
  5. avalia árvore, regressão logística e regras simples no teste (2025);
  6. mostra a matriz de confusão, o recall por trimestre e por volume e o
     caminho de decisão de municípios escolhidos.

Uso:
    python dengue_prototipo.py
    python dengue_prototipo.py --dados caminho/01_saude_dengue.csv
    python dengue_prototipo.py --dados caminho/01_saude_dengue.csv --municipio "GOIANIA"
"""

from __future__ import annotations

import argparse
import itertools
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier, export_text

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
RANDOM_STATE = 42
ALVO = "aumento_semana_seguinte"
CODIGO_IGNORADO = "520000"
CSV_PADRAO = Path(__file__).resolve().parent / "dados" / "01_saude_dengue.csv"

# Seis entradas: contagem atual, as quatro contagens anteriores e a semana ISO.
ENTRADAS_6 = [
    "notificacoes_semana_atual",
    "notificacoes_semana_menos_1",
    "notificacoes_semana_menos_2",
    "notificacoes_semana_menos_3",
    "notificacoes_semana_menos_4",
    "semana_ano",
]
# Nove entradas: as seis anteriores + soma de 4 semanas, diferença e razão.
ENTRADAS_9 = ENTRADAS_6 + [
    "notificacoes_ultimas_4_semanas",
    "diferenca_semanal",
    "razao_media_anterior",
]
CONJUNTOS = {"6 entradas": ENTRADAS_6, "9 entradas": ENTRADAS_9}

GRADE_PROFUNDIDADE = [3, 5, 8]
GRADE_MIN_FOLHA = [20, 50, 200, 500]
GRADE_PESOS = [None, "balanced"]


# ---------------------------------------------------------------------------
# 1. Preparação dos dados
# ---------------------------------------------------------------------------
def carregar_dados(caminho: Path) -> pd.DataFrame:
    if caminho.suffix.lower() != ".csv":
        raise ValueError("Use a base semanal em formato CSV.")
    if not caminho.is_file():
        raise FileNotFoundError(
            f"Base não encontrada em '{caminho}'. Informe o arquivo semanal fornecido "
            "na disciplina usando --dados com o caminho do CSV."
        )
    df = pd.read_csv(caminho, dtype={"codigo_municipio": "string"}, encoding="utf-8-sig")
    campos = [
        "codigo_municipio", "municipio", "semana_inicio", ALVO,
        *ENTRADAS_6, "notificacoes_ultimas_4_semanas",
    ]
    faltantes = [campo for campo in campos if campo not in df]
    if faltantes:
        raise ValueError("Colunas ausentes na base semanal: " + ", ".join(faltantes))
    df["semana_inicio"] = pd.to_datetime(df["semana_inicio"], errors="raise")
    if df[campos].isna().any().any() or df.duplicated(["codigo_municipio", "semana_inicio"]).any():
        raise ValueError("A base tem campos vazios ou pares de município e semana duplicados.")
    if set(df[ALVO]) != {0, 1}:
        raise ValueError("A variável-alvo deve conter as classes 0 e 1.")
    return df.sort_values(["codigo_municipio", "semana_inicio"]).reset_index(drop=True)


def conferir_rotulo(df: pd.DataFrame) -> tuple[int, int]:
    """Reconstrói o rótulo a partir da linha seguinte de cada código (seção 3.2)."""
    seguinte = df.groupby("codigo_municipio")["notificacoes_semana_atual"].shift(-1)
    consecutiva = (
        df.groupby("codigo_municipio")["semana_inicio"].shift(-1) - df["semana_inicio"]
    ) == pd.Timedelta(days=7)
    atual = df["notificacoes_semana_atual"]
    diferenca = seguinte - atual
    rotulo = ((diferenca >= 3) & (diferenca / atual.clip(lower=1) >= 0.25)).astype(int)
    conferidas = consecutiva & seguinte.notna()
    divergencias = int((rotulo[conferidas] != df.loc[conferidas, ALVO]).sum())
    return int(conferidas.sum()), divergencias


def preparar(df: pd.DataFrame) -> pd.DataFrame:
    """Retira o código ignorado e calcula diferença e razão (Quadro 3)."""
    d = df[df["codigo_municipio"] != CODIGO_IGNORADO].copy()
    d["diferenca_semanal"] = d["notificacoes_semana_atual"] - d["notificacoes_semana_menos_1"]
    media_anterior = d[
        [f"notificacoes_semana_menos_{i}" for i in range(1, 5)]
    ].mean(axis=1)
    d["razao_media_anterior"] = d["notificacoes_semana_atual"] / (media_anterior + 1)
    return d


def _periodo(ano: pd.Series) -> pd.Series:
    """Treino = 2019 a 2023; validação = 2024; teste = 2025 (2026 = fora da base)."""
    return ano.clip(lower=2023)


def separar_periodos(d: pd.DataFrame, *, verbose: bool = True) -> dict[str, pd.DataFrame]:
    """Divisão por ano civil de semana_inicio, sem linhas que cruzam entre períodos.

    A semana-alvo (t + 1) termina 13 dias depois de semana_inicio. Linhas em que
    esse fim cai no período seguinte (2023->2024 ou 2024->2025) usam dados do
    período posterior e são removidas.
    """
    ano_civil = d["semana_inicio"].dt.year
    fim_semana_alvo = d["semana_inicio"] + pd.Timedelta(days=13)
    cruza_periodo = _periodo(fim_semana_alvo.dt.year) != _periodo(ano_civil)

    if verbose:
        print("\n== Separação cronológica (seção 7.1) ==")
        print(f"Linhas com municípios identificados: {len(d):,}".replace(",", "."))
        removidas = d[cruza_periodo]
        for data, n in removidas.groupby("semana_inicio").size().items():
            print(f"  retiradas {n} linhas da semana iniciada em {data:%d/%m/%Y}")
        print(f"  total retirado: {len(removidas)}")

    d = d[~cruza_periodo]
    ano_civil = ano_civil[~cruza_periodo]
    periodos = {
        "Treino (2019 a 2023)": d[ano_civil <= 2023],
        "Validação (2024)": d[ano_civil == 2024],
        "Teste (2025)": d[ano_civil == 2025],
    }
    if any(p[ALVO].nunique() < 2 for p in periodos.values()):
        raise ValueError("Treino, validação e teste precisam conter as duas classes. Use a base completa do projeto.")
    if verbose:
        print(f"Linhas restantes: {len(d):,}".replace(",", "."))
        for nome, p in periodos.items():
            pos = int(p[ALVO].sum())
            print(f"  {nome:22s} {len(p):>6} linhas | classe 1: {pos} ({pct(pos / len(p))})")
    return periodos


# ---------------------------------------------------------------------------
# 2. Métricas
# ---------------------------------------------------------------------------
def metricas(y_true, y_pred) -> dict[str, float]:
    return {
        "precisao": precision_score(y_true, y_pred, zero_division=np.nan),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1": f1_score(y_true, y_pred, zero_division=0),
        "acuracia": accuracy_score(y_true, y_pred),
    }


def pct(x: float) -> str:
    return "—" if pd.isna(x) else f"{100 * x:.2f}%".replace(".", ",")


# ---------------------------------------------------------------------------
# 3. Árvore de decisão: grade de 48 configurações
# ---------------------------------------------------------------------------
def selecionar_arvore(treino, validacao, *, verbose: bool = True):
    if verbose:
        print("\n== Grade da árvore de decisão na validação (seção 5) ==")
    linhas = []
    for (nome_conj, cols), prof, folha, peso in itertools.product(
        CONJUNTOS.items(), GRADE_PROFUNDIDADE, GRADE_MIN_FOLHA, GRADE_PESOS
    ):
        arv = DecisionTreeClassifier(
            max_depth=prof,
            min_samples_leaf=folha,
            class_weight=peso,
            random_state=RANDOM_STATE,
        ).fit(treino[cols], treino[ALVO])
        m = metricas(validacao[ALVO], arv.predict(validacao[cols]))
        linhas.append(
            {
                "conjunto": nome_conj,
                "max_depth": prof,
                "min_samples_leaf": folha,
                "class_weight": peso or "padrão",
                "folhas": arv.get_n_leaves(),
                **m,
            }
        )
    grade = pd.DataFrame(linhas)
    if verbose:
        print(f"Configurações avaliadas: {len(grade)}")
        for conj in CONJUNTOS:
            melhor = grade[grade["conjunto"] == conj]["f1"].max()
            print(f"  maior F1 com {conj}: {pct(melhor)}")
        print("Cinco melhores configurações:")
        top = grade.sort_values("f1", ascending=False).head(5)
        print(
            top[["conjunto", "max_depth", "min_samples_leaf", "class_weight", "folhas", "f1"]]
            .to_string(index=False, formatters={"f1": pct})
        )

    escolhida = grade.loc[grade["f1"].idxmax()]
    cols = CONJUNTOS[escolhida["conjunto"]]
    peso = None if escolhida["class_weight"] == "padrão" else escolhida["class_weight"]
    arvore = DecisionTreeClassifier(
        max_depth=int(escolhida["max_depth"]),
        min_samples_leaf=int(escolhida["min_samples_leaf"]),
        class_weight=peso,
        random_state=RANDOM_STATE,
    ).fit(treino[cols], treino[ALVO])
    if verbose:
        print(
            f"Escolhida: {escolhida['conjunto']}, profundidade {arvore.max_depth}, "
            f"mínimo {arvore.min_samples_leaf} por folha, pesos {escolhida['class_weight']}, "
            f"{arvore.get_n_leaves()} folhas, F1 de validação {pct(escolhida['f1'])}"
        )
    return arvore, cols, grade


def resumir_topo(arvore, cols, treino):
    """Proporções de aumento no treino nos dois primeiros níveis (Figura 3)."""
    print("\n== Dois primeiros níveis da árvore (Figura 3) ==")
    t = arvore.tree_
    caminho = arvore.decision_path(treino[cols])
    y = treino[ALVO].to_numpy()

    def descrever(no, prefixo):
        idx = caminho[:, no].toarray().ravel().astype(bool)
        print(f"{prefixo}nó {no}: {idx.sum()} registros, aumento {pct(y[idx].mean())}")

    raiz = 0
    print(f"Raiz: {cols[t.feature[raiz]]} <= {t.threshold[raiz]:.1f}")
    descrever(raiz, "  ")
    for lado, filho in (("sim", t.children_left[raiz]), ("não", t.children_right[raiz])):
        descrever(filho, f"  [{lado}] ")
        if t.feature[filho] >= 0:
            print(f"       pergunta seguinte: {cols[t.feature[filho]]} <= {t.threshold[filho]:.1f}")
            for lado2, neto in (("sim", t.children_left[filho]), ("não", t.children_right[filho])):
                descrever(neto, f"       [{lado2}] ")


# ---------------------------------------------------------------------------
# 4. Regressão logística de referência
# ---------------------------------------------------------------------------
def ajustar_logistica(cols, peso, treino):
    modelo = make_pipeline(
        StandardScaler(),  # média e desvio calculados só no treino
        LogisticRegression(class_weight=peso, max_iter=1000, random_state=RANDOM_STATE),
    )
    return modelo.fit(treino[cols], treino[ALVO])


def selecionar_logistica(treino, validacao):
    print("\n== Regressão logística na validação (seção 4.4) ==")
    resultados = {}
    for nome_conj, cols in CONJUNTOS.items():
        for peso in GRADE_PESOS:
            modelo = ajustar_logistica(cols, peso, treino)
            f1 = f1_score(validacao[ALVO], modelo.predict(validacao[cols]))
            resultados[(nome_conj, peso)] = f1
            print(f"  {nome_conj}, pesos {peso or 'padrão':9s}: F1 {pct(f1)}")
    # Referência do relatório: 6 entradas padronizadas, pesos balanceados.
    return ajustar_logistica(ENTRADAS_6, "balanced", treino), ENTRADAS_6


# ---------------------------------------------------------------------------
# 5. Avaliação no teste
# ---------------------------------------------------------------------------
def avaliar_teste(teste, arvore, cols_arv, logistica, cols_log):
    y = teste[ALVO]
    atual = teste["notificacoes_semana_atual"]
    previsoes = {
        "Árvore de decisão": arvore.predict(teste[cols_arv]),
        "Regressão logística": logistica.predict(teste[cols_log]),
        "Semana atual >= 3 notificações": (atual >= 3).astype(int),
        "Semana atual >= 3 e semana ISO <= 17": ((atual >= 3) & (teste["semana_ano"] <= 17)).astype(int),
        "Sempre classe 0": np.zeros(len(teste), dtype=int),
    }
    print(f"\n== Comparação nas {len(teste)} observações do teste (Tabela 2) ==")
    tabela = pd.DataFrame({nome: metricas(y, p) for nome, p in previsoes.items()}).T
    tabela.columns = ["Precisão", "Recall", "F1", "Acurácia"]
    print(tabela.map(pct).to_string())
    print("  (precisão indefinida quando nenhuma previsão é positiva)")

    pred = previsoes["Árvore de decisão"]
    tn, fp, fn, tp = confusion_matrix(y, pred).ravel()
    print("\n== Matriz de confusão da árvore no teste (Tabela 3) ==")
    print(f"  observada 1: {tp} verdadeiros positivos | {fn} falsos negativos")
    print(f"  observada 0: {fp} falsos positivos     | {tn} verdadeiros negativos")
    print(f"  sinalizações: {tp + fp}")
    regra3 = previsoes["Semana atual >= 3 notificações"]
    tp3 = int(((regra3 == 1) & (y == 1)).sum())
    fp3 = int(((regra3 == 1) & (y == 0)).sum())
    print(
        f"  em relação à regra de 3 notificações: {tp - tp3:+d} aumentos detectados, "
        f"{fp - fp3:+d} falsos positivos"
    )
    escore = arvore.predict_proba(teste[cols_arv])[:, 1]
    print(
        f"  precisão média (average precision): {pct(average_precision_score(y, escore))}"
        f" | prevalência da classe 1: {pct(y.mean())}"
    )
    return pred, escore


def recall_por_recorte(teste, treino, pred):
    print("\n== Detecção por trimestre e por volume histórico (Tabela 4) ==")
    t = teste.assign(previsto=pred)
    t["trimestre"] = t["semana_inicio"].dt.quarter

    media = treino.groupby("codigo_municipio")["notificacoes_semana_atual"].mean()
    mediana = media.median()
    t["grupo_volume"] = np.where(
        t["codigo_municipio"].map(media) <= mediana,
        "Municípios até a mediana de volume",
        "Municípios acima da mediana de volume",
    )

    def linha(nome, g):
        aum = int(g[ALVO].sum())
        fn = int(((g[ALVO] == 1) & (g["previsto"] == 0)).sum())
        print(f"  {nome:40s} aumentos {aum:>5} | FN {fn:>4} | recall {pct((aum - fn) / aum)}")

    for q, g in t.groupby("trimestre"):
        linha(f"{q}º trimestre de referência", g)
    for nome in ["Municípios até a mediana de volume", "Municípios acima da mediana de volume"]:
        linha(nome, t[t["grupo_volume"] == nome])
    print(f"  mediana da média semanal por município no treino: {mediana:.2f}".replace(".", ","))


# ---------------------------------------------------------------------------
# 6. Explicação de um caso
# ---------------------------------------------------------------------------
def normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return sem_acento.upper().strip()


def explicar_caso(arvore, cols, linha: pd.Series):
    t = arvore.tree_
    x = linha[cols].to_numpy(dtype=float).reshape(1, -1)
    x_df = pd.DataFrame(x, columns=cols)
    nos = arvore.decision_path(x_df).indices
    folha = arvore.apply(x_df)[0]
    print(
        f"\n-- {linha['municipio']} | semana iniciada em {linha['semana_inicio']:%d/%m/%Y} "
        f"(semana ISO {linha['semana_ano']}) --"
    )
    for c in cols:
        v = linha[c]
        print(f"   {c:32s} = {v:.3f}" if isinstance(v, float) else f"   {c:32s} = {v}")
    print("   Caminho:")
    for no in nos:
        if no == folha:
            continue
        f, lim = t.feature[no], t.threshold[no]
        valor = x[0, f]
        sinal = "<=" if valor <= lim else ">"
        print(f"     {cols[f]} = {valor:g} {sinal} {lim:.3f}")
    escore = arvore.predict_proba(x_df)[0, 1]
    print(
        f"   Folha {folha}: classe prevista {arvore.predict(x_df)[0]} (escore {escore:.3f})"
        f" | classe observada {linha[ALVO]}"
    )


def exemplos_relatorio(teste, arvore, cols, pred):
    """Procura no teste os dois exemplos da Tabela 5."""
    print("\n== Dois exemplos do teste (Tabela 5) ==")
    t = teste.assign(previsto=pred).sort_values(["codigo_municipio", "semana_inicio"])
    t["seguinte"] = t.groupby("codigo_municipio")["notificacoes_semana_atual"].shift(-1)
    criterios = [
        # Abadia de Goiás: 1 -> 4, soma de 4 semanas 11, previsto 1, observado 1
        (
            "ABADIA DE GOIAS",
            dict(
                notificacoes_semana_atual=1,
                seguinte=4,
                notificacoes_ultimas_4_semanas=11,
                previsto=1,
            ),
        ),
        # Aparecida do Rio Doce: 0 -> 3, soma 1, semana ISO 2, previsto 0, observado 1
        (
            "APARECIDA DO RIO DOCE",
            dict(
                notificacoes_semana_atual=0,
                seguinte=3,
                notificacoes_ultimas_4_semanas=1,
                semana_ano=2,
                previsto=0,
            ),
        ),
    ]
    for nome, filtros in criterios:
        sel = t[t["municipio"].map(normalizar) == nome]
        for col, v in filtros.items():
            sel = sel[sel[col] == v]
        if sel.empty:
            print(f"  Exemplo de {nome} não encontrado com os critérios do relatório.")
            continue
        if len(sel) > 1:
            print(f"  {nome}: {len(sel)} semanas atendem aos critérios; mostrando a primeira.")
        explicar_caso(arvore, cols, sel.iloc[0])


def caso_escolhido(dados, arvore, cols, municipio: str, semana: str | None):
    sel = dados[dados["municipio"].map(normalizar) == normalizar(municipio)]
    if sel.empty:
        print(f"\nMunicípio '{municipio}' não encontrado.")
        return
    if semana:
        sel = sel[sel["semana_inicio"] == pd.Timestamp(semana)]
        if sel.empty:
            print(f"\nSemana {semana} não encontrada para {municipio}.")
            return
    explicar_caso(arvore, cols, sel.iloc[-1])


# ---------------------------------------------------------------------------
# Programa principal
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Protótipo do Projeto 1 (dengue em Goiás)")
    parser.add_argument(
        "--dados",
        "--csv",
        dest="dados",
        type=Path,
        default=CSV_PADRAO,
        help="caminho do CSV semanal (padrão: dados/01_saude_dengue.csv)",
    )
    parser.add_argument("--municipio", help="nome do município para mostrar o caminho de decisão")
    parser.add_argument("--semana", help="segunda-feira da semana (AAAA-MM-DD); padrão: última do teste")
    parser.add_argument("--regras", action="store_true", help="imprime a árvore inteira em texto")
    args = parser.parse_args()

    if args.semana and not args.municipio:
        parser.error("--semana deve ser usado junto com --municipio")
    if args.semana:
        try:
            args.semana = pd.Timestamp(args.semana)
        except ValueError:
            parser.error("Use uma data válida no formato AAAA-MM-DD para --semana.")
    try:
        df = carregar_dados(args.dados)
    except (OSError, ValueError) as erro:
        parser.error(str(erro))
    print("== Base de dados (seção 3) ==")
    print(
        f"Linhas: {len(df)} | códigos: {df['codigo_municipio'].nunique()} | "
        f"semanas por código: {df.groupby('codigo_municipio').size().unique().tolist()}"
    )
    dist = df[ALVO].value_counts().sort_index()
    for c, n in dist.items():
        print(f"  classe {c}: {n} ({pct(n / len(df))})")
    conferidas, divergencias = conferir_rotulo(df)
    print(f"Rótulos reconstruídos a partir da semana seguinte: {conferidas} (divergências: {divergencias})")

    dados = preparar(df)
    try:
        periodos = separar_periodos(dados)
    except ValueError as erro:
        parser.error(str(erro))
    treino, validacao, teste = periodos.values()

    arvore, cols_arv, _ = selecionar_arvore(treino, validacao)
    resumir_topo(arvore, cols_arv, treino)
    logistica, cols_log = selecionar_logistica(treino, validacao)

    pred, _ = avaliar_teste(teste, arvore, cols_arv, logistica, cols_log)
    recall_por_recorte(teste, treino, pred)
    exemplos_relatorio(teste, arvore, cols_arv, pred)

    if args.municipio:
        print("\n== Caso escolhido ==")
        caso_escolhido(teste, arvore, cols_arv, args.municipio, args.semana)
    if args.regras:
        print("\n== Árvore completa ==")
        print(export_text(arvore, feature_names=cols_arv, show_weights=False))


if __name__ == "__main__":
    main()
