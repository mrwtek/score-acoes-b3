"""
Setor por ticker e quais indicadores nao se aplicam a cada setor (P1-12).

Este modulo so RESPONDE perguntas; nao pontua nada. Quem usa e o scoring,
no P1-13.

Por que um mapa escrito a mao em vez de vir da API: nem a brapi nem a BolsAI
entregam setor nas respostas que o projeto consome. Com 10 a 30 tickers, um
dicionario versionado e mais simples, mais legivel e mais confiavel do que
mais uma dependencia de rede -- e setor de empresa quase nunca muda.

Por que isso importa: alavancagem e o modelo de negocio de um banco, nao um
defeito. ROA de banco e estruturalmente baixo (1-2% e normal). Banco nao tem
EBITDA no sentido usual. Pontuar esses indicadores para financeira nao mede
qualidade, mede o setor -- e vira ruido puro na ordenacao.

Sintoma concreto que motivou: no ranking atual BBAS3 tira 0.0 em seguranca
(divida/PL 5,13) e ITUB4 tira 100.0 (divida/PL 0,00). Nenhum dos dois numeros
diz nada sobre a empresa. O primeiro e alavancagem normal de banco; o segundo
e quase certamente ausencia disfarcada de zero.

Referencia: o Piotroski F-Score exclui explicitamente bancos, seguradoras e
REITs, pela mesma razao -- estrutura de balanco fundamentalmente diferente.
Ver PRD secao 7A.3, 7A.4 e 7A.6, e DECISOES.md de 03/09/2026.
"""

FINANCEIRO = "financeiro"
FUNDO_IMOBILIARIO = "fundo_imobiliario"
ENERGIA = "energia"
MINERACAO = "mineracao"
PETROLEO = "petroleo"
TELECOM = "telecom"
BENS_INDUSTRIAIS = "bens_industriais"

# Mapa explicito. Ticker novo na whitelist precisa entrar aqui: sem setor, o
# codigo nao exclui nada e avisa, o que e o lado seguro do erro -- pontuar
# demais e visivel no ranking, pontuar de menos passa despercebido.
SETOR_POR_TICKER = {
    # bancos
    "BBAS3": FINANCEIRO,
    "BBDC4": FINANCEIRO,
    "ITUB4": FINANCEIRO,
    # holding cujo ativo principal e banco; mesmo problema de balanco
    "ITSA4": FINANCEIRO,
    # seguradora -- o Piotroski exclui junto com bancos
    "BBSE3": FINANCEIRO,

    "PETR4": PETROLEO,
    "VALE3": MINERACAO,
    "WEGE3": BENS_INDUSTRIAIS,
    "ISAE4": ENERGIA,
    "FIQE3": TELECOM,

    # FIIs: nao tem balanco de empresa operacional. Hoje a BolsAI nem devolve
    # fundamento para eles, mas deixar explicito evita que um dia entrem no
    # score por acidente. Suporte de verdade a FII e o P3-7.
    "MXRF11": FUNDO_IMOBILIARIO,
    "GARE11": FUNDO_IMOBILIARIO,
    "BTCI11": FUNDO_IMOBILIARIO,
}

# Todos os indicadores fundamentalistas que o score conhece. Serve de base
# para o caso do FII, em que nenhum se aplica.
TODOS_INDICADORES = frozenset({
    "roe", "roa", "roic",
    "margem_liquida", "margem_bruta", "margem_ebitda",
    "cagr_receita_5a", "cagr_lucro_5a",
    "divida_patrimonio",
})

NAO_APLICAVEIS_POR_SETOR = {
    FINANCEIRO: frozenset({
        "roa",                 # estruturalmente baixo por causa da alavancagem
        "margem_liquida",      # banco nao tem "receita" comparavel a de operacional
        "margem_bruta",
        "margem_ebitda",       # banco nao tem EBITDA no sentido usual
        "divida_patrimonio",   # alavancagem e o negocio, nao um defeito
    }),
    FUNDO_IMOBILIARIO: TODOS_INDICADORES,
}


def setor_de(ticker):
    """Setor do ticker, ou None se ele nao estiver no mapa."""
    return SETOR_POR_TICKER.get(str(ticker).strip().upper())


def indicadores_nao_aplicaveis(ticker):
    """Conjunto de indicadores que nao devem pontuar para este ticker.

    Ticker sem setor conhecido devolve conjunto vazio: na duvida, pontua tudo
    e deixa o numero estranho aparecer, em vez de sumir com ele em silencio.
    """
    setor = setor_de(ticker)
    if setor is None:
        return frozenset()
    return NAO_APLICAVEIS_POR_SETOR.get(setor, frozenset())


def nao_se_aplica(ticker, indicador):
    return indicador in indicadores_nao_aplicaveis(ticker)


def tickers_sem_setor(tickers):
    """Quais dos tickers dados nao estao no mapa. Para avisar no terminal."""
    return sorted(t for t in tickers if setor_de(t) is None)
