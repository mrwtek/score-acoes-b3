"""
Calculo dos scores. Extraido do analise.py no P1-1.

As funcoes daqui NAO leem o banco: recebem DataFrames prontos e devolvem
DataFrames. Quem carrega e o analise.py.

A separacao existe para o bloco que vem a seguir (P1-11 a P1-2), que reescreve
o miolo do calculo e pede teste com dados sinteticos em cada mudanca. Com os
dados entrando por parametro, conferir "ROE de 18% vira nota 80" e montar uma
tabela de tres linhas na mao, sem banco temporario e sem depender de quais
tickers estao na whitelist hoje.

ATENCAO antes de mexer: a metodologia vigente esta na secao 7A do PRD e no
DECISOES.md. O bloco de migracao
P1-11 -> P1-12 -> P1-13 -> P1-2 -> P1-14 esta TODO implementado aqui: faixas
absolutas fora do valuation, margens como categoria propria, margem_bruta fora
do score, score_geral removido, winsorizacao + z-score + CDF no relativo e a
flag de premio sobre a Selic.
"""

import math

import numpy as np
import pandas as pd

import faixas
import setores

# Peso de cada indicador dentro da sua categoria (PRD 7A.3 a 7A.7).
#
# ROIC pesa mais que ROE porque mede retorno sobre o capital total empregado,
# entao nao e inflado por alavancagem. Receita pesa mais que lucro porque e
# bem menos manipulavel contabilmente.
#
# margem_bruta NAO esta aqui: saiu do score no P1-11 (7A.4). A coluna continua
# no banco, sem custo. E o indicador mais dependente de setor do conjunto --
# 25% e otimo para varejo e pessimo para software -- e sem ajuste setorial nao
# informa nada comparavel entre VALE3 e ITUB4.
PESOS_INDICADOR = {
    "valuation": {"earnings_yield": 0.50, "book_to_market": 0.50},
    "rentabilidade": {"roic": 0.40, "roe": 0.35, "roa": 0.25},
    "margens": {"margem_liquida": 0.60, "margem_ebitda": 0.40},
    "crescimento": {"cagr_receita_5a": 0.60, "cagr_lucro_5a": 0.40},
    "seguranca": {"divida_patrimonio": 1.00},
}

# Categorias com FAIXA ABSOLUTA: a nota sai do valor do indicador, pelas
# ancoras do faixas.py, e nao depende de quem esta na whitelist.
CATEGORIAS_ABSOLUTAS = ("rentabilidade", "margens", "crescimento", "seguranca")

# Valuation e a excecao, e continua RELATIVA ao universo: "caro" so existe em
# comparacao. Desde o P1-2: winsorizacao + z-score + CDF, em nota_relativa().
CATEGORIAS_RELATIVAS = ("valuation",)

# Percentis de corte da winsorizacao (P1-2). Valor fora da faixa nao e
# descartado -- e puxado ate a borda, continuando a ser o extremo da serie sem
# ancorar a escala dos outros. Quem descarta o impossivel e o validacao.py;
# aqui o valor e plausivel, so esta longe.
#
# Com a whitelist de hoje (10 tickers) isto corta exatamente 2 valores, o
# minimo e o maximo, e so parcialmente -- p5 de 10 pontos cai entre o 1o e o
# 2o. O efeito cresce junto com a whitelist (P1-8).
PERCENTIL_WINSOR = 0.05

# Direcao das metricas relativas. As absolutas nao precisam disso: a direcao
# ja esta na ordem das notas das ancoras.
MAIOR_MELHOR = {"earnings_yield": True, "book_to_market": True}

CATEGORIAS_FUNDAMENTALISTAS = tuple(PESOS_INDICADOR)

