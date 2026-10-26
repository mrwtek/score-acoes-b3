"""Testes do P1-13: dado ausente, cobertura e fim do score_geral.

Roda sem pytest, no mesmo estilo dos outros scripts de teste do projeto:

    cd src && python test_scoring.py

Dados sinteticos, sem banco e sem API -- exatamente o que a separacao do P1-1
(scoring.py nao le o banco) tornou possivel. Os tickers usados sao reais
porque as regras de setor dependem deles: BBAS3 e financeira, PETR4 nao.
"""

import numpy as np
import pandas as pd

from scoring import (
    CATEGORIAS_FUNDAMENTALISTAS,
    PESOS_CATEGORIA,
    calcular_ranking,
    calcular_score_fundamentalista,
    normalizar,
)

COLUNAS = ["pl", "pvp", "roe", "roa", "roic", "margem_liquida", "margem_bruta",
           "margem_ebitda", "cagr_receita_5a", "cagr_lucro_5a", "divida_patrimonio"]

PADRAO = {"pl": 10.0, "pvp": 1.5, "roe": 15.0, "roa": 6.0, "roic": 12.0,
          "margem_liquida": 10.0, "margem_bruta": 30.0, "margem_ebitda": 20.0,
          "cagr_receita_5a": 8.0, "cagr_lucro_5a": 7.0, "divida_patrimonio": 1.0}


def montar(**por_ticker):
    """montar(PETR4={"roe": 20}, VALE3={}) -> DataFrame com o resto no padrao."""
    linhas = {}
    for ticker, ajustes in por_ticker.items():
        valores = dict(PADRAO)
        valores.update(ajustes)
        linhas[ticker] = valores
    return pd.DataFrame.from_dict(linhas, orient="index")[COLUNAS]


def cotacoes_de(*tickers):
    return pd.DataFrame(
        {"ticker": list(tickers) * 2,
         "preco": [10.0] * len(tickers) + [12.0] * len(tickers)}
    )


# --------------------------------------------------------------------------
# 1. O fim do fillna(median)
# --------------------------------------------------------------------------
def teste_01_indicador_ausente_nao_vira_nota_media():
    serie = pd.Series([10.0, np.nan, 30.0], index=["a", "b", "c"])
    notas = normalizar(serie, maior_melhor=True)

    assert pd.isna(notas["b"]), (
        "ausente virou nota. Antes o fillna(median) dava nota media em "
        "silencio, e nada no ranking distinguia 'mediano' de 'nao sabemos'"
    )
    assert notas["a"] == 0.0 and notas["c"] == 100.0


def teste_02_ausente_nao_mexe_mais_na_escala_dos_presentes():
    com_buraco = normalizar(pd.Series([10.0, np.nan, 30.0]), True)
    sem_buraco = normalizar(pd.Series([10.0, 30.0]), True)

    assert list(com_buraco.dropna()) == list(sem_buraco), (
        "o ausente influenciou min/max; antes ele entrava como mediana e "
        "comprimia a escala"
    )


def teste_03_serie_toda_ausente_nao_quebra():
    notas = normalizar(pd.Series([np.nan, np.nan]), True)
    assert notas.isna().all()


def teste_04_todos_iguais_viram_neutro_menos_o_ausente():
    notas = normalizar(pd.Series([5.0, 5.0, np.nan], index=["a", "b", "c"]), True)
    assert notas["a"] == 50.0 and notas["b"] == 50.0
    assert pd.isna(notas["c"]), "sem valor nao ha nota, nem mesmo a neutra"


# --------------------------------------------------------------------------
# 5. Cobertura
# --------------------------------------------------------------------------
def teste_05_cobertura_conta_indicadores_usados_e_aplicaveis():
    df = montar(PETR4={}, VALE3={"roe": np.nan, "roa": np.nan})
    r = calcular_score_fundamentalista(df)

    assert r.loc["PETR4", "indicadores_aplicaveis"] == 11, (
        "nao financeira: 2 de valuation + 6 de rentabilidade + 2 de crescimento + 1 de seguranca"
    )
    assert r.loc["PETR4", "indicadores_usados"] == 11
    assert r.loc["VALE3", "indicadores_usados"] == 9, "dois indicadores faltando"
    assert r.loc["VALE3", "indicadores_aplicaveis"] == 11, (
        "faltar dado nao reduz o que se APLICA -- e isso que deixa o buraco visivel"
    )


def teste_06_financeira_tem_menos_indicadores_aplicaveis():
    df = montar(BBAS3={}, PETR4={})
    r = calcular_score_fundamentalista(df)

    assert r.loc["BBAS3", "indicadores_aplicaveis"] == 6, (
        "banco pontua valuation (2), roe, roic e os dois CAGR"
    )
    assert r.loc["PETR4", "indicadores_aplicaveis"] == 11


# --------------------------------------------------------------------------
# 7. O caso de aceite do P1-12, agora de ponta a ponta
# --------------------------------------------------------------------------
def teste_07_banco_nao_tira_zero_em_seguranca():
    # divida/PL alta no banco, baixa na nao-financeira: pelo min-max antigo o
    # banco tirava exatamente 0.0
    df = montar(BBAS3={"divida_patrimonio": 5.13}, PETR4={"divida_patrimonio": 0.76})
    r = calcular_score_fundamentalista(df)

    assert pd.isna(r.loc["BBAS3", "seguranca"]), (
        "BBAS3 recebeu nota de seguranca. Alavancagem e o modelo de negocio de "
        "um banco; a nota tem que ser ausente, nunca 0 e nunca neutra"
    )
    assert r.loc["BBAS3", "seguranca"] != 0.0


