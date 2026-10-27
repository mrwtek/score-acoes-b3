"""Testes das faixas absolutas (P1-11).

Roda sem pytest, no mesmo estilo dos outros scripts de teste do projeto:

    cd src && python test_faixas.py

Dados sinteticos, sem banco e sem API.
"""

from faixas import (
    CAP_CAGR_LUCRO,
    FAIXAS,
    INDICADORES_REAIS,
    INFLACAO_REFERENCIA,
    SELIC_REFERENCIA,
    deflacionar,
    interpolar,
    nota,
)


def nominal(real, inflacao=INFLACAO_REFERENCIA):
    """Inversa de deflacionar(): o CAGR nominal que vira `real` no extrato."""
    return ((1 + real / 100) * (1 + inflacao / 100) - 1) * 100


def perto(a, b, tol=1e-6):
    return abs(a - b) < tol


# --------------------------------------------------------------------------
# 1. As ancoras batem exatamente com a tabela da 7A
# --------------------------------------------------------------------------
def teste_01_ancoras_da_7a3_rentabilidade():
    assert nota("roe", 20.0) == 100.0
    assert nota("roe", 15.0) == 80.0
    assert nota("roe", 10.0) == 55.0
    assert nota("roe", 5.0) == 30.0
    assert nota("roe", 0.0) == 10.0

    assert nota("roa", 12.0) == 100.0
    assert nota("roa", 8.0) == 80.0
    assert nota("roa", 5.0) == 55.0

    assert nota("roic", 20.0) == 100.0
    assert nota("roic", 15.0) == 80.0
    assert nota("roic", 10.0) == 55.0
    assert nota("roic", 5.0) == 25.0


def teste_02_ancoras_da_7a4_margens_e_7a5_crescimento():
    assert nota("margem_liquida", 20.0) == 100.0
    assert nota("margem_liquida", 12.0) == 80.0
    assert nota("margem_ebitda", 30.0) == 100.0
    assert nota("margem_ebitda", 20.0) == 80.0

    # As ancoras de crescimento estao em termos REAIS e a entrada e nominal,
    # entao a conferencia passa por nominal(): 15% real = 21,09% no extrato.
    for indicador in ("cagr_receita_5a", "cagr_lucro_5a"):
        assert perto(nota(indicador, nominal(15.0)), 100.0)
        assert perto(nota(indicador, nominal(10.0)), 80.0)
        assert perto(nota(indicador, nominal(5.0)), 55.0)
        assert perto(nota(indicador, nominal(0.0)), 25.0)


def teste_03_ancoras_da_7a6_seguranca_sao_decrescentes():
    assert nota("divida_patrimonio", 0.3) == 100.0
    assert nota("divida_patrimonio", 0.6) == 80.0
    assert nota("divida_patrimonio", 1.0) == 60.0
    assert nota("divida_patrimonio", 2.0) == 35.0
    assert nota("divida_patrimonio", 3.0) == 15.0


# --------------------------------------------------------------------------
# 4. O ponto do P1-11: interpolado, nao em degraus
# --------------------------------------------------------------------------
def teste_04_meio_da_faixa_fica_no_meio_da_nota():
    # ROE 17,5 esta na metade entre 15 (nota 80) e 20 (nota 100)
    assert nota("roe", 17.5) == 90.0, (
        "caiu no degrau: ROE 17,5 valeria 80, igual a ROE 15,1"
    )
    assert nota("roe", 12.5) == 67.5


def teste_05_nao_existe_salto_na_borda():
    antes = nota("roe", 19.99)
    depois = nota("roe", 20.01)

    assert abs(depois - antes) < 0.1, (
        f"0,02 ponto de ROE mudou a nota em {depois - antes:.1f}. Era esse "
        f"penhasco que o P1-11 veio tirar"
    )


def teste_06_variacoes_iguais_movem_a_nota_de_forma_parecida():
    # dentro da mesma faixa, 1 p.p. de ROE sempre vale o mesmo
    passo_baixo = nota("roe", 16.0) - nota("roe", 15.0)
    passo_alto = nota("roe", 19.0) - nota("roe", 18.0)

    assert abs(passo_baixo - passo_alto) < 1e-9
    assert passo_baixo > 0


