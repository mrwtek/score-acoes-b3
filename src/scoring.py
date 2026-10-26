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
DECISOES.md. O que esta implementado aqui ainda e a versao antiga - min-max
relativo ao universo em todas as categorias, margens dentro de rentabilidade,
margem_bruta pontuando e score_geral existindo. Tudo isso ja foi decidido
contra; a migracao e o bloco P1-11 -> P1-12 -> P1-13 -> P1-2 -> P1-14.
O P1-1 so moveu o codigo de lugar, sem mudar uma conta.
"""

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
# comparacao. Hoje por min-max; o P1-2 troca por winsorizacao + z-score.
CATEGORIAS_RELATIVAS = ("valuation",)

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
    economica: vira NaN e cai no fillna(median) de normalizar(), junto com os
    valores ausentes. Valores muito proximos de zero pelo lado positivo geram
    yield gigante -- o clip no teto de cada metrica impede que um unico ticker
    achate todos os outros na normalizacao.
    """
    df = df.copy()
    for coluna_banco, coluna_derivada, teto in METRICAS_VALUATION:
        valores = pd.to_numeric(df[coluna_banco], errors="coerce").replace(0, np.nan)
        df[coluna_derivada] = (1 / valores).clip(-teto, teto)
    return df


def normalizar(valor, maior_melhor):
    """Min-max 0-100. Dado ausente continua ausente (P1-13).

    Antes isto fazia fillna(valor.median()): quem nao tinha o indicador
    recebia nota media em silencio, e nada no ranking indicava a diferenca
    entre "mediano" e "nao sabemos". Agora o ausente nao pontua e some da
    conta da categoria, e a cobertura aparece no ranking.

    O min e o max tambem passam a ignorar o ausente, entao um indicador
    faltante deixa de influenciar a escala dos outros.
    """
    minimo, maximo = valor.min(), valor.max()
    if pd.isna(minimo) or minimo == maximo:
        # serie toda ausente, ou todos iguais: nota neutra para quem tem
        # valor, ausente para quem nao tem
        return pd.Series(
            [np.nan if pd.isna(v) else 50.0 for v in valor], index=valor.index
        )

    normalizado = (valor - minimo) / (maximo - minimo) * 100
    return normalizado if maior_melhor else 100 - normalizado


def _mascarar_nao_aplicaveis(df):
    """Transforma em ausente o indicador que nao se aplica ao setor (P1-12).

    Acontece ANTES de normalizar, de proposito: um valor inaplicavel nao pode
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


def calcular_score_fundamentalista(fundamentos):
    """`fundamentos`: um registro por ticker, indexado por ticker.

    Quatro categorias usam FAIXA ABSOLUTA (faixas.py): a nota sai do valor do
    indicador e nao muda quando a whitelist muda. So valuation e relativa ao
    universo, porque "caro" so existe em comparacao.

    Devolve as notas por categoria, o score_fundamentalista e a cobertura
    (`indicadores_usados` de `indicadores_aplicaveis`). Categoria sem nenhum
    indicador disponivel sai como ausente e tem o peso redistribuido entre as
    que sobraram -- nao vira zero, que seria dizer "ruim" quando a verdade e
    "nao da para saber".
    """
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
                df[col_score] = normalizar(df[indicador], MAIOR_MELHOR[indicador])

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


def calcular_ranking(fundamentos, precos):
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
    """
    fundamentalista = calcular_score_fundamentalista(fundamentos)
    reversao = calcular_score_reversao(precos)

    combinado = fundamentalista.join(reversao, how="left")
    return combinado.sort_values("score_fundamentalista", ascending=False)
