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
    JANELA_REVERSAO,
    MINIMO_OBSERVACOES,
    PESOS_INDICADOR,
    calcular_score_reversao,
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


def precos_de(*tickers, pregoes=70):
    """Serie diaria sintetica, longa o bastante para passar do minimo."""
    linhas = []
    for ticker in tickers:
        for passo in range(pregoes):
            linhas.append({
                "ticker": ticker,
                "data": f"2026-{1 + passo // 28:02d}-{1 + passo % 28:02d}",
                "fechamento": 10.0 + passo * 0.1,
                "fechamento_ajustado": 10.0 + passo * 0.1,
            })
    return pd.DataFrame(linhas)


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

    assert r.loc["PETR4", "indicadores_aplicaveis"] == 10, (
        "nao financeira: 2 de valuation + 3 de rentabilidade + 2 de margens + "
        "2 de crescimento + 1 de seguranca. margem_bruta saiu no P1-11"
    )
    assert r.loc["PETR4", "indicadores_usados"] == 10
    assert r.loc["VALE3", "indicadores_usados"] == 8, "dois indicadores faltando"
    assert r.loc["VALE3", "indicadores_aplicaveis"] == 10, (
        "faltar dado nao reduz o que se APLICA -- e isso que deixa o buraco visivel"
    )


def teste_06_financeira_tem_menos_indicadores_aplicaveis():
    df = montar(BBAS3={}, PETR4={})
    r = calcular_score_fundamentalista(df)

    assert r.loc["BBAS3", "indicadores_aplicaveis"] == 6, (
        "banco pontua valuation (2), roe, roic e os dois CAGR"
    )
    assert r.loc["PETR4", "indicadores_aplicaveis"] == 10


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
    r = calcular_ranking(montar(PETR4={}, VALE3={}), precos_de("PETR4", "VALE3"))

    assert "score_geral" not in r.columns, (
        "score_geral voltou. Ele somava 0,6*fundamentalista + 0,4*preco, o que "
        "fazia 55% do numero final ser alguma forma de 'esta barato'"
    )
    assert "score_fundamentalista" in r.columns
    assert "score_reversao" in r.columns, "os dois continuam, lado a lado"
    assert "score_preco" not in r.columns, (
        "score_preco voltou. Foi renomeado no P1-3: a metrica mede QUEDA, nao "
        "barateamento, e o nome antigo induzia leitura de valuation"
    )


def teste_13_ranking_ordena_por_fundamentalista():
    r = calcular_ranking(montar(PETR4={"roe": 40.0}, VALE3={"roe": 2.0}),
                         precos_de("PETR4", "VALE3"))
    assert list(r.index) == ["PETR4", "VALE3"]
    assert r["score_fundamentalista"].is_monotonic_decreasing


def teste_14_ticker_sem_cotacao_fica_sem_score_de_reversao():
    r = calcular_ranking(montar(PETR4={}, VALE3={}), precos_de("PETR4"))

    assert pd.isna(r.loc["VALE3", "score_reversao"]), (
        "sem serie de preco, o score era preenchido com 50.0 -- mesmo "
        "problema do fillna(median), numero inventado passando por medida"
    )


# --------------------------------------------------------------------------
# 15. P1-3: janela explicita e flag de dados insuficientes
# --------------------------------------------------------------------------
def serie(ticker, precos, ajustados=None, inicio=1):
    """Serie diaria com datas crescentes; `ajustados` default = os mesmos."""
    ajustados = ajustados if ajustados is not None else precos
    linhas = []
    for passo, (cru, ajustado) in enumerate(zip(precos, ajustados)):
        dia = inicio + passo
        linhas.append({
            "ticker": ticker,
            "data": f"2026-{1 + dia // 28:02d}-{1 + dia % 28:02d}",
            "fechamento": cru,
            "fechamento_ajustado": ajustado,
        })
    return pd.DataFrame(linhas)


def teste_15_menos_que_o_minimo_devolve_neutro_com_flag():
    # ACEITE DO P1-3: com menos de 60 observacoes, retorna 50 com flag
    r = calcular_score_reversao(serie("PETR4", [10.0 + i for i in range(59)]))

    assert r.loc["PETR4", "score_reversao"] == 50.0, (
        "com 59 pregoes o range nao descreve distribuicao nenhuma; a nota tem "
        "que ser neutra, nao um numero que parece medida"
    )
    assert bool(r.loc["PETR4", "dados_insuficientes"]) is True
    assert r.loc["PETR4", "observacoes"] == 59


def teste_16_no_minimo_exato_ja_calcula():
    # 60 pregoes subindo: o ultimo preco e a maxima, logo reversao = 0
    r = calcular_score_reversao(serie("PETR4", [10.0 + i for i in range(60)]))

    assert bool(r.loc["PETR4", "dados_insuficientes"]) is False
    assert abs(r.loc["PETR4", "score_reversao"] - 0.0) < 1e-9, (
        "subindo sem parar, o preco atual e a maxima: nao caiu nada"
    )


