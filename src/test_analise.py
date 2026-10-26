"""Testes dos carregadores do analise.py.

Roda sem pytest, no mesmo estilo dos outros scripts de teste do projeto:

    cd src && python test_analise.py

Banco temporario e dados sinteticos. Nada aqui toca o data/acoes.db.

Existe por causa do BUG-01: o ranking rodou por semanas sobre o fundamento
mais ANTIGO do banco sem dar erro nenhum. Nao havia teste que pegasse isso,
porque escolher a linha certa nao parece "logica de calculo" - mas e a entrada
de todo o calculo. Os testes 1 a 4 existem para esse bug nao voltar.
"""

import sqlite3
import tempfile
from pathlib import Path

import analise
import banco


class BancoTemporario:
    """Troca o banco de verdade por um arquivo descartavel durante o teste."""

    def __enter__(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.caminho = Path(self.pasta.name) / "teste.db"

        self.originais = (banco.CAMINHO_BANCO, analise.CAMINHO_BANCO, banco.fazer_backup)

        banco.CAMINHO_BANCO = self.caminho
        analise.CAMINHO_BANCO = self.caminho
        banco.fazer_backup = lambda: None
        banco.criar_tabelas()
        return self

    def __exit__(self, *_):
        banco.CAMINHO_BANCO, analise.CAMINHO_BANCO, banco.fazer_backup = self.originais
        self.pasta.cleanup()
        return False

    def gravar_fundamento(self, ticker, data_br, iso, pl):
        conexao = sqlite3.connect(self.caminho)
        conexao.execute(
            "INSERT INTO fundamentos (ticker, data, hora_coleta, pl, data_hora_iso) "
            "VALUES (?, ?, '10:00:00', ?, ?)",
            (ticker, data_br, pl, iso),
        )
        conexao.commit()
        conexao.close()

    def gravar_cotacao(self, ticker, preco, data="2026-10-01"):
        conexao = sqlite3.connect(self.caminho)
        conexao.execute(
            "INSERT OR IGNORE INTO cotacoes_historicas "
            "(ticker, data, fechamento, fechamento_ajustado, coletado_em) "
            "VALUES (?, ?, ?, ?, 'teste')",
            (ticker, data, preco, preco),
        )
        conexao.commit()
        conexao.close()


# --------------------------------------------------------------------------
# 1. O BUG-01 em si: texto dd/mm/aaaa nao ordena por tempo
# --------------------------------------------------------------------------
def teste_01_pega_o_fundamento_mais_recente_e_nao_o_maior_em_texto():
    with BancoTemporario() as temporario:
        # '31/08/2026' > '14/09/2026' na comparacao de texto, porque '3' > '1'.
        # E a data real de agosto e ANTERIOR a de setembro.
        temporario.gravar_fundamento("PETR4", "31/08/2026", "2026-08-31 10:00:00", pl=10.0)
        temporario.gravar_fundamento("PETR4", "14/09/2026", "2026-09-14 10:00:00", pl=20.0)

        df = analise.carregar_fundamentos_mais_recentes()

        assert len(df) == 1, f"esperava 1 linha por ticker, veio {len(df)}"
        assert df.loc["PETR4", "pl"] == 20.0, (
            "pegou o fundamento de agosto em vez do de setembro -- e o BUG-01: "
            "MAX() sobre a coluna `data` compara texto, nao tempo"
        )
        assert df.loc["PETR4", "data"] == "14/09/2026"


def teste_02_mesma_armadilha_com_virada_de_mes_e_de_ano():
    with BancoTemporario() as temporario:
        # '31/12/2025' > '05/01/2026' em texto, e e um ano mais velho
        temporario.gravar_fundamento("VALE3", "31/12/2025", "2025-12-31 10:00:00", pl=1.0)
        temporario.gravar_fundamento("VALE3", "05/01/2026", "2026-01-05 10:00:00", pl=2.0)

        df = analise.carregar_fundamentos_mais_recentes()
        assert df.loc["VALE3", "pl"] == 2.0, "a virada de ano cai na mesma armadilha"


def teste_03_continua_certo_quando_o_texto_por_acaso_concorda():
    with BancoTemporario() as temporario:
        # aqui a ordem textual e a cronologica batem; nao pode quebrar
        temporario.gravar_fundamento("ITUB4", "01/09/2026", "2026-09-01 10:00:00", pl=5.0)
        temporario.gravar_fundamento("ITUB4", "02/09/2026", "2026-09-02 10:00:00", pl=6.0)

        df = analise.carregar_fundamentos_mais_recentes()
        assert df.loc["ITUB4", "pl"] == 6.0


def teste_04_um_registro_por_ticker_com_varios_tickers():
    with BancoTemporario() as temporario:
        for ticker, pl_antigo, pl_novo in [("PETR4", 10.0, 11.0), ("VALE3", 20.0, 21.0)]:
            temporario.gravar_fundamento(ticker, "31/08/2026", "2026-08-31 10:00:00", pl_antigo)
            temporario.gravar_fundamento(ticker, "14/09/2026", "2026-09-14 10:00:00", pl_novo)

        df = analise.carregar_fundamentos_mais_recentes()

        assert len(df) == 2, f"esperava 2 linhas, uma por ticker, veio {len(df)}"
        assert df.loc["PETR4", "pl"] == 11.0
        assert df.loc["VALE3", "pl"] == 21.0


def teste_05_ticker_com_um_unico_registro_aparece():
    with BancoTemporario() as temporario:
        temporario.gravar_fundamento("WEGE3", "14/09/2026", "2026-09-14 10:00:00", pl=30.0)

        df = analise.carregar_fundamentos_mais_recentes()
        assert df.loc["WEGE3", "pl"] == 30.0


# --------------------------------------------------------------------------
# 6. A outra fragilidade do carregamento: a ordem das cotacoes
# --------------------------------------------------------------------------
def teste_06_precos_vem_da_serie_historica_ordenados_por_data():
    with BancoTemporario() as temporario:
        # gravados fora de ordem de proposito
        temporario.gravar_cotacao("PETR4", 30.0, "2026-10-03")
        temporario.gravar_cotacao("PETR4", 10.0, "2026-10-01")
        temporario.gravar_cotacao("PETR4", 20.0, "2026-10-02")

        df = analise.carregar_precos_para_score()

        assert list(df["fechamento"]) == [10.0, 20.0, 30.0], (
            "a serie tem que sair ordenada por data: o score de reversao usa "
            "a ultima observacao como preco atual"
        )
        assert "fechamento_ajustado" in df.columns, (
            "o score usa o ajustado; sem ele o dia do provento vira queda"
        )


def teste_07_carregador_le_cotacoes_historicas_e_nao_cotacoes():
    with BancoTemporario() as temporario:
        temporario.gravar_cotacao("PETR4", 50.0)
        # uma linha na tabela de coleta, que NAO deve ser usada
        conexao = sqlite3.connect(temporario.caminho)
        conexao.execute(
            "INSERT INTO cotacoes (ticker, data, hora_coleta, preco) "
            "VALUES ('PETR4', '01/01/2026', '10:00:00', 999.0)")
        conexao.commit(); conexao.close()

        df = analise.carregar_precos_para_score()

        assert list(df["fechamento"]) == [50.0], (
            "voltou a ler a tabela `cotacoes`, que e a serie de COLETA -- "
            "varias linhas por dia e so nos dias em que o loop rodou"
        )


if __name__ == "__main__":
    testes = [valor for nome, valor in sorted(globals().items()) if nome.startswith("teste_")]

    falhas = 0
    for teste in testes:
        try:
            teste()
        except AssertionError as erro:
            falhas += 1
            print(f"FALHOU  {teste.__name__}")
            print(f"        {erro}")
        else:
            print(f"ok      {teste.__name__}")

    print(f"\n{len(testes) - falhas}/{len(testes)} testes passaram")

    print("\nTabela de conferencia manual -- por que MAX(data) escolhe errado:\n")
    pares = [
        ("31/08/2026", "14/09/2026"),
        ("31/12/2025", "05/01/2026"),
        ("02/09/2026", "01/09/2026"),
        ("30/09/2026", "01/10/2026"),
    ]
    print(f"{'data A':12s} {'data B':12s} {'maior em texto':16s} {'maior no tempo':16s} {'concordam?'}")
    for a, b in pares:
        maior_texto = max(a, b)
        def chave(d):
            dia, mes, ano = d.split("/")
            return (ano, mes, dia)
        maior_tempo = max(a, b, key=chave)
        print(f"{a:12s} {b:12s} {maior_texto:16s} {maior_tempo:16s} "
              f"{'sim' if maior_texto == maior_tempo else 'NAO'}")