def teste_07_a_curva_e_monotona():
    """Dentro do dominio valido, mais indicador nunca pode valer menos nota.

    `divida_patrimonio` fica de fora do trecho negativo de proposito: razao
    negativa vem de patrimonio liquido negativo, o sinal inverte o significado
    e a nota cai para 0 (teste 11). E descontinuidade deliberada, nao falha de
    monotonia -- -0,5 nao e "menos divida que 0,1".
    """
    for indicador, ancoras in FAIXAS.items():
        crescente = ancoras[0][1] < ancoras[-1][1]
        anterior = None
        inicio = 0.0 if indicador == "divida_patrimonio" else ancoras[0][0] - 5
        valor = inicio
        while valor <= ancoras[-1][0] + 5:
            atual = nota(indicador, valor)
            if anterior is not None:
                if crescente:
                    assert atual >= anterior - 1e-9, f"{indicador} desceu em {valor}"
                else:
                    assert atual <= anterior + 1e-9, f"{indicador} subiu em {valor}"
            anterior = atual
            valor += 0.25


# --------------------------------------------------------------------------
# 8. Fora das pontas
# --------------------------------------------------------------------------
def teste_08_acima_da_ultima_ancora_fica_no_teto():
    assert nota("roe", 82.77) == 100.0, "ROE da BBSE3, extremo e real"
    assert nota("margem_ebitda", 51.15) == 100.0, "margem da PETR4"


def teste_09_abaixo_da_primeira_ancora_fica_no_piso():
    assert nota("roe", -50.0) == 0.0
    assert nota("roic", -20.0) == 0.0
    assert nota("divida_patrimonio", 0.1) == 100.0, (
        "pouca divida e o melhor caso: a curva de seguranca desce, nao sobe"
    )
    assert nota("divida_patrimonio", 10.0) == 0.0


def teste_10_divida_alta_de_banco_tira_zero():
    # BBAS3 tinha 5,13. Nao pontua por ser financeira (P1-12), mas se
    # pontuasse teria que ser 0, nao nota alta
    assert nota("divida_patrimonio", 5.13) == 0.0


# --------------------------------------------------------------------------
# 11. Casos especiais
# --------------------------------------------------------------------------
def teste_11_patrimonio_liquido_negativo_tira_zero():
    assert nota("divida_patrimonio", -0.5) == 0.0, (
        "razao negativa vem de patrimonio negativo; o sinal inverte o "
        "significado e nao pode virar 'pouca divida'"
    )


def teste_12_cagr_de_lucro_e_capado():
    """O cap existe, mas HOJE nao muda nota nenhuma -- ver teste 23."""
    assert nota("cagr_lucro_5a", 77.68) == nota("cagr_lucro_5a", CAP_CAGR_LUCRO)
    assert nota("cagr_lucro_5a", 77.68) == 100.0, (
        "o CAGR de 77,68% da PETR4 vem de ano-base deprimido"
    )


def teste_13_cagr_de_receita_nao_e_capado_pelo_teto_do_lucro():
    # receita nao explode do mesmo jeito; so o teto natural da ancora vale.
    # 26,49% nominal da BBAS3 = 20,12% real, acima da ancora de 15% real.
    assert nota("cagr_receita_5a", 26.49) == 100.0, "BBAS3 real"


def teste_14_ausente_vira_none_e_nunca_nota():
    assert nota("roe", None) is None
    assert nota("roe", float("nan")) is None


def teste_15_indicador_sem_faixa_vira_none():
    assert nota("margem_bruta", 30.86) is None, (
        "margem_bruta saiu do score na 7A.4: e o indicador mais dependente de "
        "setor do conjunto e so adiciona ruido"
    )
    assert nota("inventado", 10.0) is None