# PESO DE CADA CATEGORIA -- DECISAO EM ABERTO.
#
# Com margens virando categoria propria sao 5, e o PRD nao diz quanto cada uma
# vale nesse desenho. 20% para todas e o default honesto quando nao ha base
# para preferir, nao uma conclusao.
#
# O que esta em jogo: antes margens estava DENTRO de rentabilidade, e as duas
# juntas valiam 25%. Com 20% cada, qualidade (rentabilidade + margens) passa a
# valer 40% do score. Isso e o oposto do motivo da separacao, que era tirar a
# dominancia da categoria -- so que agora por decisao explicita e nao por
# contagem de indicadores. Vale revisar com o usuario.
PESOS_CATEGORIA = {
    "valuation": 0.20,
    "rentabilidade": 0.20,
    "margens": 0.20,
    "crescimento": 0.20,
    "seguranca": 0.20,
}

# Tetos das metricas derivadas. Servem para um ticker com P/L (ou P/VP) proximo
# de zero nao gerar um yield gigante que reancora a escala do min-max e achata
# todos os outros. As duas metricas tem escalas economicas diferentes, por isso
# limites diferentes:
#   earnings yield 1.0  -> P/L de 1, ou seja 100% de lucro sobre o preco;
#                          acima disso e erro de dado, nao empresa barata.
#   book-to-market 5.0  -> P/VP de 0,2. P/VP abaixo de 1 e comum e legitimo
#                          (bancos brasileiros), entao o teto tem que ser folgado
#                          o suficiente para nao empatar 0,6 com 1,0.
LIMITE_YIELD = 1.0
LIMITE_BOOK_TO_MARKET = 5.0

# Trios (coluna do banco, coluna derivada, teto) da categoria valuation.
METRICAS_VALUATION = (
    ("pl", "earnings_yield", LIMITE_YIELD),
    ("pvp", "book_to_market", LIMITE_BOOK_TO_MARKET),
)

# Colunas cruas e derivadas que o ranking mostra para conferencia manual.
COLUNAS_VALUATION_EXIBICAO = ["pl", "pvp", "earnings_yield", "book_to_market"]

# P1-14: o teste absoluto que falta no valuation (7A.7).
#
# O z-score do valuation so diz quem e o menos caro DO GRUPO. Se o grupo
# inteiro estiver caro, ele continua distribuindo notas de 5 a 95 como se
# houvesse barganha ali. O premio sobre a Selic e a pergunta que ele nao faz:
# esta acao paga mais que titulo publico, que tem risco muito menor?
#
# NAO VIRA NOTA, vira flag. Entra depois do score estar calculado e nao mexe
# em peso, categoria nem ordenacao -- de proposito, porque "caro em termos
# absolutos" ja e informacao suficiente sozinha e misturar isso na nota
# recriaria o score_geral que o P1-13 acabou de remover.
#
# ARMADILHA DE UNIDADE: earnings_yield e FRACAO (0,1961) e a Selic vem em
# PONTO PERCENTUAL (13,65). Comparar os dois crus marcaria 7 dos 10 tickers
# de hoje como premio negativo por erro de escala, inclusive a PETR4, que
# paga quase 6 pontos ACIMA da Selic. Por isso a conversao e explicita aqui e
# e o primeiro teste do test_premio.py.
PONTOS_PERCENTUAIS = 100.0

# PESO_FUNDAMENTALISTA e PESO_PRECO sairam junto com o score_geral (P1-13).
# Os dois scores agora sao lidos lado a lado, nunca somados.


def adicionar_metricas_valuation(df):
    """Cria earnings_yield (1/pl) e book_to_market (1/pvp).

    Invertendo a metrica, a direcao "maior e melhor" fica correta em todo o
    dominio: empresa com prejuizo tem yield negativo e vai para o fim do
    ranking, em vez de parecer barata so porque o P/L negativo e um numero
    pequeno. Duas empresas com prejuizo tambem passam a ser comparaveis entre
    si, sem nenhum caso especial no codigo.

    P/L ou P/VP igual a zero implicaria preco zero (lucro zero manda o P/L para
    o infinito, nao para zero), logo e dado corrompido e nao informacao
    economica: vira NaN e nao pontua, junto com os valores ausentes. Valores
    muito proximos de zero pelo lado positivo geram yield gigante -- o clip no
    teto de cada metrica e a primeira defesa, e a winsorizacao de
    nota_relativa() e a segunda.
    """
    df = df.copy()
    for coluna_banco, coluna_derivada, teto in METRICAS_VALUATION:
        valores = pd.to_numeric(df[coluna_banco], errors="coerce").replace(0, np.nan)
        df[coluna_derivada] = (1 / valores).clip(-teto, teto)
    return df


