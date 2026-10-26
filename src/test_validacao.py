"""Testes da camada de sanidade dos indicadores.

Roda sem pytest, no mesmo estilo dos outros scripts de teste do projeto:

    cd src && python test_validacao.py

Dados sinteticos, sem banco e sem API.

O criterio sob teste e um so e vale a pena repetir: descartar o IMPOSSIVEL,
nunca o incomum. ROE de 82% e extremo e verdadeiro (BBSE3); margem de 212% e
impossivel (ITSA4). Um teste para cada lado dessa linha.
"""

import math

import pandas as pd

from validacao import (
    LIMITES_PLAUSIVEIS,
    imprimir_relatorio,
    validar_dataframe,
    validar_indicadores,
)


# --------------------------------------------------------------------------
# 1. O caso que motivou a camada
# --------------------------------------------------------------------------
def teste_01_margem_acima_de_100_e_descartada():
    limpos, descartados, _ = validar_indicadores({"margem_liquida": 212.0})

    assert limpos["margem_liquida"] is None, (
        "margem de 212% virou nota em vez de virar ausente -- lucro maior que "
        "receita e impossivel, e pela faixa absoluta isso daria nota 100"
    )
    assert "margem_liquida" in descartados


def teste_02_margem_normal_passa():
    limpos, descartados, _ = validar_indicadores({"margem_liquida": 24.88})
    assert limpos["margem_liquida"] == 24.88
    assert descartados == {}


def teste_03_margem_muito_negativa_passa():
    # prejuizo grande com receita pequena da margem muito negativa, e e real
    limpos, descartados, _ = validar_indicadores({"margem_liquida": -180.0})
    assert limpos["margem_liquida"] == -180.0, "margem muito negativa e possivel"
    assert descartados == {}


# --------------------------------------------------------------------------
# 4. A linha entre extremo e impossivel
# --------------------------------------------------------------------------
def teste_04_valor_extremo_porem_real_nao_e_descartado():
    # numeros reais da carteira em 14/09/2026
    valores = {
        "roe": 82.77,              # BBSE3, alto mas verdadeiro
        "divida_patrimonio": 5.13,  # BBAS3, alavancagem de banco
        "cagr_lucro_5a": 77.68,     # PETR4, ano-base deprimido
        "margem_ebitda": 51.15,     # PETR4
    }
    limpos, descartados, _ = validar_indicadores(valores)

    assert descartados == {}, (
        f"descartou valor extremo porem real: {descartados}. Tratar extremo e "
        f"trabalho da winsorizacao (P1-2), nao desta camada"
    )
    assert limpos == valores


def teste_05_roa_e_roic_acima_de_100_sao_descartados():
    limpos, descartados, _ = validar_indicadores({"roa": 150.0, "roic": 120.0})
    assert limpos["roa"] is None
    assert limpos["roic"] is None
    assert len(descartados) == 2


def teste_06_cagr_abaixo_de_menos_100_e_descartado():
    limpos, descartados, _ = validar_indicadores({"cagr_receita_5a": -140.0})
    assert limpos["cagr_receita_5a"] is None, "exigiria receita negativa no fim"
    assert "cagr_receita_5a" in descartados


# --------------------------------------------------------------------------
# 7. Ausente continua ausente, sem virar descarte
# --------------------------------------------------------------------------
def teste_07_none_e_nan_passam_como_ausentes_sem_motivo():
    limpos, descartados, _ = validar_indicadores({"roe": None, "roa": float("nan")})

    assert limpos["roe"] is None and limpos["roa"] is None
    assert descartados == {}, (
        "dado que ja chegou ausente nao e descarte -- so o que era numero e "
        "foi recusado conta como descartado"
    )


def teste_08_texto_e_infinito_sao_descartados():
    limpos, descartados, _ = validar_indicadores(
        {"roe": "muito bom", "roa": float("inf")}
    )
    assert limpos["roe"] is None and limpos["roa"] is None
    assert len(descartados) == 2


def teste_09_indicador_sem_limite_definido_passa_sem_checagem():
    limpos, descartados, _ = validar_indicadores({"pl": 9999.0})
    assert limpos["pl"] == 9999.0, "pl nao esta em LIMITES_PLAUSIVEIS"
    assert descartados == {}


