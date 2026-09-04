import sqlite3

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.statespace.sarimax import SARIMAX

from paths import CAMINHO_BANCO


def carregar_fundamentos():
    conexao = sqlite3.connect(CAMINHO_BANCO)
    df = pd.read_sql_query("SELECT * FROM fundamentos", conexao)
    conexao.close()
    return df


def carregar_cotacoes():
    conexao = sqlite3.connect(CAMINHO_BANCO)
    df = pd.read_sql_query("SELECT * FROM cotacoes", conexao)
    conexao.close()
    return df


def carregar_posicoes():
    conexao = sqlite3.connect(CAMINHO_BANCO)
    df = pd.read_sql_query("SELECT * FROM posicoes", conexao)
    conexao.close()
    return df

CATEGORIAS_FUNDAMENTALISTAS = {
    "valuation": {"earnings_yield": True, "book_to_market": True},
    "rentabilidade": {"roe": True, "roa": True, "roic": True, "margem_liquida": True, "margem_bruta": True, "margem_ebitda": True},
    "crescimento": {"cagr_receita_5a": True, "cagr_lucro_5a": True},
    "seguranca": {"divida_patrimonio": False},
}

PESOS_CATEGORIA = {
    "valuation": 0.25,
    "rentabilidade": 0.25,
    "crescimento": 0.25,
    "seguranca": 0.25,
}

# Tetos das metricas derivadas. Servem para um ticker com P/L (ou P/VP) proximo
# de zero nao gerar um yield gigante que reancora a escala do min-max e achata
# todos os outros. As duas metricas tem escalas economicas diferentes, por isso
# limites diferentes:
#   earnings yield 1.0  -> P/L de 1, ou seja 100% de lucro sobre o preco;
#                          acima disso e erro de dado, nao empresa barata.
#   book-to-market 5.0  -> P/VP de 0,2. P/VP abaixo de 1 e comum e legitimo
#                          (bancos brasileiros), entao o teto tem que ser folgado
#                          o suficiente para nao empatar 0,6 com 1,0.
LIMITE_YIELD = 1.0
LIMITE_BOOK_TO_MARKET = 5.0

# Trios (coluna do banco, coluna derivada, teto) da categoria valuation.
METRICAS_VALUATION = (
    ("pl", "earnings_yield", LIMITE_YIELD),
    ("pvp", "book_to_market", LIMITE_BOOK_TO_MARKET),
)

# Colunas cruas e derivadas que o ranking mostra para conferencia manual.
COLUNAS_VALUATION_EXIBICAO = ["pl", "pvp", "earnings_yield", "book_to_market"]


def adicionar_metricas_valuation(df):
    """Cria earnings_yield (1/pl) e book_to_market (1/pvp).

    Invertendo a metrica, a direcao "maior e melhor" fica correta em todo o
    dominio: empresa com prejuizo tem yield negativo e vai para o fim do
    ranking, em vez de parecer barata so porque o P/L negativo e um numero
    pequeno. Duas empresas com prejuizo tambem passam a ser comparaveis entre
    si, sem nenhum caso especial no codigo.

    P/L ou P/VP igual a zero implicaria preco zero (lucro zero manda o P/L para
    o infinito, nao para zero), logo e dado corrompido e nao informacao
    economica: vira NaN e cai no fillna(median) de normalizar(), junto com os
    valores ausentes. Valores muito proximos de zero pelo lado positivo geram
    yield gigante -- o clip no teto de cada metrica impede que um unico ticker
    achate todos os outros na normalizacao.
    """
    df = df.copy()
    for coluna_banco, coluna_derivada, teto in METRICAS_VALUATION:
        valores = pd.to_numeric(df[coluna_banco], errors="coerce").replace(0, np.nan)
        df[coluna_derivada] = (1 / valores).clip(-teto, teto)
    return df