def teste_17_janela_corta_os_pregoes_mais_antigos():
    # uma maxima gigante bem no comeco, fora da janela de 252
    precos = [999.0] + [10.0] * JANELA_REVERSAO + [10.0]
    r = calcular_score_reversao(serie("PETR4", precos))

    assert r.loc["PETR4", "observacoes"] == JANELA_REVERSAO, (
        f"deveria usar so os ultimos {JANELA_REVERSAO} pregoes"
    )
    assert r.loc["PETR4", "score_reversao"] == 50.0, (
        "o pico de 999 ficou fora da janela; dentro dela o preco nao se moveu"
    )


def teste_18_usa_o_ajustado_e_nao_o_fechamento_cru():
    # o cru desaba por causa de um provento; o ajustado nao se move
    cru = [20.0] * 40 + [10.0] * 30
    ajustado = [10.0] * 70
    r = calcular_score_reversao(serie("PETR4", cru, ajustados=ajustado))

    assert r.loc["PETR4", "score_reversao"] == 50.0, (
        "leu o fechamento cru: no dia do provento o preco cai sem a empresa "
        "ter piorado, e isso viraria 'caiu muito'"
    )
    assert r.loc["PETR4", "preco_atual"] == 10.0, (
        "o preco EXIBIDO continua sendo o cru, que e o que aparece na tela"
    )


def teste_19_na_minima_tira_cem_e_na_maxima_tira_zero():
    caindo = calcular_score_reversao(serie("PETR4", [100.0 - i for i in range(70)]))
    subindo = calcular_score_reversao(serie("VALE3", [10.0 + i for i in range(70)]))

    assert abs(caindo.loc["PETR4", "score_reversao"] - 100.0) < 1e-9
    assert abs(subindo.loc["VALE3", "score_reversao"] - 0.0) < 1e-9


def teste_20_preco_parado_vira_neutro_sem_flag():
    r = calcular_score_reversao(serie("PETR4", [10.0] * 70))

    assert r.loc["PETR4", "score_reversao"] == 50.0
    assert bool(r.loc["PETR4", "dados_insuficientes"]) is False, (
        "ter dado e o dado nao variar sao coisas diferentes"
    )


def teste_21_janela_completa_so_com_252_pregoes():
    curta = calcular_score_reversao(serie("PETR4", [10.0 + i for i in range(63)]))
    cheia = calcular_score_reversao(serie("VALE3", [10.0 + i for i in range(JANELA_REVERSAO)]))

    assert bool(curta.loc["PETR4", "janela_completa"]) is False, (
        "63 pregoes passam do minimo de 60, mas sao 25% da janela -- a flag "
        "existe para isso nao passar por serie de um ano"
    )
    assert bool(cheia.loc["VALE3", "janela_completa"]) is True


def teste_22_serie_vazia_nao_quebra():
    vazio = pd.DataFrame(columns=["ticker", "data", "fechamento", "fechamento_ajustado"])
    assert calcular_score_reversao(vazio).empty


def teste_23_minimo_e_janela_sao_os_do_prd():
    assert JANELA_REVERSAO == 252, "252 pregoes = um ano de bolsa (PRD RF-05)"
    assert MINIMO_OBSERVACOES == 60


# --------------------------------------------------------------------------
# 24. O ACEITE DO P1-11: a nota nao depende de quem esta na whitelist
# --------------------------------------------------------------------------
def teste_24_mudar_a_whitelist_nao_muda_a_nota_de_quem_nao_mudou():
    pequeno = calcular_score_fundamentalista(montar(PETR4={}, VALE3={}))

    # entram seis papeis, inclusive extremos nos dois sentidos
    grande = calcular_score_fundamentalista(montar(
        PETR4={}, VALE3={},
        WEGE3={"roe": 40.0, "roic": 38.0, "margem_liquida": 30.0},
        FIQE3={"roe": 2.0, "roic": 1.0, "margem_liquida": -20.0},
        ISAE4={"cagr_receita_5a": 50.0}, BBSE3={"cagr_receita_5a": -30.0},
    ))

    for categoria in ("rentabilidade", "margens", "crescimento", "seguranca"):
        antes = pequeno.loc["PETR4", categoria]
        depois = grande.loc["PETR4", categoria]
        assert abs(antes - depois) < 1e-9, (
            f"a nota de {categoria} da PETR4 mudou de {antes:.2f} para "
            f"{depois:.2f} so porque entraram outros tickers. E exatamente o "
            f"que o P1-11 veio eliminar -- sem isso os snapshots do O1 nao "
            f"sao comparaveis no tempo"
        )


def teste_25_valuation_continua_relativo_de_proposito():
    pequeno = calcular_score_fundamentalista(montar(PETR4={"pl": 10.0}, VALE3={"pl": 12.0}))
    grande = calcular_score_fundamentalista(montar(
        PETR4={"pl": 10.0}, VALE3={"pl": 12.0}, WEGE3={"pl": 2.0}, FIQE3={"pl": 80.0},
    ))

    assert pequeno.loc["PETR4", "valuation"] != grande.loc["PETR4", "valuation"], (
        "valuation e a excecao e TEM que mudar com o universo: 'caro' so "
        "existe em comparacao"
    )


