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
    "valuation": {"pl": False, "pvp": False},
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
    df = carregar_fundamentos_mais_recentes()
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
    print(ranking.round(1).to_string())