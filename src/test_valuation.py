"""Testes do P0-4: valuation via earnings yield e book-to-market.

Roda sem pytest, no mesmo estilo dos outros scripts de teste do projeto:

    cd src && python test_valuation.py

Os casos 1 a 9 usam dados sinteticos (deterministicos, nao dependem do banco).
O caso 10 e um smoke test que le o banco real.
"""

import numpy as np
import pandas as pd

from analise import (
    CATEGORIAS_FUNDAMENTALISTAS,
    LIMITE_BOOK_TO_MARKET,
    LIMITE_YIELD,
    adicionar_metricas_valuation,
    calcular_score_geral,
    normalizar,
)


def score_valuation(df):
    """Reproduz a categoria valuation usando as funcoes reais do analise.py."""
    derivado = adicionar_metricas_valuation(df)
    scores = pd.DataFrame(index=derivado.index)
    for indicador, maior_melhor in CATEGORIAS_FUNDAMENTALISTAS["valuation"].items():
        scores[indicador] = normalizar(derivado[indicador], maior_melhor)
    return scores.mean(axis=1)


def montar(casos):
    """casos = {ticker: (pl, pvp)} -> DataFrame indexado por ticker."""
    return pd.DataFrame(
        {"pl": [pl for pl, _ in casos.values()], "pvp": [pvp for _, pvp in casos.values()]},
        index=list(casos),
    )


# --------------------------------------------------------------------------
# 1. A inversao da metrica esta certa para empresa lucrativa
# --------------------------------------------------------------------------
def teste_01_inversao_basica():
    df = montar({"A": (10.0, 2.0), "B": (4.0, 0.5)})
    derivado = adicionar_metricas_valuation(df)

    assert derivado.loc["A", "earnings_yield"] == 0.1, "1/10 deveria ser 0,10"
    assert derivado.loc["A", "book_to_market"] == 0.5, "1/2 deveria ser 0,50"
    assert derivado.loc["B", "earnings_yield"] == 0.25, "1/4 deveria ser 0,25"
    assert derivado.loc["B", "book_to_market"] == 2.0, "1/0,5 deveria ser 2,00"


# --------------------------------------------------------------------------
# 2. O bug do P0-4: prejuizo nao pode mais pontuar como barato
# --------------------------------------------------------------------------
def teste_02_prejuizo_perde_de_empresa_lucrativa():
    # pvp igual nos tres para isolar o efeito do P/L
    df = montar({"LUCRO_CARO": (40.0, 1.5), "LUCRO_BARATO": (5.0, 1.5), "PREJUIZO": (-8.0, 1.5)})
    scores = score_valuation(df)

    assert scores["PREJUIZO"] < scores["LUCRO_CARO"], (
        "empresa com prejuizo ficou melhor que empresa lucrativa e cara "
        "-- e exatamente o bug que o P0-4 corrige"
    )
    assert scores["PREJUIZO"] < scores["LUCRO_BARATO"]
    assert scores["LUCRO_BARATO"] > scores["LUCRO_CARO"], "P/L menor deveria pontuar mais"


# --------------------------------------------------------------------------
# 3. Duas empresas com prejuizo ficam comparaveis entre si
# --------------------------------------------------------------------------
def teste_03_ordena_prejuizos_entre_si():
    # P/L -50 = prejuizo pequeno em relacao ao preco; P/L -2 = prejuizo enorme
    df = montar({"PREJUIZO_PEQUENO": (-50.0, 1.5), "PREJUIZO_GRANDE": (-2.0, 1.5)})
    scores = score_valuation(df)

    assert scores["PREJUIZO_PEQUENO"] > scores["PREJUIZO_GRANDE"], (
        "prejuizo pequeno deveria pontuar mais que prejuizo grande"
    )


# --------------------------------------------------------------------------
# 4. Divisao por zero nao vira numero: vira dado ausente
# --------------------------------------------------------------------------
def teste_04_zero_vira_nan():
    df = montar({"PL_ZERO": (0.0, 2.0), "PVP_ZERO": (10.0, 0.0)})
    derivado = adicionar_metricas_valuation(df)

    assert pd.isna(derivado.loc["PL_ZERO", "earnings_yield"]), "P/L zero deveria virar NaN"
    assert pd.isna(derivado.loc["PVP_ZERO", "book_to_market"]), "P/VP zero deveria virar NaN"
    # nao contamina a outra metrica do mesmo ticker
    assert derivado.loc["PL_ZERO", "book_to_market"] == 0.5
    assert derivado.loc["PVP_ZERO", "earnings_yield"] == 0.1
    assert not np.isinf(derivado[["earnings_yield", "book_to_market"]].to_numpy()).any(), (
        "nenhum infinito deveria sobrar"
    )


# --------------------------------------------------------------------------
# 5. Ausente continua ausente (o fillna(median) e do normalizar, P1-13)
# --------------------------------------------------------------------------
def teste_05_nulo_continua_nulo():
    df = montar({"SEM_PL": (None, 2.0), "SEM_PVP": (10.0, np.nan)})
    derivado = adicionar_metricas_valuation(df)

    assert pd.isna(derivado.loc["SEM_PL", "earnings_yield"])
    assert pd.isna(derivado.loc["SEM_PVP", "book_to_market"])