# --------------------------------------------------------------------------
# 16. O aceite do P1-11
# --------------------------------------------------------------------------
def teste_16_a_nota_nao_depende_de_quem_mais_esta_na_lista():
    # a funcao nem recebe o universo: e esse o ponto
    assert nota("roe", 13.65) == nota("roe", 13.65)
    assert nota("roe", 13.65) == 73.25, (
        "o BBDC4 tem ROE 13,65; a nota dele e essa com 10 ou com 30 tickers "
        "na whitelist, e continua essa em dezembro"
    )


def teste_17_interpolar_funciona_sozinha():
    ancoras = ((0.0, 0.0), (10.0, 100.0))
    assert interpolar(ancoras, 0.0) == 0.0
    assert interpolar(ancoras, 5.0) == 50.0
    assert interpolar(ancoras, 10.0) == 100.0
    assert interpolar(ancoras, -3.0) == 0.0
    assert interpolar(ancoras, 99.0) == 100.0


def teste_18_referencias_macro_estao_declaradas():
    assert SELIC_REFERENCIA > 0, "7A.2 pede a ancora explicita, nao numero magico"
    assert CAP_CAGR_LUCRO == 30.0
    assert INFLACAO_REFERENCIA == 5.30, (
        "IPCA medio de 5 anos, serie 433 do SGS/BCB (out/2021 a set/2026). "
        "Era 4,5 chutado; se mudar aqui, toda nota de crescimento se move"
    )


# --------------------------------------------------------------------------
# 19 a 23. Correcao pela inflacao (opcao A, 26/10/2026)
# --------------------------------------------------------------------------
def teste_19_empatar_com_a_inflacao_nao_e_crescer():
    """O caso que motivou a mudanca inteira.

    Empresa cuja receita subiu exatamente a inflacao esta parada em termos
    reais. A 7A.2 chama isso de encolhimento; a regua nominal dava 56,5.
    """
    assert perto(nota("cagr_receita_5a", INFLACAO_REFERENCIA), 25.0), (
        "crescer o tanto da inflacao voltou a valer nota de aprovacao"
    )
    # e ficar abaixo da inflacao vale menos ainda
    assert nota("cagr_receita_5a", 2.0) < 25.0


def teste_20_deflacionar_nao_e_subtrair():
    # 21,09% nominal com 5,30% de inflacao da 15,00% real, nao 15,79%
    assert perto(deflacionar(21.09), 15.0, tol=0.01)
    assert deflacionar(21.09) < 21.09 - INFLACAO_REFERENCIA, (
        "a conta virou subtracao: os dois percentuais compoem"
    )
    assert deflacionar(INFLACAO_REFERENCIA) == 0.0 or perto(
        deflacionar(INFLACAO_REFERENCIA), 0.0)
    # ausente continua ausente
    assert deflacionar(None) is None
    assert deflacionar(float("nan")) != deflacionar(float("nan"))


def teste_21_so_crescimento_e_deflacionado():
    """Razoes do mesmo periodo nao levam inflacao: ela se cancela."""
    assert INDICADORES_REAIS == ("cagr_receita_5a", "cagr_lucro_5a")

    assert nota("roe", 15.0) == 80.0, "ROE foi deflacionado e nao devia"
    assert nota("roa", 8.0) == 80.0
    assert nota("roic", 15.0) == 80.0
    assert nota("margem_liquida", 12.0) == 80.0
    assert nota("margem_ebitda", 20.0) == 80.0
    assert nota("divida_patrimonio", 0.6) == 80.0


def teste_22_a_nota_de_crescimento_continua_sem_olhar_o_universo():
    """O aceite do P1-11 nao pode ter sido quebrado pela correcao.

    Deflacionar usa uma constante, nao o universo. Se um dia alguem trocar
    INFLACAO_REFERENCIA por uma media da whitelist, este teste nao pega --
    mas o teste_24 do test_scoring.py pega.
    """
    assert nota("cagr_receita_5a", 18.49) == nota("cagr_receita_5a", 18.49)
    assert perto(nota("cagr_receita_5a", 18.49), 90.10, tol=0.01), (
        "WEGE3 cresceu 18,49% nominal = 12,53% real. Essa nota vale com 10 ou "
        "com 30 tickers na lista, e continua valendo em dezembro"
    )


