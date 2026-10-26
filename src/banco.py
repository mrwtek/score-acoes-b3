import sqlite3
from collections import namedtuple
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from paths import CAMINHO_BANCO, fazer_backup

# Mesma constante que o main.py usa para a janela de pregao. Repetida aqui de
# proposito para nao criar import de main.py no banco.py (main ja importa
# banco); se um terceiro arquivo precisar dela, vale centralizar.
FUSO_B3 = ZoneInfo("America/Sao_Paulo")


def hoje():
    return datetime.now().strftime("%d/%m/%Y")


def criar_tabelas():
    fazer_backup()

    conexao = sqlite3.connect(CAMINHO_BANCO)
    cursor = conexao.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cotacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            data TEXT NOT NULL,
            hora_coleta TEXT NOT NULL,
            preco REAL,
            volume INTEGER,
            market_cap REAL,
            preco_lucro REAL,
            lucro_por_acao REAL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS posicoes (
            ticker TEXT PRIMARY KEY,
            quantidade INTEGER NOT NULL,
            preco_medio REAL NOT NULL,
            data_atualizacao TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fundamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            data TEXT NOT NULL,
            hora_coleta TEXT NOT NULL,
            pl REAL,
            pvp REAL,
            roe REAL,
            roa REAL,
            roic REAL,
            margem_liquida REAL,
            margem_bruta REAL,
            margem_ebitda REAL,
            divida_patrimonio REAL,
            cagr_receita_5a REAL,
            cagr_lucro_5a REAL,
            UNIQUE(ticker, data)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            tipo TEXT NOT NULL,
            quantidade INTEGER NOT NULL,
            preco REAL NOT NULL,
            data_operacao TEXT NOT NULL,
            taxas REAL,
            observacao TEXT
        )
    """)

    # Serie diaria de fechamento, vinda do historico da brapi. Fica separada de
    # `cotacoes` de proposito: `cotacoes` e a serie de coleta, com varias linhas
    # por dia e so o preco do momento; aqui e um ponto por pregao, com OHLC e
    # fechamento ajustado. Misturar as duas estragaria as duas.
    #
    # `data` aqui e so ISO (YYYY-MM-DD). A convivencia de dois formatos de data
    # existe no resto do banco porque ja_tem_fundamento_hoje() depende do
    # formato brasileiro; tabela nova nao herda essa divida.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cotacoes_historicas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            data TEXT NOT NULL,
            abertura REAL,
            maxima REAL,
            minima REAL,
            fechamento REAL,
            fechamento_ajustado REAL,
            volume INTEGER,
            coletado_em TEXT NOT NULL,
            UNIQUE(ticker, data)
        )
    """)

    # Benchmarks: Ibovespa (brapi) e Selic/CDI (Banco Central).
    #
    # `tipo` existe porque as duas naturezas nao se comparam do mesmo jeito:
    #   'preco'       -> nivel do indice (IBOV). Rendimento = variacao %.
    #   'taxa_diaria' -> % ao dia (Selic, CDI). Rendimento = produtorio de
    #                    (1 + valor/100). Somar taxa diaria da errado.
    # A taxa fica gravada crua, como o BCB manda; a acumulacao e na leitura.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS indices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT NOT NULL,
            data TEXT NOT NULL,
            valor REAL NOT NULL,
            tipo TEXT NOT NULL,
            coletado_em TEXT NOT NULL,
            UNIQUE(codigo, data)
        )
    """)

    # Diario de teses: o que voce achou, quando, por que, e ate quando.
    #
    # Existe para separar "eu estava certo" de "deu certo". Sem prazo e sem
    # criterio gravados ANTES, qualquer tese e inrefutavel -- sempre da para
    # dizer "ainda vai voltar". Com prazo, ela pode falhar, e so o que pode
    # falhar ensina alguma coisa.
    #
    # `preco_abertura` e `score_abertura` ficam congelados de proposito: a
    # metodologia do score ainda vai mudar (P1-11 em diante), e a nota de hoje
    # precisa continuar sendo a nota de hoje quando formos conferir.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS teses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            data_abertura TEXT NOT NULL,
            preco_abertura REAL NOT NULL,
            premissa TEXT NOT NULL,
            criterio TEXT NOT NULL,
            horizonte_dias INTEGER NOT NULL,
            score_abertura REAL,
            status TEXT NOT NULL DEFAULT 'aberta',
            data_encerramento TEXT,
            veredito TEXT,
            criado_em TEXT NOT NULL
        )
    """)

    _adicionar_coluna_se_faltar(cursor, "cotacoes", "data_hora_iso", "TEXT")
    _adicionar_coluna_se_faltar(cursor, "fundamentos", "data_hora_iso", "TEXT")
    _adicionar_coluna_se_faltar(cursor, "transacoes", "data_operacao_iso", "TEXT")

    conexao.commit()
    conexao.close()