# --------------------------------------------------------------------------
# 6. O teto corta o outlier de P/L perto de zero
# --------------------------------------------------------------------------
def teste_06_teto_corta_yield_gigante():
    df = montar({"NORMAL": (10.0, 2.0), "PL_QUASE_ZERO": (0.05, 2.0)})
    derivado = adicionar_metricas_valuation(df)

    assert derivado.loc["PL_QUASE_ZERO", "earnings_yield"] == LIMITE_YIELD, (
        "1/0,05 = 20 deveria ser capado em LIMITE_YIELD"
    )
    # o teto vale para os dois lados
    df_negativo = montar({"PREJ_MINUSCULO": (-0.02, 2.0), "NORMAL": (10.0, 2.0)})
    derivado_negativo = adicionar_metricas_valuation(df_negativo)
    assert derivado_negativo.loc["PREJ_MINUSCULO", "earnings_yield"] == -LIMITE_YIELD


# --------------------------------------------------------------------------
# 7. Regressao: o teto do book-to-market nao pode empatar P/VP legitimo
# --------------------------------------------------------------------------
def teste_07_pvp_abaixo_de_um_nao_e_capado():
    # esses tres P/VP sao todos plausiveis (bancos brasileiros) e devem ficar
    # distintos; com teto de 1,0 os tres empatavam
    df = montar({"BANCO_A": (8.0, 0.6), "BANCO_B": (8.0, 0.8), "BANCO_C": (8.0, 1.0)})
    btm = adicionar_metricas_valuation(df)["book_to_market"]

    assert btm["BANCO_A"] > btm["BANCO_B"] > btm["BANCO_C"], (
        "P/VP legitimo abaixo de 1 esta sendo achatado pelo teto"
    )
    assert btm.nunique() == 3, "tres P/VP diferentes viraram menos de tres valores"

    # e o teto ainda existe, para P/VP implausivel
    implausivel = adicionar_metricas_valuation(montar({"X": (8.0, 0.01)}))
    assert implausivel.loc["X", "book_to_market"] == LIMITE_BOOK_TO_MARKET


# --------------------------------------------------------------------------
# 8. O teto nunca inverte a ordenacao (so empata no extremo)
# --------------------------------------------------------------------------
def teste_08_teto_e_monotono():
    df = montar({f"T{i}": (pl, 1.5) for i, pl in enumerate([0.01, 0.05, 0.5, 2.0, 10.0, 40.0])})
    ey = adicionar_metricas_valuation(df)["earnings_yield"]

    assert ey.is_monotonic_decreasing, "P/L crescente deveria dar yield nao-crescente"


# --------------------------------------------------------------------------
# 9. Contrato: o que o P0-4 mexeu e o que ele nao podia mexer
# --------------------------------------------------------------------------
def teste_09_contrato_da_categoria():
    assert CATEGORIAS_FUNDAMENTALISTAS["valuation"] == {
        "earnings_yield": True,
        "book_to_market": True,
    }, "a categoria valuation deveria usar as duas metricas invertidas, maior e melhor"

    # as outras categorias seguem intactas (serao redesenhadas no P1-11)
    assert CATEGORIAS_FUNDAMENTALISTAS["seguranca"] == {"divida_patrimonio": False}
    assert CATEGORIAS_FUNDAMENTALISTAS["crescimento"] == {
        "cagr_receita_5a": True,
        "cagr_lucro_5a": True,
    }
    assert len(CATEGORIAS_FUNDAMENTALISTAS["rentabilidade"]) == 6

    # pl e pvp continuam existindo no dataframe, so nao entram no score
    derivado = adicionar_metricas_valuation(montar({"A": (10.0, 2.0)}))
    assert "pl" in derivado.columns and "pvp" in derivado.columns

    # normalizar() nao foi tocada: escala 0-100 e fillna(median)
    serie = pd.Series([1.0, 2.0, 3.0], index=["a", "b", "c"])
    assert list(normalizar(serie, True)) == [0.0, 50.0, 100.0]
    assert normalizar(pd.Series([1.0, np.nan, 3.0]), True)[1] == 50.0


# --------------------------------------------------------------------------
# 10. Smoke test no banco real: o ranking mostra as colunas de conferencia
# --------------------------------------------------------------------------
def teste_10_ranking_mostra_colunas_de_conferencia():
    ranking = calcular_score_geral()

    for coluna in ["pl", "pvp", "earnings_yield", "book_to_market", "score_geral"]:
        assert coluna in ranking.columns, f"coluna {coluna} faltando no ranking"

    # o yield exibido tem que bater com 1/pl na mao, onde o P/L e plausivel
    plausivel = ranking[(ranking["pl"] > 1 / LIMITE_YIELD) & ranking["pl"].notna()]
    assert len(plausivel) > 0, "banco sem nenhum P/L plausivel para conferir"
    assert np.allclose(plausivel["earnings_yield"], 1 / plausivel["pl"]), (
        "earnings_yield exibido nao bate com 1/pl"
    )


if __name__ == "__main__":
    testes = [valor for nome, valor in sorted(globals().items()) if nome.startswith("teste_")]

    falhas = 0
    for teste in testes:
        try:
            teste()
        except AssertionError as erro:
            falhas += 1
            print(f"FALHOU  {teste.__name__}")
            print(f"        {erro}")
        else:
            print(f"ok      {teste.__name__}")

    print(f"\n{len(testes) - falhas}/{len(testes)} testes passaram")

    print("\nTabela de conferencia manual:\n")
    casos = {
        "lucrativa": (10.0, 2.0),
        "lucrativa barata": (4.0, 0.6),
        "prejuizo pequeno": (-50.0, 1.5),
        "prejuizo grande": (-2.0, 1.5),
        "pl zero": (0.0, 2.0),
        "pl ausente": (None, 2.0),
        "pl quase zero": (0.05, 2.0),
        "pvp implausivel": (8.0, 0.01),
    }
    print(adicionar_metricas_valuation(montar(casos)).to_string())