# --------------------------------------------------------------------------
# 26. Faixa absoluta: a nota sai do valor, pela tabela do faixas.py
# --------------------------------------------------------------------------
def teste_26_nota_da_categoria_e_media_ponderada_das_ancoras():
    # ROIC 40%, ROE 35%, ROA 25%
    df = montar(PETR4={"roic": 20.0, "roe": 20.0, "roa": 12.0})
    r = calcular_score_fundamentalista(df)

    esperado = 100.0 * 0.40 + 100.0 * 0.35 + 100.0 * 0.25
    assert abs(r.loc["PETR4", "rentabilidade"] - esperado) < 1e-9


def teste_27_peso_do_indicador_ausente_e_redistribuido():
    # sem ROA: a nota tem que ser a ponderada de ROIC e ROE so entre eles
    df = montar(PETR4={"roic": 20.0, "roe": 10.0, "roa": np.nan})
    r = calcular_score_fundamentalista(df)

    esperado = (100.0 * 0.40 + 55.0 * 0.35) / (0.40 + 0.35)
    assert abs(r.loc["PETR4", "rentabilidade"] - esperado) < 1e-9, (
        "faltar ROA nao pode puxar a nota para baixo so por falta de dado"
    )


def teste_28_roic_pesa_mais_que_roe_que_pesa_mais_que_roa():
    assert PESOS_INDICADOR["rentabilidade"]["roic"] == 0.40
    assert PESOS_INDICADOR["rentabilidade"]["roe"] == 0.35
    assert PESOS_INDICADOR["rentabilidade"]["roa"] == 0.25
    assert PESOS_INDICADOR["crescimento"]["cagr_receita_5a"] == 0.60, (
        "receita pesa mais que lucro: e menos manipulavel contabilmente"
    )


# --------------------------------------------------------------------------
# 29. Margens viraram categoria propria e margem_bruta saiu
# --------------------------------------------------------------------------
def teste_29_margens_e_categoria_separada():
    r = calcular_score_fundamentalista(montar(PETR4={"margem_liquida": 20.0,
                                                    "margem_ebitda": 30.0}))
    assert "margens" in r.columns
    assert abs(r.loc["PETR4", "margens"] - 100.0) < 1e-9


def teste_30_margem_bruta_nao_move_mais_nenhuma_nota():
    alta = calcular_score_fundamentalista(montar(PETR4={"margem_bruta": 90.0}))
    baixa = calcular_score_fundamentalista(montar(PETR4={"margem_bruta": 1.0}))

    assert (alta.loc["PETR4", "score_fundamentalista"]
            == baixa.loc["PETR4", "score_fundamentalista"]), (
        "margem_bruta ainda pontua. Ela e a mais dependente de setor do "
        "conjunto e so adiciona ruido (7A.4)"
    )


def teste_31_banco_nao_tem_categoria_margens():
    r = calcular_score_fundamentalista(montar(BBAS3={}, PETR4={}))
    assert pd.isna(r.loc["BBAS3", "margens"]), "banco nao tem EBITDA no sentido usual"
    assert not pd.isna(r.loc["PETR4", "margens"])


def teste_32_cap_do_cagr_de_lucro_vale_no_score():
    capado = calcular_score_fundamentalista(montar(PETR4={"cagr_lucro_5a": 77.68}))
    no_teto = calcular_score_fundamentalista(montar(PETR4={"cagr_lucro_5a": 30.0}))

    assert (capado.loc["PETR4", "crescimento"]
            == no_teto.loc["PETR4", "crescimento"]), (
        "sem o teto, ano-base deprimido vira crescimento espetacular"
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

    print("\n\nTabela de conferencia manual -- score de reversao por tamanho de janela.")
    print("Serie sempre caindo de forma constante, so mudando quantos pregoes existem:\n")
    print(f"{'pregoes':>8s} {'nota':>7s} {'insuf?':>8s} {'cheia?':>8s}  comentario")
    for pregoes, comentario in [(20, "interruptor puro, sem significado"),
                                (59, "um abaixo do minimo"),
                                (60, "minimo exato, ja calcula"),
                                (63, "o que temos hoje: 25% da janela"),
                                (JANELA_REVERSAO, "um ano de bolsa")]:
        linha = calcular_score_reversao(serie("X", [100.0 - i * 0.1 for i in range(pregoes)]))
        print(f"{pregoes:8d} {linha.loc['X', 'score_reversao']:7.1f} "
              f"{str(bool(linha.loc['X', 'dados_insuficientes'])):>8s} "
              f"{str(bool(linha.loc['X', 'janela_completa'])):>8s}  {comentario}")

    print("\nNos tres casos de cima a serie cai igual, e a nota e a mesma 100.")
    print("O que muda e quanta confianca ela merece -- por isso as duas flags.")
