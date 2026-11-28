# Monitoramento de notificações de dengue em Goiás

Projeto 1 do Projeto Integrador de Inteligência Artificial do curso de Sistemas de Informação da Universidade Estadual de Goiás, Unidade Universitária de Trindade.

O protótipo de terminal reproduz o experimento do relatório entregue na disciplina. Ele testa se uma **árvore de decisão** consegue sinalizar aumentos relevantes de notificações na semana seguinte, usando as contagens conhecidas até o fechamento da semana de referência. Cada observação representa um município e uma semana civil.

## Painel interativo local

Escolha o intervalo de segunda a domingo em **Semana analisada**. As setas percorrem as semanas do teste. **Goiás inteiro** mostra a soma das notificações no estado e quantos municípios tiveram sinal de aumento ou aumento observado. Clique em um município no mapa ou digite seu nome em **Buscar município** para ver a previsão, o resultado observado e o histórico local. **Voltar para Goiás** restaura o resumo estadual na mesma semana.

Em **Casos e curiosidades**, os dois exemplos do relatório abrem o acerto em Abadia de Goiás e o falso negativo em Aparecida do Rio Doce. Os demais destaques são calculados no teste entre semanas com contagens comparáveis. Cada botão abre o município e a semana do caso. A tela também apresenta as regras percorridas e a matriz de confusão.

