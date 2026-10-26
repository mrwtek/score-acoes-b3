"""
Faixas absolutas dos indicadores (P1-11). PRD secao 7A.3 a 7A.6.

A NOTA DEPENDE SO DO VALOR, nunca de quem esta na whitelist. ROE de 18% vale
80 hoje e vale 80 em dezembro, com 10 ou com 30 tickers na lista. E isso que
torna os snapshots comparaveis no tempo -- o objetivo O1 do produto. Com
min-max, uma nota caindo de 76 para 62 nao distinguia "a empresa piorou" de
"entrou gente melhor na lista".

Valuation NAO esta aqui: continua relativo ao universo, porque "caro" so
existe em comparacao. Ver scoring.py.

INTERPOLADO, NAO EM DEGRAUS
---------------------------
A 7A define as faixas como degraus: ROE de 15 a 20 vale 80, de 20 para cima
vale 100. Implementado assim, ROE 19,9 vale 80 e ROE 20,1 vale 100 -- 20
pontos de diferenca por 0,2 ponto de ROE, enquanto a mesma variacao no meio da
faixa vale zero.

Isso e ruim justamente para o O1. Acompanhando a empresa no tempo, voce nao
conseguiria separar "a empresa mudou" de "a empresa cruzou uma linha
arbitraria". Medido na carteira real em 26/10/2026, a ITUB4 estava a 2,38 p.p.
de uma borda que valia 10 pontos de score.

Entao as faixas da 7A viram ANCORAS e o meio e interpolado em linha reta. As
notas nas ancoras sao exatamente as da 7A; o que muda e que entre elas a nota
varia de forma continua. ROE 17,5 vira 90 em vez de 80.

ANCORAGEM AO CUSTO DE CAPITAL BRASILEIRO (7A.2)
-----------------------------------------------
As faixas nao sao copiadas de tabela americana. ROE de 12% nos EUA e
aceitavel; aqui, com Selic de dois digitos, e empresa que rende menos que
titulo publico sem o risco de acao.
"""

# Referencias macro que ancoram as faixas. Nao sao usadas no calculo ainda --
# estao aqui para a revisao das faixas ser uma decisao consciente, e nao um
# numero magico espalhado pelo codigo (7A.2).
#
# Selic meta de 01/10/2026, serie 4189 do SGS/BCB. A serie diaria ja esta na
# tabela `indices`, entao da para conferir se saiu do lugar.
# Pendencia Q8 do PRD: com que gatilho revisar as faixas quando a Selic mudar.
SELIC_REFERENCIA = 13.65
INFLACAO_REFERENCIA = 4.5

# Teto do CAGR de lucro (7A.5). Se o ano-base teve lucro perto de zero, o CAGR
# explode: empresa que saiu de R$ 1 mi para R$ 50 mi aparece como crescimento
# espetacular quando so normalizou. A PETR4 chega com 77,68% por esse motivo.
#
# A 7A pede tambem DESCARTAR o valor quando o lucro do ano-base for <= 0. Isso
# NAO e implementavel: a BolsAI devolve o CAGR pronto, sem o lucro do ano-base.
# Fica o teto, que trata o sintoma, e a limitacao registrada no ESTADO.md.
CAP_CAGR_LUCRO = 30.0

# Ancoras (valor do indicador, nota). Sempre em ordem crescente de valor.
# Abaixo da primeira ancora vale a nota dela; acima da ultima, a da ultima.
#
# Onde a 7A diz "<X = 0" sem dizer onde a reta encosta no zero, a ancora de
# baixo foi escolhida para a interpolacao ficar continua, em vez de criar um
# degrau novo. Esse e o unico ponto em que este modulo vai alem da 7A, e vale
# para roe, roa, margem_liquida e os dois CAGR.
FAIXAS = {
    # 7A.3 rentabilidade
    "roe": ((-10.0, 0.0), (0.0, 10.0), (5.0, 30.0), (10.0, 55.0), (15.0, 80.0), (20.0, 100.0)),
    "roa": ((-5.0, 0.0), (0.0, 10.0), (2.0, 30.0), (5.0, 55.0), (8.0, 80.0), (12.0, 100.0)),
    # ROIC abaixo do custo de capital significa que a empresa DESTROI valor ao
    # crescer. No Brasil esse custo e alto, entao 5-10% ja e alerta.
    "roic": ((0.0, 0.0), (5.0, 25.0), (10.0, 55.0), (15.0, 80.0), (20.0, 100.0)),

    # 7A.4 margens. margem_bruta saiu do score (continua no banco): e o
    # indicador mais dependente de setor do conjunto -- 25% e otimo para
    # varejo e pessimo para software.
    "margem_liquida": ((-10.0, 0.0), (0.0, 10.0), (3.0, 30.0), (7.0, 55.0), (12.0, 80.0), (20.0, 100.0)),
    "margem_ebitda": ((0.0, 0.0), (5.0, 25.0), (12.0, 55.0), (20.0, 80.0), (30.0, 100.0)),

    # 7A.5 crescimento. Receita pesa mais que lucro por ser menos manipulavel
    # contabilmente (o peso esta no scoring.py).
    "cagr_receita_5a": ((-10.0, 0.0), (0.0, 25.0), (5.0, 55.0), (10.0, 80.0), (15.0, 100.0)),
    "cagr_lucro_5a": ((-10.0, 0.0), (0.0, 25.0), (5.0, 55.0), (10.0, 80.0), (15.0, 100.0)),

    # 7A.6 seguranca. MENOR e melhor, entao as notas descem conforme o valor
    # sobe -- a interpolacao nao precisa saber disso, so seguir as ancoras.
    "divida_patrimonio": ((0.3, 100.0), (0.6, 80.0), (1.0, 60.0), (2.0, 35.0), (3.0, 15.0), (4.0, 0.0)),
}


def interpolar(ancoras, valor):
    """Nota do valor na curva definida pelas ancoras, em linha reta entre elas."""
    primeiro_x, primeira_nota = ancoras[0]
    if valor <= primeiro_x:
        return primeira_nota

    ultimo_x, ultima_nota = ancoras[-1]
    if valor >= ultimo_x:
        return ultima_nota

    for (x0, y0), (x1, y1) in zip(ancoras, ancoras[1:]):
        if x0 <= valor <= x1:
            if x1 == x0:
                return y1
            return y0 + (y1 - y0) * (valor - x0) / (x1 - x0)

    # inalcancavel com ancoras ordenadas; fica como rede
    return ultima_nota


def nota(indicador, valor):
    """Nota 0-100 do indicador, ou None se nao der para pontuar.

    Devolve None para valor ausente e para indicador sem faixa definida --
    nunca um numero inventado. Quem trata ausencia e o scoring (P1-13).
    """
    if valor is None or valor != valor:  # None ou NaN
        return None

    ancoras = FAIXAS.get(indicador)
    if ancoras is None:
        return None

    valor = float(valor)

    if indicador == "cagr_lucro_5a":
        valor = min(valor, CAP_CAGR_LUCRO)

    # Patrimonio liquido negativo deixa a razao divida/PL negativa, e o sinal
    # inverte o significado: nao e "pouca divida", e empresa sem patrimonio.
    # A 7A manda nota 0 (nao "nota maxima por estar perto de zero").
    if indicador == "divida_patrimonio" and valor < 0:
        return 0.0

    return interpolar(ancoras, valor)


def indicadores_com_faixa():
    return frozenset(FAIXAS)