def _cdf_normal(z):
    """Phi(z): a area da normal padrao ate z, de 0 a 1.

    Via math.erf da biblioteca padrao, para nao introduzir o scipy so por uma
    funcao. Phi(z) = (1 + erf(z/raiz(2))) / 2.
    """
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def nota_relativa(valor, maior_melhor):
    """Nota 0-100 comparando com o universo: winsoriza, z-score, CDF (P1-2).

    Era min-max ate o P1-2, e o min-max tinha um defeito estrutural: o pior
    colocado tirava EXATAMENTE 0 e o melhor EXATAMENTE 100, sempre, fossem
    quais fossem os numeros. Isso e artefato de escala, nao informacao -- com
    dois tickers quase empatados nas pontas, a distancia entre eles aparecia
    como 100 pontos de nota. Pior: um unico outlier esticava a regua e
    espremia todos os outros no meio.

    Os tres passos:

    1. WINSORIZAR em p5/p95. O extremo e puxado ate a borda, nao removido --
       continua sendo o maior da serie, mas para de definir sozinho a escala.
    2. Z-SCORE sobre o ja winsorizado, com media e desvio tambem do
       winsorizado. A nota passa a dizer "quantos desvios acima da media do
       universo", que e uma afirmacao com conteudo, em vez de "a que fracao
       do caminho entre o pior e o melhor".
    3. CDF NORMAL para voltar a 0-100. O z nao tem limite e a escala precisa
       ter, entao falta um mapeamento. A alternativa era cortar em +-2 desvios
       e esticar linearmente, mas ai todo mundo alem de 2 desvios volta a
       empatar em 0 e 100 exatos -- justamente o que este item veio tirar.
       Com 10 tickers ninguem passa de 2 desvios e as duas opcoes empatam; com
       30 (P1-8) o corte linear voltaria a amarrar as pontas. A CDF nunca
       chega a 0 nem a 100.

    Usar a CDF NAO afirma que o indicador e normalmente distribuido. Ela entra
    como funcao de achatamento monotona e limitada -- preserva a ordem e
    devolve algo que se le como percentil. Nota 96 quer dizer "mais barato que
    ~96% do universo", nao "esta a tantos desvios numa normal".

    O desvio usa ddof=0: a whitelist e a populacao inteira que interessa, nao
    uma amostra de um universo maior.

    Dado ausente continua ausente (P1-13), e nao entra em nenhum dos tres
    passos -- nao mexe nos percentis, na media nem no desvio.
    """
    valor = pd.to_numeric(valor, errors="coerce")
    presentes = valor.dropna()

    if presentes.empty:
        return pd.Series(np.nan, index=valor.index, dtype=float)

    corte_baixo = presentes.quantile(PERCENTIL_WINSOR)
    corte_alto = presentes.quantile(1 - PERCENTIL_WINSOR)
    winsorizado = valor.clip(corte_baixo, corte_alto)

    desvio = winsorizado.std(ddof=0)
    if pd.isna(desvio) or desvio == 0:
        # todos iguais (ou um so ticker): nao ha comparacao a fazer, entao
        # nota neutra para quem tem valor e ausente para quem nao tem
        return pd.Series(
            [np.nan if pd.isna(v) else 50.0 for v in valor], index=valor.index
        )

    z = (winsorizado - winsorizado.mean()) / desvio
    if not maior_melhor:
        z = -z

    return z.map(lambda v: np.nan if pd.isna(v) else 100 * _cdf_normal(v))


