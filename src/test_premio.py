"""Testes do P1-14: a flag premio_negativo e a regua viva da Selic.

    cd src && python test_premio.py

Dados sinteticos, no mesmo estilo dos outros testes do projeto. Os unicos
testes que tocam o banco sao os da selic_anual_vigente(), e mesmo esses
trocam a funcao de leitura por uma falsa -- ninguem aqui depende de quantos
pontos a serie do BCB tem hoje.

O QUE ESTE ARQUIVO PROTEGE, em ordem de quanto doeria:

1. A UNIDADE. earnings_yield e fracao (0,1961) e a Selic vem em ponto
   percentual (13,65). Comparar os dois crus marca 10 de 10 tickers como
   premio negativo, inclusive quem paga o dobro da Selic, e a tela fica
   plausivel -- erro de escala nao parece erro, parece mercado caro.
2. AUSENTE NAO E FALSO. Quem nao tem P/L nao tem premio conhecido. Dizer
   "nao tem premio negativo" sobre esse ticker e inventar.
3. A FLAG NAO E NOTA. Se um dia ela encostar no score, o P1-13 volta pela
   janela -- era exatamente disso que o score_geral foi acusado.
"""

import numpy as np
import pandas as pd

import faixas
import indices
from scoring import calcular_premio_selic, calcular_score_fundamentalista

# Selic de referencia usada nos testes. Numero fixo de proposito: o teste nao
# pode depender do que o BCB publicou hoje.
SELIC = 13.65

COLUNAS = ["pl", "pvp", "roe", "roa", "roic", "margem_liquida", "margem_bruta",
           "margem_ebitda", "cagr_receita_5a", "cagr_lucro_5a", "divida_patrimonio"]

PADRAO = {"pl": 10.0, "pvp": 1.5, "roe": 15.0, "roa": 6.0, "roic": 12.0,
          "margem_liquida": 10.0, "margem_bruta": 30.0, "margem_ebitda": 20.0,
          "cagr_receita_5a": 8.0, "cagr_lucro_5a": 7.0, "divida_patrimonio": 1.0}

# P/L que faz o earnings yield bater EXATAMENTE na Selic: 1/pl*100 = 13,65.
PL_NA_SELIC = 100 / SELIC


def montar(**por_ticker):
    """montar(PETR4={"pl": 5.1}) -> DataFrame com o resto no padrao."""
    linhas = {}
    for ticker, trocas in por_ticker.items():
        linha = dict(PADRAO)
        linha.update(trocas)
        linhas[ticker] = linha
    return pd.DataFrame.from_dict(linhas, orient="index")[COLUNAS]


def pontuar(**por_ticker):
    return calcular_score_fundamentalista(montar(**por_ticker), selic_anual=SELIC)


# --------------------------------------------------------------------------
# 1. A armadilha de unidade
# --------------------------------------------------------------------------
def teste_01_yield_alto_nao_e_premio_negativo():
    """PETR4 a P/L 5,10 paga 19,6% a.a. -- quase 6 pontos ACIMA da Selic.

    Comparando cru, 0,1961 < 13,65 e verdadeiro e a flag acenderia. Este e o
    unico teste que distingue a implementacao certa da errada em 10 de 10
    tickers reais da carteira.
    """
    r = pontuar(PETR4={"pl": 5.10})
    assert abs(r.loc["PETR4", "premio_selic_pp"] - (100 / 5.10 - SELIC)) < 1e-9
    assert r.loc["PETR4", "premio_negativo"] == False, (
        "yield de 19,6% a.a. marcado como abaixo da Selic -- a comparacao "
        "esta sendo feita entre fracao e ponto percentual"
    )


def teste_02_yield_baixo_e_premio_negativo():
    """WEGE3 a P/L 30,91 paga 3,2% a.a.: 10 pontos abaixo de titulo publico."""
    r = pontuar(WEGE3={"pl": 30.91})
    assert r.loc["WEGE3", "premio_negativo"] == True
    assert r.loc["WEGE3", "premio_selic_pp"] < -10


def teste_03_a_conta_e_subtracao_nao_composicao():
    """Premio e diferenca em pontos percentuais, nao (1+a)/(1+b)-1.

    Caso OPOSTO ao do CAGR em faixas.deflacionar(), e a diferenca entre os
    dois nao e academica: com yield de 20% e Selic de 13,65%, subtrair da
    6,35 e compor daria 5,59. Um e premio de risco, o outro nao e nada.
    """
    premio = calcular_premio_selic(pd.Series([0.20]), SELIC).iloc[0]
    assert abs(premio - 6.35) < 1e-9
    composto = ((1 + 0.20) / (1 + SELIC / 100) - 1) * 100
    assert abs(premio - composto) > 0.5