# --------------------------------------------------------------------------
# 10. Coerencia entre indicadores: avisa, nao remove
# --------------------------------------------------------------------------
def teste_10_roic_incoerente_com_roe_gera_aviso():
    # numeros da ITSA4 em 14/09/2026
    limpos, descartados, avisos = validar_indicadores({"roic": 0.21, "roe": 18.83})

    assert len(avisos) == 1, f"esperava 1 aviso de coerencia, veio {avisos}"
    assert "holding" in avisos[0]
    assert limpos["roic"] == 0.21, (
        "o aviso nao pode remover o valor: com dois indicadores se contradizendo "
        "nao da para saber qual esta errado, e chutar e pior que avisar"
    )
    assert descartados == {}


def teste_11_roic_baixo_com_roe_baixo_nao_gera_aviso():
    _, _, avisos = validar_indicadores({"roic": 0.5, "roe": 2.0})
    assert avisos == [], "ROIC baixo com ROE baixo e so empresa ruim, nao incoerencia"


def teste_12_roic_alto_nao_gera_aviso():
    _, _, avisos = validar_indicadores({"roic": 19.72, "roe": 28.26})  # PETR4
    assert avisos == []


# --------------------------------------------------------------------------
# 13. Aplicacao sobre DataFrame
# --------------------------------------------------------------------------
def teste_13_dataframe_limpa_so_o_que_precisa():
    df = pd.DataFrame(
        {"roe": [18.83, 28.26], "margem_liquida": [212.0, 24.88], "roic": [0.21, 19.72]},
        index=["ITSA4", "PETR4"],
    )

    limpo, relatorio = validar_dataframe(df)

    assert math.isnan(limpo.at["ITSA4", "margem_liquida"]), "212% tinha que sair"
    assert limpo.at["PETR4", "margem_liquida"] == 24.88, "PETR4 nao podia ser tocada"
    assert limpo.at["ITSA4", "roic"] == 0.21, "aviso de coerencia nao remove valor"

    assert "PETR4" not in relatorio, "ticker limpo nao aparece no relatorio"
    assert "margem_liquida" in relatorio["ITSA4"]["descartados"]
    assert len(relatorio["ITSA4"]["avisos"]) == 1


def teste_14_dataframe_sem_problema_nao_gera_relatorio():
    df = pd.DataFrame({"roe": [28.26], "margem_liquida": [24.88]}, index=["PETR4"])
    _, relatorio = validar_dataframe(df)
    assert relatorio == {}


def teste_15_original_nao_e_modificado():
    df = pd.DataFrame({"margem_liquida": [212.0]}, index=["ITSA4"])
    validar_dataframe(df)
    assert df.at["ITSA4", "margem_liquida"] == 212.0, (
        "validar_dataframe alterou o DataFrame de entrada"
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

    print("\nTabela de conferencia manual -- o que passa e o que nao passa:\n")
    casos = [
        ("roe", 82.77, "BBSE3 real"),
        ("roe", 350.0, "absurdo"),
        ("roa", 41.12, "BBSE3 real"),
        ("roa", 150.0, "ativo menor que o lucro"),
        ("margem_liquida", 24.88, "PETR4 real"),
        ("margem_liquida", -180.0, "prejuizo com receita pequena"),
        ("margem_liquida", 212.0, "ITSA4 -- lucro maior que receita"),
        ("divida_patrimonio", 5.13, "BBAS3 real, banco"),
        ("cagr_lucro_5a", 77.68, "PETR4, ano-base deprimido"),
        ("cagr_receita_5a", -140.0, "receita negativa no fim"),
    ]
    print(f"{'indicador':18s} {'valor':>9s}  {'destino':11s} comentario")
    for indicador, valor, comentario in casos:
        limpos, descartados, _ = validar_indicadores({indicador: valor})
        destino = "DESCARTADO" if indicador in descartados else "passa"
        print(f"{indicador:18s} {valor:9.2f}  {destino:11s} {comentario}")

    print("\nLimites em vigor:")
    for indicador, (minimo, maximo) in sorted(LIMITES_PLAUSIVEIS.items()):
        print(f"  {indicador:18s} [{minimo:8.0f}, {maximo:8.0f}]")

    print("\nRelatorio de exemplo:")
    exemplo = pd.DataFrame(
        {"roe": [18.83], "margem_liquida": [212.0], "roic": [0.21]}, index=["ITSA4"]
    )
    imprimir_relatorio(validar_dataframe(exemplo)[1])