def teste_23_o_cap_do_lucro_hoje_nao_muda_nota_nenhuma():
    """Registra uma verdade incomoda, para ninguem confiar no que nao protege.

    O cap e 30% REAL e a ancora de cima e 15% REAL. Tudo acima de 15 ja tira
    100, entao cortar 68% para 30% nao altera resultado. O cap so passaria a
    valer se alguem subisse a ancora de cima acima de 30.
    """
    sem_cap = interpolar(FAIXAS["cagr_lucro_5a"], deflacionar(77.68))
    com_cap = nota("cagr_lucro_5a", 77.68)
    assert sem_cap == com_cap == 100.0, (
        "se estes passarem a divergir, o cap virou logica de verdade e o "
        "comentario do faixas.py precisa parar de chamar ele de protecao"
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

    print("\nTabela de conferencia manual -- degrau vs interpolado:\n")

    def nota_em_degrau(indicador, valor):
        """Como a 7A ficaria implementada ao pe da letra."""
        escolhida = 0.0
        for x, y in FAIXAS[indicador]:
            if valor >= x:
                escolhida = y
        return escolhida

    print(f"{'ROE %':>7s} {'degrau':>8s} {'interpolado':>12s} {'diferenca':>10s}")
    for roe in (9.9, 10.0, 12.5, 14.9, 15.0, 17.5, 19.9, 20.0, 20.1):
        degrau = nota_em_degrau("roe", roe)
        suave = nota("roe", roe)
        print(f"{roe:7.1f} {degrau:8.1f} {suave:12.1f} {suave - degrau:+10.1f}")

    print("\nNote 14,9 -> 15,0: no degrau a nota pula 25 pontos por 0,1 de ROE.")
    print("Interpolado, a mesma variacao vale meio ponto de nota.")

    print("\n\nTabela de conferencia manual -- nominal vs real no crescimento:\n")
    print(f"IPCA de referencia: {INFLACAO_REFERENCIA:.2f}% ao ano\n")
    print(f"{'nominal':>9s} {'real':>8s} {'antes':>8s} {'agora':>8s} {'dif':>7s}")
    for nom in (0.0, 2.0, 5.30, 8.0, 10.0, 15.0, 18.49, 21.09, 26.49, 32.89):
        real = deflacionar(nom)
        antes = interpolar(FAIXAS["cagr_receita_5a"], nom)  # como era: nominal direto
        agora = nota("cagr_receita_5a", nom)
        print(f"{nom:8.2f}% {real:7.2f}% {antes:8.1f} {agora:8.1f} {agora - antes:+7.1f}")

    print("\nA linha de 5,30% e o motivo da mudanca: crescer o tanto da")
    print("inflacao e ficar parado, e isso tirava 56,5 de nota.")

    print("\n\nIndicadores da carteira real em 14/09/2026:\n")
    reais = [
        ("BBAS3", "roe", 7.15), ("BBAS3", "roic", 4.29), ("BBAS3", "cagr_receita_5a", 26.49),
        ("BBDC4", "roe", 13.65), ("BBDC4", "roic", 7.16), ("BBDC4", "cagr_lucro_5a", 8.33),
        ("PETR4", "roe", 28.26), ("PETR4", "roic", 19.72), ("PETR4", "cagr_lucro_5a", 77.68),
        ("VALE3", "roe", 4.36), ("VALE3", "cagr_receita_5a", 0.48),
        ("WEGE3", "roic", 37.97), ("WEGE3", "divida_patrimonio", 0.27),
        ("ITSA4", "divida_patrimonio", 0.11), ("ISAE4", "divida_patrimonio", 0.80),
    ]
    print(f"{'ticker':8s} {'indicador':18s} {'valor':>8s} {'nota':>7s}")
    for ticker, indicador, valor in reais:
        print(f"{ticker:8s} {indicador:18s} {valor:8.2f} {nota(indicador, valor):7.1f}")
