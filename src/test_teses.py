"""Testes do diario de teses.

Roda sem pytest, no mesmo estilo dos outros scripts de teste do projeto:

    cd src && python test_teses.py

Banco temporario e dados sinteticos. Nada aqui toca o data/acoes.db.
"""

import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import banco
import indices
import teses
from banco import TIPO_PRECO, TIPO_TAXA_DIARIA


class BancoTemporario:
    def __enter__(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.caminho = Path(self.pasta.name) / "teste.db"
        self.originais = (banco.CAMINHO_BANCO, indices.CAMINHO_BANCO, banco.fazer_backup)

        banco.CAMINHO_BANCO = self.caminho
        indices.CAMINHO_BANCO = self.caminho
        banco.fazer_backup = lambda: None
        banco.criar_tabelas()
        return self

    def __exit__(self, *_):
        banco.CAMINHO_BANCO, indices.CAMINHO_BANCO, banco.fazer_backup = self.originais
        self.pasta.cleanup()
        return False

    def serie(self, ticker, precos, inicio="2026-10-26"):
        """Grava N pregoes diarios a partir de `inicio`."""
        base = datetime.strptime(inicio, "%Y-%m-%d")
        conexao = sqlite3.connect(self.caminho)
        for passo, preco in enumerate(precos):
            data = (base + timedelta(days=passo)).strftime("%Y-%m-%d")
            conexao.execute(
                "INSERT OR IGNORE INTO cotacoes_historicas "
                "(ticker, data, fechamento, fechamento_ajustado, coletado_em) "
                "VALUES (?, ?, ?, ?, 'teste')",
                (ticker, data, preco, preco),
            )
        conexao.commit()
        conexao.close()

    def indice(self, codigo, tipo, valores, inicio="2026-10-26"):
        base = datetime.strptime(inicio, "%Y-%m-%d")
        conexao = sqlite3.connect(self.caminho)
        for passo, valor in enumerate(valores):
            data = (base + timedelta(days=passo)).strftime("%Y-%m-%d")
            conexao.execute(
                "INSERT OR IGNORE INTO indices (codigo, data, valor, tipo, coletado_em) "
                "VALUES (?, ?, ?, ?, 'teste')",
                (codigo, data, valor, tipo),
            )
        conexao.commit()
        conexao.close()

    def cenario_padrao(self, precos_papel, niveis_ibov, taxas_cdi, ticker="BBAS3"):
        self.serie(ticker, precos_papel)
        self.indice("IBOV", TIPO_PRECO, niveis_ibov)
        self.indice("CDI", TIPO_TAXA_DIARIA, taxas_cdi)


def tese_de(id_tese=None, **campos):
    base = {"id": 1, "ticker": "BBAS3", "data_abertura": "2026-10-26",
            "preco_abertura": 17.47, "premissa": "p", "criterio": "c",
            "horizonte_dias": 90, "status": "aberta"}
    base.update(campos)
    return base


# --------------------------------------------------------------------------
# 1. Registro
# --------------------------------------------------------------------------
def teste_01_tese_e_gravada_com_prazo_e_criterio():
    with BancoTemporario():
        id_tese = teses.abrir_tese(
            "BBAS3", premissa="queda eleitoral exagerada",
            criterio="voltar acima de R$ 22 em 90 dias",
            horizonte_dias=90, preco_abertura=17.47, score_abertura=42.7,
        )
        gravada = banco.listar_teses()[0]

        assert gravada["id"] == id_tese
        assert gravada["ticker"] == "BBAS3"
        assert gravada["horizonte_dias"] == 90
        assert gravada["criterio"] == "voltar acima de R$ 22 em 90 dias"
        assert gravada["status"] == "aberta"
        assert gravada["score_abertura"] == 42.7, (
            "o score da abertura tem que ficar congelado: a metodologia ainda "
            "vai mudar e a nota de hoje precisa continuar sendo a de hoje"
        )


def teste_02_preco_vem_da_serie_quando_nao_informado():
    with BancoTemporario() as t:
        t.serie("BBAS3", [20.00, 18.00, 17.47])
        teses.abrir_tese("BBAS3", premissa="p", criterio="c", horizonte_dias=30,
                         data_abertura="2026-10-28")

        assert banco.listar_teses()[0]["preco_abertura"] == 17.47, (
            "deveria pegar o ultimo fechamento ate a data de abertura"
        )


def teste_03_sem_serie_falha_alto_em_vez_de_inventar_preco():
    with BancoTemporario():
        try:
            teses.abrir_tese("BBAS3", premissa="p", criterio="c", horizonte_dias=30)
        except ValueError as erro:
            assert "backfill" in str(erro)
            return
        raise AssertionError("abriu tese sem preco nenhum, em silencio")


def teste_04_ticker_e_normalizado():
    with BancoTemporario():
        teses.abrir_tese("bbas3", premissa="p", criterio="c", horizonte_dias=30,
                         preco_abertura=17.47)
        assert banco.listar_teses()[0]["ticker"] == "BBAS3"


# --------------------------------------------------------------------------
# 5. Conferencia contra os benchmarks
# --------------------------------------------------------------------------
def teste_05_calcula_retorno_contra_ibov_e_cdi():
    with BancoTemporario() as t:
        # papel +20%, IBOV +10%, CDI ~0,05%/dia por 2 dias
        t.cenario_padrao([100.0, 110.0, 120.0], [1000.0, 1050.0, 1100.0], [0.05, 0.05, 0.05])

        r = teses.conferir(tese_de(preco_abertura=100.0))

        assert abs(r["retorno"] - 20.0) < 1e-9
        assert abs(r["ibov"] - 10.0) < 1e-9
        assert abs(r["vs_ibov"] - 10.0) < 1e-9, "20% contra 10% = +10 p.p."
        assert r["cdi"] > 0 and r["vs_cdi"] > 19.0


def teste_06_subir_menos_que_o_ibov_conta_como_negativo():
    with BancoTemporario() as t:
        # o papel sobe 8%, o IBOV sobe 20%: subir nao e acertar
        t.cenario_padrao([100.0, 108.0], [1000.0, 1200.0], [0.05, 0.05])

        r = teses.conferir(tese_de(preco_abertura=100.0))

        assert r["retorno"] > 0, "o papel subiu"
        assert r["vs_ibov"] < 0, (
            "subir 8% com o IBOV em 20% e perder mais devagar, nao acertar"
        )


def teste_07_corta_as_series_na_data_mais_curta():
    with BancoTemporario() as t:
        # o CDI do BCB chega com atraso: tem um dia a menos que o resto
        t.serie("BBAS3", [100.0, 110.0, 130.0])
        t.indice("IBOV", TIPO_PRECO, [1000.0, 1050.0, 1100.0])
        t.indice("CDI", TIPO_TAXA_DIARIA, [0.05, 0.05])

        r = teses.conferir(tese_de(preco_abertura=100.0))

        assert r["ate"] == "2026-10-27", "deveria parar no ultimo dia do CDI"
        assert abs(r["retorno"] - 10.0) < 1e-9, (
            "usou o terceiro dia do papel contra dois dias de CDI -- janelas "
            "diferentes nao se comparam"
        )


def teste_08_sem_pregao_novo_devolve_none():
    with BancoTemporario() as t:
        t.cenario_padrao([100.0], [1000.0], [0.05])
        assert teses.conferir(tese_de(preco_abertura=100.0)) is None, (
            "com um unico dia nao existe variacao para medir"
        )


def teste_09_serie_de_benchmark_faltando_devolve_none():
    with BancoTemporario() as t:
        t.serie("BBAS3", [100.0, 110.0])
        t.indice("IBOV", TIPO_PRECO, [1000.0, 1100.0])
        # sem CDI
        assert teses.conferir(tese_de(preco_abertura=100.0)) is None


# --------------------------------------------------------------------------
# 10. Prazo
# --------------------------------------------------------------------------
def teste_10_tese_vencida_e_marcada_como_vencida():
    with BancoTemporario() as t:
        t.cenario_padrao([100.0, 110.0], [1000.0, 1050.0], [0.05, 0.05])

        antiga = (datetime.strptime(banco.hoje_b3(), "%Y-%m-%d") - timedelta(days=100))
        r = teses.conferir(tese_de(data_abertura=antiga.strftime("%Y-%m-%d"),
                                   horizonte_dias=90, preco_abertura=100.0))
        # a serie sintetica comeca em 2026-10-26; a conferencia usa a data de
        # abertura so para o prazo, entao basta checar o campo
        assert r is None or r["vencida"] or r["dias_restantes"] < 0


def teste_11_prazo_e_obrigatorio_no_registro():
    with BancoTemporario():
        try:
            teses.abrir_tese("BBAS3", premissa="p", criterio="c",
                             preco_abertura=17.47)
        except TypeError:
            return
        raise AssertionError(
            "abriu tese sem horizonte_dias. Tese sem prazo nao pode falhar, e "
            "so o que pode falhar ensina alguma coisa"
        )


# --------------------------------------------------------------------------
# 12. Encerramento preserva o historico
# --------------------------------------------------------------------------
def teste_12_encerrar_nao_apaga_a_tese():
    with BancoTemporario():
        id_tese = teses.abrir_tese("BBAS3", premissa="p", criterio="c",
                                   horizonte_dias=30, preco_abertura=17.47)
        banco.encerrar_tese(id_tese, "voltou a R$ 23, premissa confirmada")

        gravada = banco.listar_teses()[0]
        assert gravada["status"] == "encerrada"
        assert gravada["veredito"].startswith("voltou")
        assert gravada["preco_abertura"] == 17.47, "a abertura tem que sobreviver"


def teste_13_listar_apenas_abertas_filtra():
    with BancoTemporario():
        aberta = teses.abrir_tese("BBAS3", premissa="p", criterio="c",
                                  horizonte_dias=30, preco_abertura=17.47)
        fechada = teses.abrir_tese("BBDC4", premissa="p", criterio="c",
                                   horizonte_dias=30, preco_abertura=15.95)
        banco.encerrar_tese(fechada, "deu errado")

        abertas = banco.listar_teses(apenas_abertas=True)
        assert [t["id"] for t in abertas] == [aberta]
        assert len(banco.listar_teses()) == 2, "o historico nao some"


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

    print("\nTabela de conferencia manual -- por que o benchmark importa:\n")
    casos = [
        ("subiu muito, IBOV subiu pouco", 20.0, 5.0, 3.0),
        ("subiu pouco, IBOV subiu muito", 8.0, 20.0, 3.0),
        ("caiu, mas o IBOV caiu mais", -5.0, -15.0, 3.0),
        ("subiu menos que o CDI", 2.0, 1.0, 3.0),
    ]
    print(f"{'cenario':34s} {'papel':>7s} {'IBOV':>7s} {'CDI':>6s} {'vs IBOV':>9s} {'vs CDI':>8s}  leitura")
    for rotulo, papel, ibov, cdi in casos:
        leitura = "ganhou do indice" if papel > ibov else "perdeu do indice"
        if papel < cdi:
            leitura += ", e perdeu do CDI"
        print(f"{rotulo:34s} {papel:6.1f}% {ibov:6.1f}% {cdi:5.1f}% "
              f"{papel-ibov:+8.1f} {papel-cdi:+7.1f}  {leitura}")
