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
import setores
import validacao
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
    """Serie diaria de `cotacoes_historicas`, para o score de reversao (P1-3).

    Trocou a tabela `cotacoes` por esta. A `cotacoes` e a serie de COLETA:
    varias linhas por dia, so o preco do momento, e so existe nos dias em que
    o loop rodou -- eram 7 dias contra os 63 pregoes de verdade que a
    `cotacoes_historicas` ja tem. O score de reversao estava sendo calculado
    sobre sete observacoes.

    Traz os dois fechamentos: o ajustado, que e o que entra na conta (no dia
    do provento o preco cai sem a empresa ter piorado), e o cru, que e o que
    aparece na tela e serve para conferencia.
    """
    conexao = sqlite3.connect(CAMINHO_BANCO)
    df = pd.read_sql_query("""
        SELECT ticker, data, fechamento, fechamento_ajustado
        FROM cotacoes_historicas
        ORDER BY ticker, data
    """, conexao)
    conexao.close()
    return df


def fundamentos_validados():
    """(fundamentos, relatorio) com os valores impossiveis virados em ausentes.

    A validacao fica entre carregar e pontuar, nao dentro do carregador: quem
    quiser o dado cru da BolsAI, para conferir o que foi recusado, usa
    carregar_fundamentos_mais_recentes() direto.
    """
    df = carregar_fundamentos_mais_recentes()
    return validacao.validar_dataframe(df)


def ranking_atual():
    """Carrega, valida e devolve o ranking completo."""
    fundamentos, _ = fundamentos_validados()
    return scoring.calcular_ranking(fundamentos, carregar_precos_para_score())


if __name__ == "__main__":
    fundamentos = carregar_fundamentos()
    cotacoes = carregar_cotacoes()
    posicoes = carregar_posicoes()

    print("Fundamentos:", fundamentos.shape)
    print("Cotacoes:", cotacoes.shape)
    print("Posicoes:", posicoes.shape)

    print()
    validados, relatorio = fundamentos_validados()
    validacao.imprimir_relatorio(relatorio)

    sem_setor = setores.tickers_sem_setor(validados.index)
    if sem_setor:
        print(f"\nSem setor no mapa (pontuam tudo): {', '.join(sem_setor)}")
        print("Acrescente em src/setores.py para as regras de setor valerem.")

    print("\nRanking fundamentalista:\n")
    ranking = scoring.calcular_ranking(validados, carregar_precos_para_score())

    # scores em 1 casa; yields em 4, senao 0,0823 apareceria como 0,1
    ranking_exibicao = ranking.round(1)
    colunas_derivadas = ["earnings_yield", "book_to_market"]
    ranking_exibicao[colunas_derivadas] = ranking[colunas_derivadas].round(4)

    # a cobertura vira uma coluna so, legivel: "7 de 11"
    ranking_exibicao["cobertura"] = [
        f"{int(usados)} de {int(aplicaveis)}"
        for usados, aplicaveis in zip(ranking["indicadores_usados"],
                                      ranking["indicadores_aplicaveis"])
    ]
    # a janela do score de reversao vira texto: "63/252" diz mais que um bool
    ranking_exibicao["janela"] = [
        f"{int(obs)}/{scoring.JANELA_REVERSAO}" + (" !" if insuf else "")
        for obs, insuf in zip(ranking["observacoes"].fillna(0),
                              ranking["dados_insuficientes"].fillna(True))
    ]
    ranking_exibicao = ranking_exibicao.drop(
        columns=["indicadores_usados", "indicadores_aplicaveis",
                 "observacoes", "dados_insuficientes", "janela_completa"]
    )
    print(ranking_exibicao.to_string())

    print("\ncobertura = indicadores que pontuaram, de quantos se aplicam ao setor.")
    print("Categoria vazia nao vira zero: sai do calculo e o peso e redistribuido.")
    print(f"janela = pregoes usados no score de reversao, de {scoring.JANELA_REVERSAO}."
          f" '!' = abaixo do minimo de {scoring.MINIMO_OBSERVACOES}, nota neutra.")
    print("score_reversao mede QUEDA, nao barateamento -- aposta contraria deliberada.")
    print("Ele e o score_fundamentalista sao lidos lado a lado, nunca somados.")
