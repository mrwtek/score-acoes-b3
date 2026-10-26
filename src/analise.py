"""
Leitura do banco e apresentacao do ranking.

Desde o P1-1 as contas moram no scoring.py. Aqui ficam so os carregadores e a
orquestracao: este arquivo sabe de SQLite, o scoring.py sabe de formula, e
nenhum dos dois precisa saber do outro para ser testado.

Rodar: cd src && python analise.py
"""

import sqlite3

import pandas as pd

import scoring
from paths import CAMINHO_BANCO


def carregar_fundamentos():
    conexao = sqlite3.connect(CAMINHO_BANCO)
    df = pd.read_sql_query("SELECT * FROM fundamentos", conexao)
    conexao.close()
    return df


def carregar_cotacoes():
    conexao = sqlite3.connect(CAMINHO_BANCO)
    df = pd.read_sql_query("SELECT * FROM cotacoes", conexao)
    conexao.close()
    return df


def carregar_posicoes():
    conexao = sqlite3.connect(CAMINHO_BANCO)
    df = pd.read_sql_query("SELECT * FROM posicoes", conexao)
    conexao.close()
    return df


def carregar_fundamentos_mais_recentes():
    """Um registro por ticker, o mais recente, indexado por ticker.

    Ordena por `data_hora_iso`, nunca por `data` (BUG-01). A coluna `data`
    guarda dd/mm/aaaa, e MAX() sobre texto compara caractere a caractere:
    '31/08/2026' sai maior que '14/09/2026' porque '3' > '1'. O efeito nao e
    erro nem linha faltando - e o ranking inteiro calculado sobre o fundamento
    mais ANTIGO do banco, em silencio.

    Vale para qualquer consulta nova: as colunas *_iso existem para isso.
    """
    conexao = sqlite3.connect(CAMINHO_BANCO)
    df = pd.read_sql_query("""
        SELECT f.*
        FROM fundamentos f
        INNER JOIN (
            SELECT ticker, MAX(data_hora_iso) AS mais_recente
            FROM fundamentos
            WHERE data_hora_iso IS NOT NULL
            GROUP BY ticker
        ) ultimo
        ON f.ticker = ultimo.ticker AND f.data_hora_iso = ultimo.mais_recente
    """, conexao)
    conexao.close()
    return df.set_index("ticker")


def carregar_precos_para_score():
    """Ticker e preco de todas as coletas, na ordem de insercao.

    Sem ORDER BY de proposito: o calcular_score_preco() pega o "preco atual"
    com agg("last"), entao depende desta ordem. Ordenar aqui mudaria o
    resultado em silencio.
    """
    conexao = sqlite3.connect(CAMINHO_BANCO)
    df = pd.read_sql_query("SELECT ticker, preco FROM cotacoes", conexao)
    conexao.close()
    return df


def ranking_atual():
    """Carrega o que o score precisa e devolve o ranking completo."""
    return scoring.calcular_score_geral(
        carregar_fundamentos_mais_recentes(),
        carregar_precos_para_score(),
    )


if __name__ == "__main__":
    fundamentos = carregar_fundamentos()
    cotacoes = carregar_cotacoes()
    posicoes = carregar_posicoes()

    print("Fundamentos:", fundamentos.shape)
    print("Cotacoes:", cotacoes.shape)
    print("Posicoes:", posicoes.shape)

    print("\nRanking geral (fundamentalista + preco):\n")
    ranking = ranking_atual()

    # scores em 1 casa; yields em 4, senao 0,0823 apareceria como 0,1
    ranking_exibicao = ranking.round(1)
    colunas_derivadas = ["earnings_yield", "book_to_market"]
    ranking_exibicao[colunas_derivadas] = ranking[colunas_derivadas].round(4)
    print(ranking_exibicao.to_string())