def _adicionar_coluna_se_faltar(cursor, tabela, coluna, tipo):
    cursor.execute(f"PRAGMA table_info({tabela})")
    colunas_existentes = [linha[1] for linha in cursor.fetchall()]
    if coluna not in colunas_existentes:
        cursor.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}")


def salvar_cotacoes(lista_dados):
    conexao = sqlite3.connect(CAMINHO_BANCO)
    cursor = conexao.cursor()
    agora = datetime.now()

    for dados in lista_dados:
        cursor.execute("""
            INSERT INTO cotacoes (ticker, data, hora_coleta, preco, volume, market_cap, preco_lucro, lucro_por_acao, data_hora_iso)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            dados.get("symbol"),
            agora.strftime("%d/%m/%Y"),
            agora.strftime("%H:%M:%S"),
            dados.get("regularMarketPrice"),
            dados.get("regularMarketVolume"),
            dados.get("marketCap"),
            dados.get("priceEarnings"),
            dados.get("earningsPerShare"),
            agora.strftime("%Y-%m-%d %H:%M:%S"),
        ))

    conexao.commit()
    conexao.close()
    print(f"{len(lista_dados)} cotacoes salvas no banco.")


def normalizar_ticker(ticker):
    """Maiusculo, sem espacos e sem o sufixo .SA.

    O join entre as fontes e por ticker, entao a normalizacao tem que acontecer
    na escrita. As funcoes antigas (salvar_cotacoes, salvar_fundamento) ainda
    gravam o que a API devolveu; por ora as duas APIs em uso ja devolvem o
    formato certo.
    """
    limpo = str(ticker).strip().upper()
    if limpo.endswith(".SA"):
        limpo = limpo[:-3]
    return limpo


# Hora em que o pregao fecha, no fuso da B3. Mesma constante do main.py.
HORA_FECHAMENTO = 18


def hoje_b3():
    """Data de hoje no fuso da B3, em 'YYYY-MM-DD'."""
    return datetime.now(FUSO_B3).strftime("%Y-%m-%d")


def data_limite_para_historico(momento=None):
    """Ultima data que ja pode ser gravada como pregao fechado.

    Devolve a data de hoje enquanto o pregao esta em andamento, e None depois
    do fechamento -- quando nao ha mais nada a excluir.

    CORRECAO de 26/10/2026. A versao anterior recusava QUALQUER barra com a
    data de hoje, e o motivo escrito era que a brapi devolvia numeros
    inconsistentes para o dia corrente. Isso estava errado: naquele dia os
    bancos caíram de verdade (BBAS3 -29,33%, BBDC4 -21,70%) enquanto VALE3
    subia 4,01%, e eu li esse padrao como dado corrompido. Era evento de
    setor, nao defeito da fonte -- o Investidor10 mostrava os mesmos precos.
    Treze linhas reais foram apagadas por causa dessa leitura.

    O risco que a regra tenta evitar e real, mas so existe DURANTE o pregao:
    ali a barra ainda muda e o INSERT OR IGNORE congelaria um valor parcial.
    Depois do fechamento a barra e final e tem que entrar.

    Licao que fica: implausibilidade nao e criterio para apagar dado. Quando a
    fonte e o codigo discordam, conferir com uma segunda fonte antes, nunca
    deduzir do formato do numero.
    """
    momento = momento or datetime.now(FUSO_B3)
    if momento.hour < HORA_FECHAMENTO:
        return momento.strftime("%Y-%m-%d")
    return None


# O que aconteceu com os pontos recebidos. `em_andamento` fica separado de
# `descartadas` de proposito: descartar dado corrompido e ignorar o pregao de
# hoje sao coisas diferentes, e so a primeira merece preocupacao.
ResultadoGravacao = namedtuple("ResultadoGravacao", "novas descartadas em_andamento")


def salvar_cotacoes_historicas(ticker, pontos):
    """Grava a serie diaria de um ticker e devolve um ResultadoGravacao.

    `pontos` e a lista de dicionarios que a brapi devolve em
    historicalDataPrice. O INSERT OR IGNORE, somado ao UNIQUE(ticker, data),
    e o que torna o backfill reexecutavel: rodar de novo sobre dias que ja
    estao no banco nao duplica nem sobrescreve, so nao faz nada.

    Pontos sem data ou sem fechamento sao descartados - sem esses dois campos
    a linha nao serve para calcular retorno nenhum.

    O pregao de hoje so e ignorado ENQUANTO a sessao esta aberta, porque ali a
    barra ainda muda e o INSERT OR IGNORE congelaria um valor parcial. Depois
    do fechamento ela entra normalmente. Ver data_limite_para_historico(), que
    documenta o erro que essa regra ja causou.
    """
    ticker = normalizar_ticker(ticker)
    conexao = sqlite3.connect(CAMINHO_BANCO)
    cursor = conexao.cursor()
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    limite = data_limite_para_historico()

    antes = conexao.total_changes
    descartadas = 0
    em_andamento = 0

    for ponto in pontos:
        data_iso = _data_do_ponto(ponto)
        if data_iso is None or ponto.get("close") is None:
            descartadas += 1
            continue

        if limite is not None and data_iso >= limite:
            em_andamento += 1
            continue

        cursor.execute("""
            INSERT OR IGNORE INTO cotacoes_historicas (
                ticker, data, abertura, maxima, minima,
                fechamento, fechamento_ajustado, volume, coletado_em
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ticker,
            data_iso,
            ponto.get("open"),
            ponto.get("high"),
            ponto.get("low"),
            ponto.get("close"),
            # quando a API nao manda o ajustado, o fechamento cru e o melhor
            # palpite - so nao vale fingir que sao a mesma coisa em silencio,
            # por isso o backfill conta e reporta esses casos
            ponto.get("adjustedClose"),
            ponto.get("volume"),
            agora,
        ))

    conexao.commit()
    novas = conexao.total_changes - antes
    conexao.close()
    return ResultadoGravacao(novas, descartadas, em_andamento)