def _mascarar_nao_aplicaveis(df):
    """Transforma em ausente o indicador que nao se aplica ao setor (P1-12).

    Acontece ANTES de pontuar, de proposito: um valor inaplicavel nao pode
    nem virar nota nem ancorar a escala dos outros. A divida/PL de 5,13 do
    BBAS3 e alavancagem normal de banco, nao defeito -- mas, deixada na
    coluna, ela estica o min-max e muda a nota de seguranca de todo mundo.

    Nota sobre a 7A.6: o PRD pede "nota NEUTRA + flag nao_aplicavel" para
    financeiras. Aqui o inaplicavel e tratado como o ausente -- nao pontua e
    sai da conta -- em vez de receber 50. Nota neutra continua sendo um numero
    inventado, que puxa todo banco para o meio da escala; e a 7A.8 ja define
    exatamente este mecanismo para o dado faltante. Um mecanismo so, e a
    coluna de cobertura mostra a diferenca. Ver DECISOES.md.
    """
    df = df.copy()
    for ticker in df.index:
        for indicador in setores.indicadores_nao_aplicaveis(ticker):
            if indicador in df.columns:
                df.at[ticker, indicador] = np.nan
    return df


def _contar_aplicaveis(df):
    """Quantos indicadores do score se aplicam a cada ticker."""
    contagem = pd.Series(0, index=df.index, dtype=int)
    for indicadores in PESOS_INDICADOR.values():
        for indicador in indicadores:
            if indicador not in df.columns:
                continue
            for ticker in df.index:
                if not setores.nao_se_aplica(ticker, indicador):
                    contagem[ticker] += 1
    return contagem


def _media_ponderada(df, pesos_por_coluna):
    """Media ponderada linha a linha, ignorando coluna ausente.

    O peso da coluna que falta e redistribuido entre as presentes. Sem isso,
    faltar o ROA puxaria a nota de rentabilidade para baixo so por falta de
    dado -- o mesmo erro que o fillna(median) cometia pelo lado oposto.
    """
    colunas = [coluna for coluna in pesos_por_coluna if coluna in df.columns]
    if not colunas:
        return pd.Series(np.nan, index=df.index)

    notas = df[colunas]
    pesos = pd.DataFrame(
        {coluna: pesos_por_coluna[coluna] for coluna in colunas}, index=df.index
    ).where(notas.notna())

    soma = pesos.sum(axis=1)
    return (notas * pesos).sum(axis=1) / soma.replace(0, np.nan)


def calcular_premio_selic(earnings_yield, selic_anual):
    """Premio da acao sobre o titulo publico, em pontos percentuais (7A.7).

    `earnings_yield` chega como FRACAO (1/pl) e `selic_anual` em PONTO
    PERCENTUAL ao ano -- a conversao e o unico lugar onde isso pode dar
    errado, entao esta explicita numa linha so.

    Subtracao simples, nao composicao, e aqui isso esta certo: sao duas taxas
    nominais do mesmo periodo lidas lado a lado, e a diferenca em pontos
    percentuais e exatamente como o mercado le premio de risco. E o caso
    OPOSTO ao do CAGR em faixas.deflacionar(), onde a composicao importava
    porque uma taxa estava dentro da outra.

    Yield ausente devolve ausente -- nao da para saber, e isso nao e o mesmo
    que premio zero nem que premio negativo.
    """
    yield_anual = pd.to_numeric(earnings_yield, errors="coerce") * PONTOS_PERCENTUAIS
    return yield_anual - selic_anual


