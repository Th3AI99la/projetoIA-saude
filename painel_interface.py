"""Componentes da interface e projeção da malha municipal para SVG."""

import json
import math
from pathlib import Path

import streamlit as st


RAIZ = Path(__file__).resolve().parent
INTERFACE = RAIZ / "interface"


def componente(nome):
    return st.components.v2.component(
        f"dengue_{nome}",
        html=(INTERFACE / f"{nome}.html").read_text(encoding="utf-8"),
        js=(INTERFACE / f"{nome}.js").read_text(encoding="utf-8"),
        isolate_styles=False,
    )


def projetar(lon, lat):
    x = (lon + 50) * 100
    y = -(math.degrees(math.asinh(math.tan(math.radians(lat)))) + 16) * 100
    return round(x, 2), round(y, 2)


def limites(pontos):
    xs, ys = zip(*pontos)
    return [min(xs), min(ys), max(xs), max(ys)]


@st.cache_data(show_spinner=False)
def geografia():
    caminho = RAIZ / "mapas" / "goias_municipios.geojson"
    with caminho.open(encoding="utf-8") as arquivo:
        feicoes = json.load(arquivo)["features"]

    formas, todos_os_pontos = [], []
    for feicao in feicoes:
        geometria = feicao["geometry"]
        coordenadas = geometria["coordinates"]
        poligonos = [coordenadas] if geometria["type"] == "Polygon" else coordenadas
        aneis = [[projetar(lon, lat) for lon, lat in anel] for poligono in poligonos for anel in poligono]
        pontos = [ponto for anel in aneis for ponto in anel]
        todos_os_pontos.extend(pontos)
        formas.append({
            "codigo": feicao["properties"]["codarea"][:6],
            "limites": limites(pontos),
            "caminho": "".join("M" + "L".join(f"{x:g},{y:g}" for x, y in anel) + "Z" for anel in aneis),
        })
    return formas, limites(todos_os_pontos)


@st.cache_data(show_spinner=False)
def catalogo_brasoes():
    caminho = RAIZ / "static" / "brasoes" / "fontes.json"
    if not caminho.is_file():
        return {}
    with caminho.open(encoding="utf-8") as arquivo:
        return json.load(arquivo)


busca_municipal = componente("busca")
mapa_goias = componente("mapa")
indicadores = componente("indicadores")
