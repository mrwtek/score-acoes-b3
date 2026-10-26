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
    """Um registro por ticker, indexado por ticker.

    ATENCAO - BUG CONHECIDO, nao corrigido aqui de proposito:
    o MAX(data) abaixo compara a coluna `data` como TEXTO, no formato
    dd/mm/aaaa. Isso nao ordena por tempo: '31/08/2026' sai maior que
    '14/09/2026' porque '3' > '1'. Hoje os dez tickers acabam pegando o
    fundamento de 31/08 em vez do de 14/09, ou seja, o ranking roda sobre o
    dado mais ANTIGO.

    O conserto e trocar por data_hora_iso, mas isso muda todos os numeros do
    ranking - e o criterio de aceite do P1-1 era justamente "ranking sai
    igual", que e o que prova que a extracao nao quebrou nada. Separado de
    proposito: refatoracao e mudanca de comportamento nao entram no mesmo
    commit. Ver ESTADO.md.
    """
    conexao = sqlite3.connect(CAMINHO_BANCO)
    df = pd.read_sql_query("""
        SELECT f.*
        FROM fundamentos f
        INNER JOIN (
            SELECT ticker, MAX(data) AS data_mais_recente
            FROM fundamentos
            GROUP BY ticker
        ) ultimo
        ON f.ticker = ultimo.ticker AND f.data = ultimo.data_mais_recente
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
