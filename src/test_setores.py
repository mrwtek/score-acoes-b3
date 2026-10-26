"""Testes do mapa de setores (P1-12).

Roda sem pytest, no mesmo estilo dos outros scripts de teste do projeto:

    cd src && python test_setores.py

Sem banco e sem API.
"""

from whitelist import WHITELIST_BASE
import setores
from setores import (
    FINANCEIRO,
    FUNDO_IMOBILIARIO,
    SETOR_POR_TICKER,
    TODOS_INDICADORES,
    indicadores_nao_aplicaveis,
    nao_se_aplica,
    setor_de,
    tickers_sem_setor,
)


# --------------------------------------------------------------------------
# 1. O caso de aceite do P1-12
# --------------------------------------------------------------------------
def teste_01_banco_nao_pontua_alavancagem():
    assert nao_se_aplica("BBAS3", "divida_patrimonio"), (
        "BBAS3 ainda pontuaria divida/PL -- e o 0.0 em seguranca que o P1-12 "
        "existe para eliminar. Alavancagem e o modelo de negocio de um banco"
    )
    assert nao_se_aplica("ITUB4", "divida_patrimonio"), (
        "ITUB4 ainda pontuaria divida/PL de 0,00, que e ausencia disfarcada "
        "de zero virando nota 100 -- o mesmo ruido, pelo lado oposto"
    )


def teste_02_banco_nao_pontua_roa_nem_margens():
    for indicador in ("roa", "margem_liquida", "margem_bruta", "margem_ebitda"):
        assert nao_se_aplica("BBDC4", indicador), f"{indicador} deveria ser inaplicavel a banco"


def teste_03_banco_continua_pontuando_o_que_faz_sentido():
    for indicador in ("roe", "roic", "cagr_receita_5a", "cagr_lucro_5a"):
        assert not nao_se_aplica("BBAS3", indicador), (
            f"{indicador} se aplica a banco e nao pode ser excluido"
        )


# --------------------------------------------------------------------------
# 4. Classificacoes que nao sao obvias
# --------------------------------------------------------------------------
def teste_04_holding_de_banco_conta_como_financeira():
    assert setor_de("ITSA4") == FINANCEIRO, (
        "ITSA4 e holding cujo ativo principal e banco; tem o mesmo problema "
        "de balanco, e e dela a margem liquida de 212% que a validacao recusa"
    )


def teste_05_seguradora_conta_como_financeira():
    assert setor_de("BBSE3") == FINANCEIRO, (
        "o Piotroski exclui seguradoras junto com bancos, pela mesma razao"
    )


def teste_06_fii_nao_pontua_nenhum_indicador_fundamentalista():
    assert setor_de("MXRF11") == FUNDO_IMOBILIARIO
    assert indicadores_nao_aplicaveis("MXRF11") == TODOS_INDICADORES, (
        "FII nao tem balanco de empresa operacional; nenhum indicador se aplica"
    )


def teste_07_nao_financeira_pontua_tudo():
    for ticker in ("PETR4", "VALE3", "WEGE3", "ISAE4", "FIQE3"):
        assert indicadores_nao_aplicaveis(ticker) == frozenset(), (
            f"{ticker} nao e financeira nem FII; tudo deveria se aplicar"
        )


# --------------------------------------------------------------------------
# 8. Ticker desconhecido: o lado seguro do erro
# --------------------------------------------------------------------------
def teste_08_ticker_fora_do_mapa_nao_exclui_nada():
    assert setor_de("XXXX9") is None
    assert indicadores_nao_aplicaveis("XXXX9") == frozenset(), (
        "na duvida tem que pontuar tudo: pontuar demais aparece como numero "
        "estranho no ranking, pontuar de menos passa despercebido"
    )


def teste_09_ticker_e_normalizado_antes_da_busca():
    assert setor_de("  bbas3  ") == FINANCEIRO
    assert setor_de("petr4") is not None


def teste_10_tickers_sem_setor_lista_os_que_faltam():
    faltando = tickers_sem_setor(["PETR4", "XXXX9", "BBAS3", "ZZZZ3"])
    assert faltando == ["XXXX9", "ZZZZ3"]


# --------------------------------------------------------------------------
# 11. O mapa cobre o universo de verdade
# --------------------------------------------------------------------------
def teste_11_whitelist_base_esta_toda_mapeada():
    faltando = tickers_sem_setor(WHITELIST_BASE)
    assert faltando == [], f"tickers da WHITELIST_BASE sem setor: {faltando}"


def teste_12_nenhum_indicador_inventado_no_mapa_de_inaplicaveis():
    for setor, indicadores in setores.NAO_APLICAVEIS_POR_SETOR.items():
        desconhecidos = set(indicadores) - set(TODOS_INDICADORES)
        assert not desconhecidos, (
            f"setor {setor} lista indicador que o score nao conhece: {desconhecidos}"
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

    print("\nTabela de conferencia manual -- o que cada ticker pontua:\n")
    indicadores = sorted(TODOS_INDICADORES)
    cabecalho = "".join(f"{i[:6]:>8s}" for i in indicadores)
    print(f"{'ticker':9s} {'setor':18s}{cabecalho}")
    for ticker in sorted(SETOR_POR_TICKER):
        excluidos = indicadores_nao_aplicaveis(ticker)
        marcas = "".join(f"{('-' if i in excluidos else 'sim'):>8s}" for i in indicadores)
        print(f"{ticker:9s} {setor_de(ticker):18s}{marcas}")

    print("\n'-' = nao pontua (nota nenhuma, nem 0 nem neutra).")
    print("Quantos indicadores cada um pontua:")
    for ticker in sorted(SETOR_POR_TICKER):
        quantos = len(TODOS_INDICADORES) - len(indicadores_nao_aplicaveis(ticker))
        print(f"  {ticker:9s} {quantos} de {len(TODOS_INDICADORES)}")