def calcular_score_fundamentalista(fundamentos, selic_anual=None):
    """`fundamentos`: um registro por ticker, indexado por ticker.

    Quatro categorias usam FAIXA ABSOLUTA (faixas.py): a nota sai do valor do
    indicador e nao muda quando a whitelist muda. So valuation e relativa ao
    universo, porque "caro" so existe em comparacao.

    Devolve as notas por categoria, o score_fundamentalista e a cobertura
    (`indicadores_usados` de `indicadores_aplicaveis`). Categoria sem nenhum
    indicador disponivel sai como ausente e tem o peso redistribuido entre as
    que sobraram -- nao vira zero, que seria dizer "ruim" quando a verdade e
    "nao da para saber".

    `selic_anual` e a regua do premio do P1-14, em % ao ano. Quando nao vem,
    usa a constante de faixas.py -- o default existe para teste com dado
    sintetico e para quem chamar daqui sem ter banco. Em producao quem passa
    e o analise.py, com a Selic viva de indices.selic_anual_vigente().
    """
    if selic_anual is None:
        selic_anual = faixas.SELIC_REFERENCIA

    df = adicionar_metricas_valuation(fundamentos)
    aplicaveis = _contar_aplicaveis(df)
    df = _mascarar_nao_aplicaveis(df)

    scores_categoria = pd.DataFrame(index=df.index)
    colunas_de_indicador = []

    for categoria in CATEGORIAS_FUNDAMENTALISTAS:
        pesos = PESOS_INDICADOR[categoria]
        pesos_por_coluna = {}

        for indicador, peso in pesos.items():
            if indicador not in df.columns:
                continue
            col_score = f"score_{indicador}"

            if categoria in CATEGORIAS_ABSOLUTAS:
                df[col_score] = df[indicador].map(
                    lambda valor, ind=indicador: faixas.nota(ind, valor)
                )
            else:
                df[col_score] = nota_relativa(df[indicador], MAIOR_MELHOR[indicador])

            pesos_por_coluna[col_score] = peso

        colunas_de_indicador.extend(pesos_por_coluna)
        scores_categoria[categoria] = _media_ponderada(df, pesos_por_coluna)

    categorias = list(CATEGORIAS_FUNDAMENTALISTAS)
    notas = scores_categoria[categorias]

    # peso redistribuido sobre as categorias que esse ticker tem
    pesos = pd.DataFrame(
        {categoria: PESOS_CATEGORIA[categoria] for categoria in categorias},
        index=df.index,
    ).where(notas.notna())

    soma_pesos = pesos.sum(axis=1)
    scores_categoria["score_fundamentalista"] = (
        (notas * pesos).sum(axis=1) / soma_pesos.replace(0, np.nan)
    )

    scores_categoria["indicadores_usados"] = df[colunas_de_indicador].notna().sum(axis=1)
    scores_categoria["indicadores_aplicaveis"] = aplicaveis
    scores_categoria["categorias_usadas"] = notas.notna().sum(axis=1)

    for coluna in COLUNAS_VALUATION_EXIBICAO:
        scores_categoria[coluna] = df[coluna]

    # P1-14. Depois do score estar pronto, e sem entrar nele.
    premio = calcular_premio_selic(df["earnings_yield"], selic_anual)
    scores_categoria["premio_selic_pp"] = premio
    # dtype anulavel de proposito: yield ausente vira <NA>, nao False. Dizer
    # "nao tem premio negativo" sobre quem nao tem P/L seria inventar.
    scores_categoria["premio_negativo"] = (premio < 0).astype("boolean").where(
        premio.notna()
    )

    return scores_categoria.sort_values("score_fundamentalista", ascending=False)


# Janela do score de reversao, em pregoes. 252 e um ano de bolsa -- a mesma
# janela da "maxima e minima de 52 semanas" que o mercado usa.
JANELA_REVERSAO = 252

# Abaixo disso o range nao descreve distribuicao nenhuma: com 20 pregoes, o
# ultimo preco e quase sempre a maxima ou a minima, e o score vira interruptor
# de 0 ou 100 em vez de escala.
MINIMO_OBSERVACOES = 60