def teste_08_valor_de_financeira_nao_ancora_a_escala_dos_outros():
    com_banco = calcular_score_fundamentalista(montar(
        BBAS3={"divida_patrimonio": 5.13},
        PETR4={"divida_patrimonio": 0.76},
        WEGE3={"divida_patrimonio": 0.27},
    ))
    sem_banco = calcular_score_fundamentalista(montar(
        PETR4={"divida_patrimonio": 0.76},
        WEGE3={"divida_patrimonio": 0.27},
    ))

    assert com_banco.loc["PETR4", "seguranca"] == sem_banco.loc["PETR4", "seguranca"], (
        "a divida/PL do banco mudou a nota da PETR4 -- ela tem que sair da "
        "coluna ANTES de normalizar, nao so deixar de pontuar"
    )


# --------------------------------------------------------------------------
# 9. Categoria vazia sai da conta, com o peso redistribuido
# --------------------------------------------------------------------------
def teste_09_categoria_sem_indicador_vira_ausente_e_nao_zero():
    r = calcular_score_fundamentalista(montar(BBAS3={}, BBDC4={}))
    assert pd.isna(r.loc["BBAS3", "seguranca"])
    assert pd.isna(r.loc["BBAS3", "margens"]) if "margens" in r.columns else True
    assert r.loc["BBAS3", "categorias_usadas"] == 3, (
        "banco tem valuation, rentabilidade e crescimento; seguranca sai"
    )


def teste_10_peso_e_redistribuido_entre_as_categorias_presentes():
    r = calcular_score_fundamentalista(montar(BBAS3={}, BBDC4={}, ITUB4={}))

    presentes = [c for c in CATEGORIAS_FUNDAMENTALISTAS if not pd.isna(r.loc["BBAS3", c])]
    soma_pesos = sum(PESOS_CATEGORIA[c] for c in presentes)
    esperado = sum(r.loc["BBAS3", c] * PESOS_CATEGORIA[c] for c in presentes) / soma_pesos

    assert abs(r.loc["BBAS3", "score_fundamentalista"] - esperado) < 1e-9, (
        "o peso da categoria ausente nao foi redistribuido; o score ficaria "
        "artificialmente baixo so por faltar categoria"
    )


def teste_11_ticker_sem_nenhum_dado_nao_vira_zero():
    vazio = {coluna: np.nan for coluna in COLUNAS}
    r = calcular_score_fundamentalista(montar(PETR4={}, VALE3=vazio))

    assert pd.isna(r.loc["VALE3", "score_fundamentalista"]), (
        "ticker sem nenhum indicador recebeu nota. Zero diria 'ruim' quando a "
        "verdade e 'nao da para saber'"
    )
    assert r.loc["VALE3", "indicadores_usados"] == 0


# --------------------------------------------------------------------------
# 12. O fim do score_geral
# --------------------------------------------------------------------------
def teste_12_score_geral_nao_existe_mais():
    r = calcular_ranking(montar(PETR4={}, VALE3={}), cotacoes_de("PETR4", "VALE3"))

    assert "score_geral" not in r.columns, (
        "score_geral voltou. Ele somava 0,6*fundamentalista + 0,4*preco, o que "
        "fazia 55% do numero final ser alguma forma de 'esta barato'"
    )
    assert "score_fundamentalista" in r.columns
    assert "score_preco" in r.columns, "os dois continuam, lado a lado"


def teste_13_ranking_ordena_por_fundamentalista():
    r = calcular_ranking(montar(PETR4={"roe": 40.0}, VALE3={"roe": 2.0}),
                         cotacoes_de("PETR4", "VALE3"))
    assert list(r.index) == ["PETR4", "VALE3"]
    assert r["score_fundamentalista"].is_monotonic_decreasing


def teste_14_ticker_sem_cotacao_fica_sem_score_de_preco():
    r = calcular_ranking(montar(PETR4={}, VALE3={}), cotacoes_de("PETR4"))

    assert pd.isna(r.loc["VALE3", "score_preco"]), (
        "sem cotacao, o score de preco era preenchido com 50.0 -- mesmo "
        "problema do fillna(median), numero inventado passando por medida"
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

    print("\nTabela de conferencia manual -- cobertura e peso redistribuido:\n")
    exemplo = calcular_score_fundamentalista(montar(
        PETR4={},
        BBAS3={},                                   # financeira: perde 5 indicadores
        VALE3={"roe": np.nan, "cagr_lucro_5a": np.nan},  # nao financeira com buracos
        BBSE3={"margem_liquida": np.nan, "cagr_receita_5a": np.nan},  # financeira com buracos
    ))
    colunas = list(CATEGORIAS_FUNDAMENTALISTAS) + [
        "score_fundamentalista", "categorias_usadas",
        "indicadores_usados", "indicadores_aplicaveis",
    ]
    print(exemplo[colunas].round(1).to_string())
    print("\nNaN em categoria = nenhum indicador aplicavel com dado; o peso dela")
    print("e redistribuido. Note que BBAS3 e BBSE3 tem 6 aplicaveis, nao 11.")
