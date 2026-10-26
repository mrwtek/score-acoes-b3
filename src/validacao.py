"""
Camada de sanidade dos indicadores fundamentalistas.

Por que existe: faixa absoluta transforma numero absurdo em nota confiante. A
ITSA4 chega da BolsAI com margem liquida de 212% -- impossivel, e artefato de
holding, cujo "lucro" vem de equivalencia patrimonial enquanto a "receita" e
quase nada. Pela faixa absoluta isso vira nota 100, a maxima. O min-max pelo
menos diluia o absurdo na escala do grupo; a faixa absoluta nao dilui nada.

O que esta camada faz: marca como AUSENTE o valor que nao pode ser verdade, em
vez de deixar virar nota. Dado ausente e problema conhecido e tratado (P1-13);
dado absurdo pontuado e problema invisivel.

O que esta camada NAO faz: adivinhar qual numero era o certo, nem corrigir
nada. Ela so separa "isso nao pode ser" de "isso e extremo mas possivel".

Criterio dos limites: so entra aqui o que e impossivel por definicao, nunca o
que e so incomum. Margem acima de 100% significa lucro maior que receita;
CAGR abaixo de -100% significaria receita negativa. Valor extremo porem
possivel (ROE de 82% da BBSE3, divida/PL de 5,1 do BBAS3) passa -- quem trata
extremo e a winsorizacao do P1-2, nao esta camada.
"""

import math

# (minimo, maximo) plausivel por indicador. Fora disso o valor vira ausente.
LIMITES_PLAUSIVEIS = {
    # ROE pode ser extremo quando o patrimonio e pequeno; so bloqueia o absurdo
    "roe": (-300.0, 300.0),
    # retorno sobre ativo/capital acima de 100% implicaria ativo menor que o lucro
    "roa": (-100.0, 100.0),
    "roic": (-100.0, 100.0),
    # margem acima de 100% = lucro maior que receita. Para baixo pode ser
    # muito negativa quando a receita e pequena, entao o piso e folgado
    "margem_liquida": (-500.0, 100.0),
    "margem_bruta": (-500.0, 100.0),
    "margem_ebitda": (-500.0, 100.0),
    # divida/PL negativa so acontece com patrimonio liquido negativo, que e
    # informacao real; o teto alto e so contra erro grosseiro
    "divida_patrimonio": (-50.0, 50.0),
    # CAGR abaixo de -100% exigiria receita/lucro negativo no fim
    "cagr_receita_5a": (-100.0, 500.0),
    "cagr_lucro_5a": (-100.0, 1000.0),
}

# Checagens que cruzam dois indicadores. Nao removem nada: quando os dois se
# contradizem nao da para saber qual esta errado, e chutar seria pior que
# avisar. Servem para aparecer no relatorio de cobertura.
#
# ROIC quase zero com ROE alto e o caso da ITSA4: ROIC de holding nao mede o
# que o nome diz, porque o capital empregado nao e operacional.
def _roic_incoerente_com_roe(valores):
    roic, roe = valores.get("roic"), valores.get("roe")
    if roic is None or roe is None:
        return None
    if roe > 10.0 and roic < 1.0:
        return f"ROIC de {roic:.2f}% com ROE de {roe:.2f}% -- incoerente, tipico de holding"
    return None


COERENCIAS = (_roic_incoerente_com_roe,)


def _ausente(valor):
    return valor is None or (isinstance(valor, float) and math.isnan(valor))


def validar_indicadores(valores):
    """Devolve (valores_limpos, descartados, avisos).

    `valores` e um dict {indicador: numero ou None}.
    `valores_limpos` tem None no lugar do que nao passou.
    `descartados` e {indicador: motivo}.
    `avisos` e uma lista de textos de incoerencia, sem nada removido.
    """
    limpos = {}
    descartados = {}

    for indicador, valor in valores.items():
        if _ausente(valor):
            limpos[indicador] = None
            continue

        try:
            numero = float(valor)
        except (TypeError, ValueError):
            limpos[indicador] = None
            descartados[indicador] = f"nao e numero: {valor!r}"
            continue

        if math.isinf(numero):
            limpos[indicador] = None
            descartados[indicador] = "infinito"
            continue

        limites = LIMITES_PLAUSIVEIS.get(indicador)
        if limites is not None:
            minimo, maximo = limites
            if not (minimo <= numero <= maximo):
                limpos[indicador] = None
                descartados[indicador] = (
                    f"{numero:.2f} fora da faixa plausivel [{minimo:.0f}, {maximo:.0f}]"
                )
                continue

        limpos[indicador] = numero

    avisos = []
    for checagem in COERENCIAS:
        aviso = checagem(limpos)
        if aviso is not None:
            avisos.append(aviso)

    return limpos, descartados, avisos


def validar_dataframe(df, indicadores=None):
    """Aplica validar_indicadores linha a linha de um DataFrame indexado por ticker.

    Devolve (df_limpo, relatorio), em que `relatorio` e
    {ticker: {"descartados": {...}, "avisos": [...]}} so para os tickers que
    tiveram alguma coisa. Ticker limpo nao aparece no relatorio.
    """
    indicadores = indicadores or [c for c in LIMITES_PLAUSIVEIS if c in df.columns]
    df = df.copy()
    relatorio = {}

    for ticker in df.index:
        valores = {ind: df.at[ticker, ind] for ind in indicadores}
        limpos, descartados, avisos = validar_indicadores(valores)

        for indicador, valor in limpos.items():
            df.at[ticker, indicador] = valor

        if descartados or avisos:
            relatorio[ticker] = {"descartados": descartados, "avisos": avisos}

    return df, relatorio


def imprimir_relatorio(relatorio):
    """Relatorio curto para quem roda o ranking no terminal."""
    if not relatorio:
        print("Sanidade dos indicadores: nada a relatar.")
        return

    print("Sanidade dos indicadores:")
    for ticker, achados in sorted(relatorio.items()):
        for indicador, motivo in sorted(achados["descartados"].items()):
            print(f"  {ticker:8s} {indicador:18s} DESCARTADO -- {motivo}")
        for aviso in achados["avisos"]:
            print(f"  {ticker:8s} {'(coerencia)':18s} aviso      -- {aviso}")