# --------------------------------------------------------------------------
# 2. Bordas e ausencia
# --------------------------------------------------------------------------
def teste_04_exatamente_na_selic_nao_e_negativo():
    """Premio zero e empate, nao desvantagem. A flag so acende abaixo."""
    r = pontuar(XPTO3={"pl": PL_NA_SELIC})
    assert abs(r.loc["XPTO3", "premio_selic_pp"]) < 1e-9
    assert r.loc["XPTO3", "premio_negativo"] == False


def teste_05_um_milesimo_abaixo_ja_acende():
    r = pontuar(XPTO3={"pl": PL_NA_SELIC * 1.001})
    assert r.loc["XPTO3", "premio_selic_pp"] < 0
    assert r.loc["XPTO3", "premio_negativo"] == True


def teste_06_prejuizo_acende_a_flag():
    """P/L negativo = prejuizo. Yield negativo esta abaixo da Selic sempre."""
    r = pontuar(XPTO3={"pl": -8.0})
    assert r.loc["XPTO3", "premio_selic_pp"] < 0
    assert r.loc["XPTO3", "premio_negativo"] == True


def teste_07_sem_pl_fica_ausente_e_nao_falso():
    """Ausente nao vira False. False afirma 'tem premio', e nao se sabe."""
    r = pontuar(SEMPL3={"pl": np.nan}, ZERO3={"pl": 0.0})
    for ticker in ("SEMPL3", "ZERO3"):
        assert pd.isna(r.loc[ticker, "premio_selic_pp"]), ticker
        assert pd.isna(r.loc[ticker, "premio_negativo"]), (
            f"{ticker}: premio ausente virou booleano -- um ticker sem P/L "
            f"passa a aparecer como 'tem premio' ou 'nao tem', e nenhum dos "
            f"dois e verdade"
        )


def teste_08_dtype_anulavel():
    """A coluna precisa ser 'boolean' (anulavel), nao 'bool' nem 'object'."""
    r = pontuar(PETR4={}, SEMPL3={"pl": np.nan})
    assert str(r["premio_negativo"].dtype) == "boolean", r["premio_negativo"].dtype


# --------------------------------------------------------------------------
# 3. A flag nao e nota
# --------------------------------------------------------------------------
def teste_09_regua_diferente_nao_muda_o_score():
    """Trocar a Selic muda a flag e NADA mais. E a definicao do P1-14.

    Se este teste falhar, o premio vazou para dentro do score e o composto
    que o P1-13 removeu voltou disfarcado.
    """
    dados = dict(PETR4={"pl": 5.10}, WEGE3={"pl": 30.91}, VALE3={"pl": 26.97})
    barata = calcular_score_fundamentalista(montar(**dados), selic_anual=2.0)
    cara = calcular_score_fundamentalista(montar(**dados), selic_anual=40.0)

    assert list(barata.index) == list(cara.index), "a ordem do ranking mudou"
    for coluna in ("valuation", "rentabilidade", "margens", "crescimento",
                   "seguranca", "score_fundamentalista"):
        for ticker in barata.index:
            assert abs(barata.loc[ticker, coluna] - cara.loc[ticker, coluna]) < 1e-9, (
                f"{ticker}.{coluna} mudou com a Selic -- a flag virou nota"
            )

    assert barata["premio_negativo"].sum() == 0, "Selic a 2% e alguem ficou abaixo?"
    assert cara["premio_negativo"].sum() == 3, "Selic a 40% e alguem passou?"


def teste_10_premio_nao_entra_na_cobertura():
    """O premio nao e indicador: nao conta em indicadores_usados."""
    sem_flag = pontuar(PETR4={"pl": PL_NA_SELIC})
    com_flag = pontuar(PETR4={"pl": 30.0})
    assert (sem_flag.loc["PETR4", "indicadores_usados"]
            == com_flag.loc["PETR4", "indicadores_usados"])


# --------------------------------------------------------------------------
# 4. A regua viva (indices.py)
# --------------------------------------------------------------------------
def teste_11_anualizar_compoe_nao_multiplica():
    """0,050788% ao dia da 13,65% ao ano compondo, 12,80% multiplicando."""
    anual = indices.anualizar_taxa_diaria(0.050788)
    assert abs(anual - 13.65) < 0.01, anual
    assert abs(anual - 0.050788 * 252) > 0.8, (
        "compor e multiplicar deram quase o mesmo numero -- confira os 252"
    )


def teste_12_selic_do_banco_vira_regua():
    pontos = [("2026-10-23", 0.050788), ("2026-10-26", 0.050788)]
    with _serie_falsa(pontos):
        r = indices.selic_anual_vigente(hoje="2026-10-28")
    assert abs(r["selic_anual"] - 13.65) < 0.01
    assert r["selic_data"] == "2026-10-26", "pegou um ponto que nao e o ultimo"
    assert r["defasagem_dias"] == 2
    assert r["fonte"] == indices.FONTE_SELIC_BANCO


