"""
Script de uso unico: cria uma transacao inicial do tipo 'compra' para cada
posicao ja existente hoje, usando quantidade/preco_medio/data_atualizacao
atuais. Nao reflete as compras reais que ja aconteceram - so da um ponto de
partida ao historico de transacoes.
"""
import sqlite3

from paths import CAMINHO_BANCO, fazer_backup
from banco import criar_tabelas, listar_posicoes


def main():
    criar_tabelas()
    fazer_backup()

    conexao = sqlite3.connect(CAMINHO_BANCO)
    cursor = conexao.cursor()

    cursor.execute("SELECT COUNT(*) FROM transacoes")
    total_existente = cursor.fetchone()[0]
    if total_existente > 0:
        print(f"transacoes ja tem {total_existente} registro(s). Backfill nao executado.")
        conexao.close()
        return

    posicoes = listar_posicoes()
    if not posicoes:
        print("Nenhuma posicao encontrada. Nada para migrar.")
        conexao.close()
        return

    for ticker, quantidade, preco_medio, data_atualizacao in posicoes:
        cursor.execute("""
            INSERT INTO transacoes (ticker, tipo, quantidade, preco, data_operacao, taxas, observacao)
            VALUES (?, 'compra', ?, ?, ?, NULL, 'backfill inicial a partir de posicoes')
        """, (ticker, quantidade, preco_medio, data_atualizacao))

    conexao.commit()
    conexao.close()
    print(f"Backfill concluido: {len(posicoes)} transacao(oes) criada(s) a partir de posicoes.")


if __name__ == "__main__":
    main()