def _data_do_ponto(ponto):
    """Converte o campo `date` (epoch em segundos) para 'YYYY-MM-DD'.

    A brapi manda a meia-noite de Sao Paulo (03:00 UTC). Converter com o fuso
    da maquina daria o dia certo aqui, mas erraria por um dia em qualquer fuso
    a oeste de UTC-3, que e onde 03:00 UTC ainda e a vespera. Como a data e a
    chave do UNIQUE, um deslize desses geraria linha duplicada em vez de erro.
    """
    bruto = ponto.get("date")
    if bruto is None:
        return None
    try:
        momento = datetime.fromtimestamp(int(bruto), tz=timezone.utc)
    except (ValueError, TypeError, OSError, OverflowError):
        return None
    return momento.astimezone(FUSO_B3).strftime("%Y-%m-%d")


def contar_cotacoes_historicas():
    """Devolve [(ticker, linhas, primeira_data, ultima_data)] para conferencia."""
    conexao = sqlite3.connect(CAMINHO_BANCO)
    cursor = conexao.cursor()
    cursor.execute("""
        SELECT ticker, COUNT(*), MIN(data), MAX(data)
        FROM cotacoes_historicas
        GROUP BY ticker
        ORDER BY ticker
    """)
    resultado = cursor.fetchall()
    conexao.close()
    return resultado


TIPO_PRECO = "preco"
TIPO_TAXA_DIARIA = "taxa_diaria"


def salvar_indices(codigo, tipo, pontos):
    """Grava pontos de um indice e devolve um ResultadoGravacao.

    `pontos` e uma lista de (data_iso, valor). Mesma regra do historico de
    precos: INSERT OR IGNORE sobre UNIQUE(codigo, data), para o backfill poder
    rodar quantas vezes quiser, e o dia de hoje fica de fora.

    No caso das taxas o dia corrente nem costuma existir - o BCB publica a
    Selic e o CDI de um dia depois do fechamento, entao a serie chega com dois
    ou tres dias de atraso em relacao ao Ibovespa. Isso e da fonte, nao do
    codigo: quem comparar rendimento acumulado precisa cortar as duas series
    na mesma data final.
    """
    if tipo not in (TIPO_PRECO, TIPO_TAXA_DIARIA):
        raise ValueError(f"tipo invalido: {tipo!r}. Use {TIPO_PRECO!r} ou {TIPO_TAXA_DIARIA!r}.")

    codigo = str(codigo).strip().upper()
    conexao = sqlite3.connect(CAMINHO_BANCO)
    cursor = conexao.cursor()
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    limite = data_limite_para_historico()

    antes = conexao.total_changes
    descartadas = 0
    em_andamento = 0

    for data_iso, valor in pontos:
        if data_iso is None or valor is None:
            descartadas += 1
            continue

        if limite is not None and data_iso >= limite:
            em_andamento += 1
            continue

        cursor.execute("""
            INSERT OR IGNORE INTO indices (codigo, data, valor, tipo, coletado_em)
            VALUES (?, ?, ?, ?, ?)
        """, (codigo, data_iso, valor, tipo, agora))

    conexao.commit()
    novas = conexao.total_changes - antes
    conexao.close()
    return ResultadoGravacao(novas, descartadas, em_andamento)