O painel abre em tema escuro e usa a fonte Poppins, servida localmente com a licença em `static/fonts/poppins-OFL.txt`. O mapa mostra as contagens de notificações da semana de referência por faixas fixas e destaca o município selecionado. Os limites municipais vêm de uma malha simplificada do IBGE, incluída em `mapas/goias_municipios.geojson`. A junção usa os seis primeiros dígitos do código municipal do IBGE. [Malha usada no mapa](https://servicodados.ibge.gov.br/api/v3/malhas/estados/52?formato=application%2Fvnd.geo%2Bjson&qualidade=minima&intrarregiao=municipio)

Os brasões municipais aparecem ao lado do nome da cidade quando há um arquivo identificado no catálogo. As imagens locais foram redimensionadas para WebP e vinculadas pelo código do IBGE. O arquivo `static/brasoes/fontes.json` registra a origem, os créditos e as licenças declaradas. O diretório estadual é indicado nos recortes cuja licença individual precisa de conferência antes da redistribuição. Clicar no brasão abre a fonte. [Wikimedia Commons](https://commons.wikimedia.org/wiki/Category:Coats_of_arms_of_municipalities_of_Goi%C3%A1s) · [Diretório oficial de Goiás](https://goias.gov.br/governo/wp-content/uploads/sites/11/2021/01/CADASTRO-DE-AUTORIDADES-26-190.pdf)

A interação de selecionar o município diretamente no mapa segue a referência do painel [Clima em Goiás, do PET-Saúde](https://th3ai99la.github.io/dev_pet_gat1_saude/).

Na raiz da cópia local, coloque o CSV da disciplina em `rafa/01_saude_dengue.csv` ou `dados/01_saude_dengue.csv`. Para outro local, defina a variável `DENGUE_CSV` com o caminho do arquivo. Na primeira instalação, prepare o ambiente em PowerShell com Python 3.13.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\requirements-painel.txt
```

Para iniciar o painel, execute da mesma pasta.

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

Acesse o [painel local](http://127.0.0.1:8501). A primeira abertura treina a árvore e guarda o resultado em memória. Os filtros usam esse resultado para explorar a avaliação.

### Estilos da interface

O painel usa os estilos compilados em `interface/tailwind.css`. Para recompilar após editar os componentes ou `interface/controles.css`, execute na raiz do repositório.

```powershell
npm ci
npm run build:css
```

O Tailwind CSS 4.3.5 está fixado no `package-lock.json`. O Streamlit lê o CSS compilado ao iniciar o painel.

O painel usa a organização de indicadores e gráficos do painel de Valdivino Aquino como referência visual. A implementação consulta os exemplos de gráficos e cache do Streamlit e de caminhos de decisão do scikit-learn. [Dengue em Goiás](https://github.com/valdivinoaquino/dengue_em_goias) · [Exemplo do Streamlit](https://github.com/streamlit/demo-uber-nyc-pickups/blob/main/streamlit_app.py) · [Caminho de decisão](https://scikit-learn.org/stable/auto_examples/tree/plot_unveil_tree_structure.html#decision-path)

## O que está no repositório

| Arquivo | Uso |
| --- | --- |
| `dengue_prototipo.py` | Prepara a base, seleciona a árvore, avalia as abordagens e explica previsões por município. |
| `requirements-prototipo.txt` | Dependências da versão executada com Python 3.13. |
| `resultados_execucao.txt` | Saída de referência gerada com a base didática. |

## Como executar

Use o arquivo `01_saude_dengue.csv` disponibilizado na disciplina. A base contém 88.673 observações agregadas e a coluna `aumento_semana_seguinte`. Coloque o arquivo em uma pasta local `dados/` na raiz desta cópia ou informe seu caminho no argumento `--dados`.

No PowerShell, abra o terminal na pasta do repositório e use Python 3.13:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\requirements-prototipo.txt
.\.venv\Scripts\python.exe .\dengue_prototipo.py --dados ".\dados\01_saude_dengue.csv"
```

Em Linux ou macOS, use `./.venv/bin/python` após criar o ambiente e ajuste os caminhos para barras normais.

O programa imprime os resultados gerais e explica dois casos do teste. Para consultar outra previsão histórica, informe o município e a segunda-feira de referência:

```powershell
.\.venv\Scripts\python.exe .\dengue_prototipo.py --dados ".\dados\01_saude_dengue.csv" --municipio "Goiânia" --semana 2025-03-10
```

A opção `--regras` imprime a árvore em texto. Com `--municipio` sem `--semana`, o programa explica o registro mais recente desse município no recorte de teste.

## Como a avaliação funciona

1. A base define classe 1 quando a semana seguinte tem pelo menos três notificações a mais e um crescimento de pelo menos 25%. O cálculo usa denominador mínimo de 1. A preparação exclui o código de município ignorado (520000).
2. O treino usa as semanas de 2019 a 2023, a validação usa 2024 e o teste retrospectivo usa 2025. Foram retiradas 738 linhas da virada entre períodos, porque a janela usada para determinar o rótulo alcançava o período seguinte.
3. A validação compara 48 configurações de árvore pelo F1 da classe de aumento. A configuração escolhida usa nove entradas, profundidade máxima 8, pelo menos 50 observações por folha e pesos balanceados. Ela alcançou F1 de 41,83% na validação.
4. O mesmo recorte de teste compara a árvore, a regressão logística e as regras simples. A aplicação mostra precisão, recall, F1, acurácia, matriz de confusão e resultados por trimestre e volume histórico.

As nove entradas da árvore são a contagem da semana de referência, as quatro contagens anteriores, o número da semana ISO, a soma das últimas quatro semanas, a diferença para a semana anterior e a razão entre o volume atual e a média das quatro semanas anteriores acrescida de 1. A saída indica a classe prevista e o caminho de regras da árvore permite explicar cada caso.

## Resultado da árvore

| Precisão | Recall | F1 | Aumentos detectados | Aumentos sem sinalização | Sinalizações sem aumento |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 23,36% | 79,43% | 36,10% | 1.255 | 325 | 4.117 |

A árvore detectou 1.255 dos 1.580 aumentos observados no teste. A baixa precisão indica que as sinalizações precisam de revisão. O escore da árvore é uma medida para ordenar sinais e deve ser interpretado com cautela, pois o balanceamento altera as proporções nas folhas. O experimento usa notificações históricas e tem finalidade acadêmica de apoio à revisão de registros.