def teste_13_sem_serie_cai_para_a_constante():
    with _serie_falsa([]):
        r = indices.selic_anual_vigente(hoje="2026-10-28")
    assert r["selic_anual"] == faixas.SELIC_REFERENCIA
    assert r["fonte"] == indices.FONTE_SELIC_FIXA
    assert r["selic_data"] is None


def teste_14_taxa_implausivel_cai_para_a_constante():
    """1% ao dia seria Selic de 1.100% ao ano. E erro de dado, nao politica."""
    with _serie_falsa([("2026-10-26", 1.0)]):
        r = indices.selic_anual_vigente(hoje="2026-10-28")
    assert r["selic_anual"] == faixas.SELIC_REFERENCIA
    assert r["fonte"] == indices.FONTE_SELIC_FIXA


def teste_15_serie_velha_ainda_serve():
    """Defasagem nao e motivo para recusar -- a Selic fica parada entre Copoms.

    Recusar por estar velha trocaria uma regua de dois meses atras por uma
    constante editada a mao ha mais tempo ainda, que e estritamente pior.
    """
    with _serie_falsa([("2026-08-14", 0.050788)]):
        r = indices.selic_anual_vigente(hoje="2026-10-28")
    assert r["fonte"] == indices.FONTE_SELIC_BANCO
    assert r["defasagem_dias"] == 75, r["defasagem_dias"]


class _serie_falsa:
    """Troca indices.carregar_serie_indice por uma lista fixa, e devolve depois."""

    def __init__(self, pontos):
        self.pontos = pontos

    def __enter__(self):
        self.original = indices.carregar_serie_indice
        indices.carregar_serie_indice = lambda *a, **k: self.pontos

    def __exit__(self, *erro):
        indices.carregar_serie_indice = self.original


if __name__ == "__main__":
    testes = [valor for nome, valor in sorted(globals().items())
              if nome.startswith("teste_")]

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

    print()
    print(f"{len(testes) - falhas}/{len(testes)} testes passaram")

    print()
    print(f"Tabela de conferencia manual -- premio contra Selic de {SELIC}% a.a.")
    print("Os P/L sao os da carteira real em 28/10/2026, mais as bordas.")
    print()
    print(f"{'P/L':>9s} {'e_yield':>9s} {'% a.a.':>9s} {'premio pp':>10s} "
          f"{'flag':>6s}  comentario")

    casos = [
        (5.10, "PETR4: paga quase 6 pontos acima da Selic"),
        (6.39, "ISAE4"),
        (6.74, "BBDC4"),
        (PL_NA_SELIC, "borda: empate exato com a Selic"),
        (8.12, "BBAS3: valuation 78/100 no grupo, e mesmo assim abaixo"),
        (9.47, "ITUB4"),
        (26.97, "VALE3"),
        (30.91, "WEGE3: o mais caro da lista"),
        (-8.00, "prejuizo: yield negativo, sempre abaixo"),
        (float("nan"), "sem P/L: ausente, nem verdadeiro nem falso"),
    ]
    for pl, comentario in casos:
        r = pontuar(X={"pl": pl})
        ey = r.loc["X", "earnings_yield"]
        premio = r.loc["X", "premio_selic_pp"]
        flag = r.loc["X", "premio_negativo"]
        if pd.isna(ey):
            print(f"{'-':>9s} {'-':>9s} {'-':>9s} {'-':>10s} {'<NA>':>6s}  "
                  f"{comentario}")
        else:
            marca = "SIM" if flag else "nao"
            print(f"{pl:9.2f} {ey:9.4f} {ey * 100:9.2f} {premio:10.2f} "
                  f"{marca:>6s}  {comentario}")

    print()
    print("A flag nao entra em nota nenhuma. Ela responde uma pergunta que o")
    print("z-score do valuation nao faz: o grupo inteiro pode estar caro, e")
    print("ainda assim alguem seria 'o mais barato do grupo'.")

    print()
    print("Tabela de conferencia manual -- anualizar taxa diaria:")
    print()
    print(f"{'% a.d.':>9s} {'compondo':>10s} {'x252':>10s} {'erro pp':>9s}")
    for diaria in (0.040000, 0.050788, 0.060000, 0.075000):
        composto = indices.anualizar_taxa_diaria(diaria)
        simples = diaria * 252
        print(f"{diaria:9.6f} {composto:10.2f} {simples:10.2f} "
              f"{composto - simples:9.2f}")

    print()
    print("Multiplicar por 252 subestima a Selic em quase um ponto. Com earnings")
    print("yield de 13%, isso sozinho inverte a flag.")