def contar_indices():
    """Devolve [(codigo, tipo, linhas, primeira_data, ultima_data)]."""
    conexao = sqlite3.connect(CAMINHO_BANCO)
    cursor = conexao.cursor()
    cursor.execute("""
        SELECT codigo, tipo, COUNT(*), MIN(data), MAX(data)
        FROM indices
        GROUP BY codigo, tipo
        ORDER BY codigo
    """)
    resultado = cursor.fetchall()
    conexao.close()
    return resultado


def salvar_tese(ticker, data_abertura, preco_abertura, premissa, criterio,
                horizonte_dias, score_abertura=None):
    """Grava uma tese aberta e devolve o id."""
    ticker = normalizar_ticker(ticker)
    conexao = sqlite3.connect(CAMINHO_BANCO)
    cursor = conexao.cursor()
    cursor.execute("""
        INSERT INTO teses (ticker, data_abertura, preco_abertura, premissa,
                           criterio, horizonte_dias, score_abertura, status, criado_em)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'aberta', ?)
    """, (ticker, data_abertura, preco_abertura, premissa, criterio,
          horizonte_dias, score_abertura,
          datetime.now(FUSO_B3).strftime("%Y-%m-%d %H:%M:%S")))
    conexao.commit()
    id_tese = cursor.lastrowid
    conexao.close()
    return id_tese


def listar_teses(apenas_abertas=False):
    """Devolve as teses como lista de dicionarios, mais antiga primeiro."""
    conexao = sqlite3.connect(CAMINHO_BANCO)
    conexao.row_factory = sqlite3.Row
    sql = "SELECT * FROM teses"
    if apenas_abertas:
        sql += " WHERE status = 'aberta'"
    sql += " ORDER BY data_abertura, ticker"
    linhas = [dict(linha) for linha in conexao.execute(sql).fetchall()]
    conexao.close()
    return linhas


def encerrar_tese(id_tese, veredito, data_encerramento=None):
    """Fecha uma tese com o veredito escrito. Nao apaga nada."""
    conexao = sqlite3.connect(CAMINHO_BANCO)
    conexao.execute("""
        UPDATE teses SET status = 'encerrada', veredito = ?, data_encerramento = ?
        WHERE id = ?
    """, (veredito, data_encerramento or hoje_b3(), id_tese))
    conexao.commit()
    conexao.close()


def ja_tem_fundamento_hoje(ticker):
    conexao = sqlite3.connect(CAMINHO_BANCO)
    cursor = conexao.cursor()
    cursor.execute(
        "SELECT 1 FROM fundamentos WHERE ticker = ? AND data = ?",
        (ticker, hoje())
    )
    resultado = cursor.fetchone()
    conexao.close()
    return resultado is not None


