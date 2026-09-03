import sqlite3
from datetime import datetime

from paths import CAMINHO_BANCO, fazer_backup


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

    conexao.commit()
    conexao.close()


def salvar_cotacoes(lista_dados):
    conexao = sqlite3.connect(CAMINHO_BANCO)
    cursor = conexao.cursor()
    agora = datetime.now()

    for dados in lista_dados:
        cursor.execute("""
            INSERT INTO cotacoes (ticker, data, hora_coleta, preco, volume, market_cap, preco_lucro, lucro_por_acao)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            dados.get("symbol"),
            agora.strftime("%d/%m/%Y"),
            agora.strftime("%H:%M:%S"),
            dados.get("regularMarketPrice"),
            dados.get("regularMarketVolume"),
            dados.get("marketCap"),
            dados.get("priceEarnings"),
            dados.get("earningsPerShare"),
        ))

    conexao.commit()
    conexao.close()
    print(f"{len(lista_dados)} cotacoes salvas no banco.")


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
            divida_patrimonio, cagr_receita_5a, cagr_lucro_5a
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

    data_operacao = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    cursor.execute("""
        INSERT INTO posicoes (ticker, quantidade, preco_medio, data_atualizacao)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(ticker) DO UPDATE SET
            quantidade = excluded.quantidade,
            preco_medio = excluded.preco_medio,
            data_atualizacao = excluded.data_atualizacao
    """, (ticker, nova_quantidade, novo_preco_medio, data_operacao))

    cursor.execute("""
        INSERT INTO transacoes (ticker, tipo, quantidade, preco, data_operacao, taxas, observacao)
        VALUES (?, 'compra', ?, ?, ?, NULL, NULL)
    """, (ticker, quantidade, preco, data_operacao))

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
    data_operacao = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

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
        INSERT INTO transacoes (ticker, tipo, quantidade, preco, data_operacao, taxas, observacao)
        VALUES (?, 'venda', ?, ?, ?, NULL, NULL)
    """, (ticker, quantidade, preco_medio_atual, data_operacao))

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