# Nota devolvida quando nao ha observacoes suficientes. Neutra de proposito:
# "nao sei" nao e nem bom nem ruim, e vem acompanhada da flag.
NOTA_SEM_DADOS = 50.0


def calcular_score_reversao(precos):
    """Posicao do preco dentro da janela, invertida. Era `calcular_score_preco`.

    `precos`: colunas ticker, data e fechamento_ajustado, uma linha por pregao.

    MEDE QUEDA, NAO BARATEAMENTO. Uma acao pode cair 40% e ficar mais cara, se
    o lucro caiu 60%. E uma aposta contraria deliberada, e a literatura de
    fatores (Asness, Moskowitz, Pedersen) aponta na direcao oposta -- valor com
    momentum positivo tende a funcionar melhor que comprar o que esta caindo.
    Mantido como fator informativo, com o trade-off explicito. Nunca descreva
    esta coluna como valuation.

    Usa fechamento AJUSTADO: no dia do provento o preco cai sem que a empresa
    tenha piorado, e o fechamento cru leria isso como queda.

    Devolve, por ticker: preco_atual (fechamento cru, que e o que aparece na
    tela), score_reversao, observacoes e a flag dados_insuficientes.
    """
    colunas = ["preco_atual", "score_reversao", "observacoes",
               "dados_insuficientes", "janela_completa"]
    if precos.empty:
        return pd.DataFrame(columns=colunas)

    linhas = {}
    for ticker, grupo in precos.groupby("ticker"):
        janela = grupo.sort_values("data").tail(JANELA_REVERSAO)
        serie = janela["fechamento_ajustado"].dropna()
        observacoes = len(serie)

        preco_atual = (janela["fechamento"].dropna().iloc[-1]
                       if "fechamento" in janela.columns and janela["fechamento"].notna().any()
                       else (serie.iloc[-1] if observacoes else np.nan))

        if observacoes < MINIMO_OBSERVACOES:
            nota = NOTA_SEM_DADOS
            insuficiente = True
        else:
            minimo, maximo = serie.min(), serie.max()
            if maximo == minimo:
                # preco parado na janela inteira: nao caiu nem subiu
                nota = NOTA_SEM_DADOS
            else:
                posicao = (serie.iloc[-1] - minimo) / (maximo - minimo)
                nota = (1 - posicao) * 100
            insuficiente = False

        linhas[ticker] = {
            "preco_atual": preco_atual,
            "score_reversao": nota,
            "observacoes": observacoes,
            "dados_insuficientes": insuficiente,
            "janela_completa": observacoes >= JANELA_REVERSAO,
        }

    return pd.DataFrame.from_dict(linhas, orient="index")[colunas]


def calcular_ranking(fundamentos, precos, selic_anual=None):
    """Junta score fundamentalista e score de reversao, lado a lado.

    NAO existe mais score_geral (P1-13). Ele era
    0,6*fundamentalista + 0,4*preco e nao era consumido por nada: as regras de
    sinal (RF-07) ja usavam os dois separados. O composto so misturava "empresa
    boa" com "caiu recentemente" num numero unico que esconde qual dos dois
    esta falando.

    Descoberto ao revisar: 0,6 x 25% (valuation) + 40% (preco) = 55% do score
    final era alguma forma de "esta barato" -- um vies de valor muito mais
    agressivo do que o desenho aparentava. Ver DECISOES.md.

    Ordena por score_fundamentalista. O score de reversao fica ao lado, para
    ser lido junto e nao somado -- um diz "empresa boa", o outro diz "caiu".

    `selic_anual` so atravessa daqui para o score fundamentalista, onde vira a
    regua da flag `premio_negativo` (P1-14). Nao toca em nota nenhuma.
    """
    fundamentalista = calcular_score_fundamentalista(fundamentos, selic_anual)
    reversao = calcular_score_reversao(precos)

    combinado = fundamentalista.join(reversao, how="left")
    return combinado.sort_values("score_fundamentalista", ascending=False)