def carregar_fundamentos_mais_recentes():
    conexao = sqlite3.connect(CAMINHO_BANCO)
    df = pd.read_sql_query("""
        SELECT f.*
        FROM fundamentos f
        INNER JOIN (
            SELECT ticker, MAX(data) AS data_mais_recente
            FROM fundamentos
            GROUP BY ticker
        ) ultimo
        ON f.ticker = ultimo.ticker AND f.data = ultimo.data_mais_recente
    """, conexao)
    conexao.close()
    return df.set_index("ticker")


def normalizar(valor, maior_melhor):
    valor = valor.fillna(valor.median())
    minimo, maximo = valor.min(), valor.max()
    if maximo == minimo:
        return pd.Series(50.0, index=valor.index)
    normalizado = (valor - minimo) / (maximo - minimo) * 100
    return normalizado if maior_melhor else 100 - normalizado


def calcular_score_fundamentalista():
    df = adicionar_metricas_valuation(carregar_fundamentos_mais_recentes())
    scores_categoria = pd.DataFrame(index=df.index)

    for categoria, indicadores in CATEGORIAS_FUNDAMENTALISTAS.items():
        colunas_score = []
        for indicador, maior_melhor in indicadores.items():
            if indicador not in df.columns:
                continue
            col_score = f"score_{indicador}"
            df[col_score] = normalizar(df[indicador], maior_melhor)
            colunas_score.append(col_score)
        scores_categoria[categoria] = df[colunas_score].mean(axis=1)

    scores_categoria["score_fundamentalista"] = sum(
        scores_categoria[categoria] * peso
        for categoria, peso in PESOS_CATEGORIA.items()
    )

    for coluna in COLUNAS_VALUATION_EXIBICAO:
        scores_categoria[coluna] = df[coluna]

    return scores_categoria.sort_values("score_fundamentalista", ascending=False)

PESO_FUNDAMENTALISTA = 0.6
PESO_PRECO = 0.4


def calcular_score_preco():
    conexao = sqlite3.connect(CAMINHO_BANCO)
    cotacoes = pd.read_sql_query("SELECT ticker, preco FROM cotacoes", conexao)
    conexao.close()

    agrupado = cotacoes.groupby("ticker")["preco"].agg(["min", "max", "last"])
    agrupado.columns = ["preco_min", "preco_max", "preco_atual"]

    posicao_no_range = (agrupado["preco_atual"] - agrupado["preco_min"]) / (agrupado["preco_max"] - agrupado["preco_min"])
    posicao_no_range = posicao_no_range.fillna(0.5)

    agrupado["score_preco"] = (1 - posicao_no_range) * 100
    return agrupado[["preco_atual", "score_preco"]]


def calcular_score_geral():
    fundamentalista = calcular_score_fundamentalista()
    preco = calcular_score_preco()

    combinado = fundamentalista.join(preco, how="left")
    combinado["score_preco"] = combinado["score_preco"].fillna(50.0)

    combinado["score_geral"] = (
        combinado["score_fundamentalista"] * PESO_FUNDAMENTALISTA +
        combinado["score_preco"] * PESO_PRECO
    )

    return combinado.sort_values("score_geral", ascending=False)


if __name__ == "__main__":
    fundamentos = carregar_fundamentos()
    cotacoes = carregar_cotacoes()
    posicoes = carregar_posicoes()

    print("Fundamentos:", fundamentos.shape)
    print("Cotacoes:", cotacoes.shape)
    print("Posicoes:", posicoes.shape)

    print("\nRanking geral (fundamentalista + preco):\n")
    ranking = calcular_score_geral()

    # scores em 1 casa; yields em 4, senao 0,0823 apareceria como 0,1
    ranking_exibicao = ranking.round(1)
    colunas_derivadas = ["earnings_yield", "book_to_market"]
    ranking_exibicao[colunas_derivadas] = ranking[colunas_derivadas].round(4)
    print(ranking_exibicao.to_string())