def salvar_fundamento(ticker, dados):
    conexao = sqlite3.connect(CAMINHO_BANCO)
    cursor = conexao.cursor()
    agora = datetime.now()

    cursor.execute("""
        INSERT OR IGNORE INTO fundamentos (
            ticker, data, hora_coleta, pl, pvp, roe, roa, roic,
            margem_liquida, margem_bruta, margem_ebitda,
            divida_patrimonio, cagr_receita_5a, cagr_lucro_5a, data_hora_iso
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        ticker,
        agora.strftime("%d/%m/%Y"),
        agora.strftime("%H:%M:%S"),
        dados.get("pl"),
        dados.get("pvp"),
        dados.get("roe"),
        dados.get("roa"),
        dados.get("roic"),
        dados.get("net_margin"),
        dados.get("gross_margin"),
        dados.get("ebitda_margin"),
        dados.get("debt_equity"),
        dados.get("cagr_revenue_5y"),
        dados.get("cagr_earnings_5y"),
        agora.strftime("%Y-%m-%d %H:%M:%S"),
    ))

    conexao.commit()
    conexao.close()
    print(f"Fundamentos de {ticker} salvos no banco.")


def registrar_compra(ticker, quantidade, preco):
    conexao = sqlite3.connect(CAMINHO_BANCO)
    cursor = conexao.cursor()
    cursor.execute("SELECT quantidade, preco_medio FROM posicoes WHERE ticker = ?", (ticker,))
    existente = cursor.fetchone()

    if existente is None:
        nova_quantidade = quantidade
        novo_preco_medio = preco
    else:
        quantidade_atual, preco_medio_atual = existente
        nova_quantidade = quantidade_atual + quantidade
        novo_preco_medio = ((quantidade_atual * preco_medio_atual) + (quantidade * preco)) / nova_quantidade

    agora = datetime.now()
    data_operacao = agora.strftime("%d/%m/%Y %H:%M:%S")
    data_operacao_iso = agora.strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        INSERT INTO posicoes (ticker, quantidade, preco_medio, data_atualizacao)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(ticker) DO UPDATE SET
            quantidade = excluded.quantidade,
            preco_medio = excluded.preco_medio,
            data_atualizacao = excluded.data_atualizacao
    """, (ticker, nova_quantidade, novo_preco_medio, data_operacao))

    cursor.execute("""
        INSERT INTO transacoes (ticker, tipo, quantidade, preco, data_operacao, taxas, observacao, data_operacao_iso)
        VALUES (?, 'compra', ?, ?, ?, NULL, NULL, ?)
    """, (ticker, quantidade, preco, data_operacao, data_operacao_iso))

    conexao.commit()
    conexao.close()
    print(f"Compra registrada: {ticker} agora com {nova_quantidade} acoes a preco medio de R$ {novo_preco_medio:.2f}")


def registrar_venda(ticker, quantidade):
    conexao = sqlite3.connect(CAMINHO_BANCO)
    cursor = conexao.cursor()
    cursor.execute("SELECT quantidade, preco_medio FROM posicoes WHERE ticker = ?", (ticker,))
    existente = cursor.fetchone()

    if existente is None:
        print(f"Nao ha posicao registrada para {ticker}.")
        conexao.close()
        return

    quantidade_atual, preco_medio_atual = existente

    if quantidade > quantidade_atual:
        print(f"Erro: tentando vender {quantidade}, mas so ha {quantidade_atual} em posicao.")
        conexao.close()
        return

    nova_quantidade = quantidade_atual - quantidade
    agora = datetime.now()
    data_operacao = agora.strftime("%d/%m/%Y %H:%M:%S")
    data_operacao_iso = agora.strftime("%Y-%m-%d %H:%M:%S")

    if nova_quantidade == 0:
        cursor.execute("DELETE FROM posicoes WHERE ticker = ?", (ticker,))
        print(f"Posicao de {ticker} zerada e removida.")
    else:
        cursor.execute("""
            UPDATE posicoes SET quantidade = ?, data_atualizacao = ?
            WHERE ticker = ?
        """, (nova_quantidade, data_operacao, ticker))
        print(f"Venda registrada: {ticker} agora com {nova_quantidade} acoes (preco medio mantido em R$ {preco_medio_atual:.2f}).")

    cursor.execute("""
        INSERT INTO transacoes (ticker, tipo, quantidade, preco, data_operacao, taxas, observacao, data_operacao_iso)
        VALUES (?, 'venda', ?, ?, ?, NULL, NULL, ?)
    """, (ticker, quantidade, preco_medio_atual, data_operacao, data_operacao_iso))

    conexao.commit()
    conexao.close()


def listar_posicoes():
    conexao = sqlite3.connect(CAMINHO_BANCO)
    cursor = conexao.cursor()
    cursor.execute("SELECT ticker, quantidade, preco_medio, data_atualizacao FROM posicoes")
    resultado = cursor.fetchall()
    conexao.close()
    return resultado

def listar_tickers_em_carteira():
    conexao = sqlite3.connect(CAMINHO_BANCO)
    cursor = conexao.cursor()
    cursor.execute("SELECT ticker FROM posicoes WHERE quantidade > 0")
    resultado = [linha[0] for linha in cursor.fetchall()]
    conexao.close()
    return resultado