# Monitoramento de notificações de dengue em Goiás

Projeto 1 do Projeto Integrador de Inteligência Artificial do curso de Sistemas de Informação da Universidade Estadual de Goiás, Unidade Universitária de Trindade.

O protótipo de terminal reproduz o experimento do relatório entregue na disciplina. Ele testa se uma **árvore de decisão** consegue sinalizar aumentos relevantes de notificações na semana seguinte, usando as contagens conhecidas até o fechamento da semana de referência. Cada observação representa um município e uma semana civil.

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
