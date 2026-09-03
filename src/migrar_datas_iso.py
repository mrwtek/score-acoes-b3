"""
Migracao unica (P0-3): preenche as colunas ISO (data_hora_iso / data_operacao_iso)
para linhas ja existentes em cotacoes, fundamentos e transacoes, convertendo a
partir dos campos de data em formato brasileiro ja gravados.

Nao mexe nas colunas antigas. Roda uma vez; linhas que ja tem a coluna ISO
preenchida sao ignoradas, entao rodar de novo nao faz mal.
"""

import sqlite3
from datetime import datetime

from paths import CAMINHO_BANCO
from banco import criar_tabelas


def _converter(data_str, hora_str):
    return datetime.strptime(f"{data_str} {hora_str}", "%d/%m/%Y %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")


def migrar_cotacoes(cursor):
    cursor.execute("SELECT id, data, hora_coleta FROM cotacoes WHERE data_hora_iso IS NULL")
    linhas = cursor.fetchall()
    migradas = 0

    for id_linha, data_str, hora_str in linhas:
        try:
            data_hora_iso = _converter(data_str, hora_str)
        except ValueError:
            print(f"[cotacoes] pulando id={id_linha}: nao consegui converter data='{data_str}' hora='{hora_str}'")
            continue

        cursor.execute("UPDATE cotacoes SET data_hora_iso = ? WHERE id = ?", (data_hora_iso, id_linha))
        migradas += 1

    print(f"cotacoes: {migradas} de {len(linhas)} linhas migradas.")


def migrar_fundamentos(cursor):
    cursor.execute("SELECT id, data, hora_coleta FROM fundamentos WHERE data_hora_iso IS NULL")
    linhas = cursor.fetchall()
    migradas = 0

    for id_linha, data_str, hora_str in linhas:
        try:
            data_hora_iso = _converter(data_str, hora_str)
        except ValueError:
            print(f"[fundamentos] pulando id={id_linha}: nao consegui converter data='{data_str}' hora='{hora_str}'")
            continue

        cursor.execute("UPDATE fundamentos SET data_hora_iso = ? WHERE id = ?", (data_hora_iso, id_linha))
        migradas += 1

    print(f"fundamentos: {migradas} de {len(linhas)} linhas migradas.")


def migrar_transacoes(cursor):
    cursor.execute("SELECT id, data_operacao FROM transacoes WHERE data_operacao_iso IS NULL")
    linhas = cursor.fetchall()
    migradas = 0

    for id_linha, data_operacao_str in linhas:
        try:
            data_operacao_iso = datetime.strptime(data_operacao_str, "%d/%m/%Y %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            print(f"[transacoes] pulando id={id_linha}: nao consegui converter data_operacao='{data_operacao_str}'")
            continue

        cursor.execute("UPDATE transacoes SET data_operacao_iso = ? WHERE id = ?", (data_operacao_iso, id_linha))
        migradas += 1

    print(f"transacoes: {migradas} de {len(linhas)} linhas migradas.")


def main():
    criar_tabelas()

    conexao = sqlite3.connect(CAMINHO_BANCO)
    cursor = conexao.cursor()

    migrar_cotacoes(cursor)
    migrar_fundamentos(cursor)
    migrar_transacoes(cursor)

    conexao.commit()
    conexao.close()
    print("Migracao concluida.")


if __name__ == "__main__":
    main()
