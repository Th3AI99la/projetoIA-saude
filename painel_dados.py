"""Dados e resultados da avaliação retrospectiva para a interface do protótipo."""

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from sklearn.metrics import confusion_matrix
from sklearn.tree import DecisionTreeClassifier

from dengue_prototipo import (
    ALVO,
    CODIGO_IGNORADO,
    carregar_dados,
    metricas,
    normalizar,
    preparar,
    selecionar_arvore,
    separar_periodos,
)


COLUNA_MUNICIPIO = "municipio"
COLUNA_SEMANA = "semana_inicio"
COLUNA_CONTAGEM = "notificacoes_semana_atual"
COLUNA_SEGUINTE = "notificacoes_semana_seguinte"
COLUNA_PREVISTA = "classe_prevista"


@dataclass(frozen=True)
class Regra:
    entrada: str
    valor: float
    operador: str
    limite: float


@dataclass(frozen=True)
class Caso:
    municipio: str
    semana_referencia: pd.Timestamp
    semana_seguinte: pd.Timestamp
    notificacoes_semana_atual: int
    notificacoes_semana_seguinte: int | None
    classe_prevista: int
    classe_observada: int
    regras: list[Regra]


@dataclass
class Painel:
    historico: pd.DataFrame
    teste: pd.DataFrame
    municipios: tuple[str, ...]
    metricas: dict[str, float]
    matriz: dict[str, int]
    configuracao: dict[str, int | float | str]
    _arvore: DecisionTreeClassifier
    _entradas: list[str]

    def semanas(self, municipio: str) -> tuple[pd.Timestamp, ...]:
        """Retorna as semanas com avaliação disponível para o município."""
        escolha = self.teste[COLUNA_MUNICIPIO].eq(municipio)
        return tuple(self.teste.loc[escolha, COLUNA_SEMANA].sort_values())

    def consultar(self, municipio: str, semana: pd.Timestamp) -> Caso:
        """Explica uma previsão do teste e retorna as observações disponíveis."""
        semana = pd.Timestamp(semana)
        escolha = self.teste[COLUNA_MUNICIPIO].eq(municipio) & self.teste[COLUNA_SEMANA].eq(semana)
        selecionado = self.teste.loc[escolha]
        if selecionado.empty:
            raise ValueError("Município e semana não encontrados no período de teste.")
        linha = selecionado.iloc[0]
        seguinte = linha[COLUNA_SEGUINTE]
        modelo = self._arvore.tree_
        regras = []
        for no in self._arvore.decision_path(selecionado[self._entradas]).indices:
            atributo = modelo.feature[no]
            if atributo < 0:
                continue
            entrada = self._entradas[atributo]
            valor = float(linha[entrada])
            limite = float(modelo.threshold[no])
            regras.append(Regra(entrada, valor, "≤" if valor <= limite else ">", limite))
        return Caso(
            municipio=municipio,
            semana_referencia=semana,
            semana_seguinte=semana + pd.Timedelta(days=7),
            notificacoes_semana_atual=int(linha[COLUNA_CONTAGEM]),
            notificacoes_semana_seguinte=int(seguinte) if pd.notna(seguinte) else None,
            classe_prevista=int(linha[COLUNA_PREVISTA]),
            classe_observada=int(linha[ALVO]),
            regras=regras,
        )


def carregar_painel(caminho: Path) -> Painel:
    """Treina a árvore com o protocolo publicado e prepara apenas o teste para consulta."""
    base = carregar_dados(Path(caminho))
    historico = base.loc[base["codigo_municipio"].ne(CODIGO_IGNORADO)]
    treino, validacao, teste = separar_periodos(preparar(base), verbose=False).values()
    arvore, entradas, grade = selecionar_arvore(treino, validacao, verbose=False)
    observadas = teste[ALVO]
    previstas = arvore.predict(teste[entradas])
    vn, fp, fn, vp = confusion_matrix(observadas, previstas, labels=[0, 1]).ravel()

    # A semana seguinte só é consultada depois da previsão, para exibir o resultado.
    por_municipio = historico.groupby("codigo_municipio", sort=False)
    datas_seguinte = por_municipio[COLUNA_SEMANA].shift(-1)
    consecutivas = datas_seguinte.sub(historico[COLUNA_SEMANA]).eq(pd.Timedelta(days=7))
    contagens_seguinte = por_municipio[COLUNA_CONTAGEM].shift(-1).where(consecutivas)
    teste = teste.assign(
        **{COLUNA_PREVISTA: previstas, COLUNA_SEGUINTE: contagens_seguinte.reindex(teste.index)}
    )
    return Painel(
        historico=historico,
        teste=teste,
        municipios=tuple(sorted(teste[COLUNA_MUNICIPIO].unique(), key=normalizar)),
        metricas=metricas(observadas, previstas),
        matriz={"vn": int(vn), "fp": int(fp), "fn": int(fn), "vp": int(vp)},
        configuracao={
            "entradas": len(entradas),
            "profundidade": arvore.max_depth,
            "minimo_por_folha": arvore.min_samples_leaf,
            "folhas": int(arvore.get_n_leaves()),
            "f1_validacao": float(grade["f1"].max()),
            "total_configuracoes": len(grade),
            "pesos": "pesos balanceados" if arvore.class_weight == "balanced" else "pesos padrão",
        },
        _arvore=arvore,
        _entradas=entradas,
    )
