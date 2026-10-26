"""Testes da tabela `indices` e dos coletores de benchmark.

Roda sem pytest, no mesmo estilo dos outros scripts de teste do projeto:

    cd src && python test_indices.py

Banco temporario e dados sinteticos. Nada aqui chama a brapi nem o BCB.
"""

import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import banco
from banco import TIPO_PRECO, TIPO_TAXA_DIARIA
from indices import (
    CODIGO_IBOV,
    TIPOS,
    _converter_pontos_bcb,
    _para_formato_bcb,
    acumular_taxa_diaria,
    variacao_percentual,
)


class BancoTemporario:
    """Troca o banco de verdade por um arquivo descartavel durante o teste."""

    def __enter__(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.caminho = Path(self.pasta.name) / "teste.db"

        self.caminho_original = banco.CAMINHO_BANCO
        self.backup_original = banco.fazer_backup

        banco.CAMINHO_BANCO = self.caminho
        banco.fazer_backup = lambda: None
        banco.criar_tabelas()
        return self

    def __exit__(self, *_):
        banco.CAMINHO_BANCO = self.caminho_original
        banco.fazer_backup = self.backup_original
        self.pasta.cleanup()
        return False

    def linhas(self):
        conexao = sqlite3.connect(self.caminho)
        resultado = conexao.execute(
            "SELECT codigo, data, valor, tipo FROM indices ORDER BY codigo, data"
        ).fetchall()
        conexao.close()
        return resultado


def data_de_hoje():
    return banco.hoje_b3()


def data_de_ontem():
    ontem = datetime.strptime(banco.hoje_b3(), "%Y-%m-%d") - timedelta(days=1)
    return ontem.strftime("%Y-%m-%d")


# --------------------------------------------------------------------------
# 1. Conversao de formato do BCB (data brasileira, valor como string)
# --------------------------------------------------------------------------
def teste_01_data_iso_vira_formato_do_bcb():
    assert _para_formato_bcb("2026-07-28") == "28/07/2026"
    assert _para_formato_bcb("2026-01-05") == "05/01/2026"


def teste_02_resposta_do_bcb_vira_data_iso_e_float():
    pontos = _converter_pontos_bcb(
        [{"data": "28/07/2026", "valor": "0.052531"},
         {"data": "29/07/2026", "valor": "0.052531"}],
        "SELIC",
    )

    assert pontos == [("2026-07-28", 0.052531), ("2026-07-29", 0.052531)], (
        "o SGS manda data em DD/MM/AAAA e valor como string; os dois tem que "
        "ser normalizados na entrada"
    )


def teste_03_ponto_malformado_do_bcb_e_pulado_sem_derrubar_o_resto():
    pontos = _converter_pontos_bcb(
        [{"data": "28/07/2026", "valor": "0.05"},
         {"data": "sem data", "valor": "0.05"},
         {"data": "30/07/2026", "valor": "nao e numero"},
         {"valor": "0.05"},
         {"data": "31/07/2026", "valor": "0.06"}],
        "SELIC",
    )

    assert pontos == [("2026-07-28", 0.05), ("2026-07-31", 0.06)]


# --------------------------------------------------------------------------
# 4. Taxa diaria acumula por produtorio, nunca por soma
# --------------------------------------------------------------------------
def teste_04_acumulado_e_produtorio_e_nao_soma():
    pontos = [(f"2026-07-{dia:02d}", 0.05) for dia in range(1, 22)]  # 21 dias a 0,05%

    acumulado = acumular_taxa_diaria(pontos)
    soma_ingenua = 21 * 0.05

    assert abs(acumulado - 1.05523) < 0.0001, f"esperado ~1,05523%, veio {acumulado}"
    assert acumulado > soma_ingenua, (
        "somar taxa diaria subestima o rendimento; com Selic de dois digitos "
        "e serie longa a diferenca deixa de ser detalhe"
    )


def teste_05_acumulado_de_serie_vazia_e_zero():
    assert acumular_taxa_diaria([]) == 0.0


def teste_06_acumulado_de_um_dia_devolve_a_propria_taxa():
    assert abs(acumular_taxa_diaria([("2026-07-28", 0.052531)]) - 0.052531) < 1e-9


# --------------------------------------------------------------------------
# 7. Indice de nivel acumula por variacao percentual
# --------------------------------------------------------------------------
def teste_07_variacao_percentual_do_ibov():
    pontos = [("2026-07-28", 100000.0), ("2026-08-28", 105000.0)]
    assert abs(variacao_percentual(pontos) - 5.0) < 1e-9


def teste_08_variacao_percentual_aceita_queda():
    pontos = [("2026-07-28", 200000.0), ("2026-08-28", 180000.0)]
    assert abs(variacao_percentual(pontos) - (-10.0)) < 1e-9


def teste_09_variacao_percentual_sem_dois_pontos_e_none():
    assert variacao_percentual([]) is None
    assert variacao_percentual([("2026-07-28", 100000.0)]) is None, (
        "com um ponto so nao existe variacao para calcular"
    )


# --------------------------------------------------------------------------
# 10. Os dois tipos estao mapeados certo
# --------------------------------------------------------------------------
def teste_10_tipos_dos_codigos():
    assert TIPOS[CODIGO_IBOV] == TIPO_PRECO, "Ibovespa e nivel de indice"
    assert TIPOS["SELIC"] == TIPO_TAXA_DIARIA
    assert TIPOS["CDI"] == TIPO_TAXA_DIARIA


def teste_11_tipo_invalido_falha_alto():
    with BancoTemporario():
        try:
            banco.salvar_indices("IBOV", "qualquer_coisa", [("2026-07-28", 100.0)])
        except ValueError:
            return
        raise AssertionError(
            "tipo invalido passou batido; o `tipo` e o que decide se a leitura "
            "faz variacao percentual ou produtorio, entao errar nele e grave"
        )


# --------------------------------------------------------------------------
# 12. Gravacao
# --------------------------------------------------------------------------
def teste_12_grava_indice_de_preco_e_de_taxa():
    with BancoTemporario() as temporario:
        banco.salvar_indices("IBOV", TIPO_PRECO, [("2026-07-28", 136000.5)])
        banco.salvar_indices("CDI", TIPO_TAXA_DIARIA, [("2026-07-28", 0.052531)])

        assert temporario.linhas() == [
            ("CDI", "2026-07-28", 0.052531, TIPO_TAXA_DIARIA),
            ("IBOV", "2026-07-28", 136000.5, TIPO_PRECO),
        ]


def teste_13_codigo_e_normalizado_para_maiusculo():
    with BancoTemporario() as temporario:
        banco.salvar_indices("  cdi  ", TIPO_TAXA_DIARIA, [("2026-07-28", 0.05)])
        assert temporario.linhas()[0][0] == "CDI"


def teste_14_rodar_duas_vezes_nao_duplica():
    with BancoTemporario() as temporario:
        pontos = [("2026-07-28", 0.05), ("2026-07-29", 0.05)]

        primeira = banco.salvar_indices("CDI", TIPO_TAXA_DIARIA, pontos)
        segunda = banco.salvar_indices("CDI", TIPO_TAXA_DIARIA, pontos)

        assert primeira.novas == 2
        assert segunda.novas == 0, (
            f"segunda execucao gravou {segunda.novas} -- o backfill mensal "
            f"duplicaria a serie de taxas e o acumulado sairia errado"
        )
        assert len(temporario.linhas()) == 2


def teste_15_codigos_diferentes_coexistem_no_mesmo_dia():
    with BancoTemporario() as temporario:
        banco.salvar_indices("SELIC", TIPO_TAXA_DIARIA, [("2026-07-28", 0.052531)])
        resultado = banco.salvar_indices("CDI", TIPO_TAXA_DIARIA, [("2026-07-28", 0.052531)])

        assert resultado.novas == 1, "o UNIQUE e por (codigo, data), nao so por data"
        assert len(temporario.linhas()) == 2


def teste_16_valor_ausente_e_descartado():
    with BancoTemporario() as temporario:
        resultado = banco.salvar_indices("CDI", TIPO_TAXA_DIARIA, [
            ("2026-07-28", 0.05),
            ("2026-07-29", None),
            (None, 0.05),
        ])

        assert (resultado.novas, resultado.descartadas) == (1, 2)
        assert len(temporario.linhas()) == 1


def teste_17_dia_de_hoje_e_ignorado_so_com_pregao_aberto():
    original = banco.data_limite_para_historico
    banco.data_limite_para_historico = lambda momento=None: banco.hoje_b3()
    try:
        with BancoTemporario() as temporario:
            resultado = banco.salvar_indices("IBOV", TIPO_PRECO, [
                (data_de_ontem(), 136000.0),
                (data_de_hoje(), 999999.0),
            ])

            assert resultado.novas == 1
            assert resultado.em_andamento == 1, (
                "o nivel do Ibovespa de hoje ainda muda ate o fechamento"
            )
            assert temporario.linhas()[0][1] == data_de_ontem()
    finally:
        banco.data_limite_para_historico = original


def teste_17b_dia_de_hoje_entra_depois_do_fechamento():
    original = banco.data_limite_para_historico
    banco.data_limite_para_historico = lambda momento=None: None
    try:
        with BancoTemporario() as temporario:
            resultado = banco.salvar_indices("IBOV", TIPO_PRECO, [
                (data_de_hoje(), 176608.23),
            ])

            assert resultado.novas == 1, (
                "fechado o pregao, o nivel do dia e final e tem que entrar"
            )
            assert temporario.linhas()[0][2] == 176608.23
    finally:
        banco.data_limite_para_historico = original


def teste_18_resumo_reporta_codigo_tipo_e_periodo():
    with BancoTemporario():
        banco.salvar_indices("IBOV", TIPO_PRECO, [
            ("2026-07-28", 136000.0), ("2026-07-29", 137000.0),
        ])
        banco.salvar_indices("CDI", TIPO_TAXA_DIARIA, [("2026-07-28", 0.05)])

        resumo = {linha[0]: linha[1:] for linha in banco.contar_indices()}
        assert resumo["IBOV"] == (TIPO_PRECO, 2, "2026-07-28", "2026-07-29")
        assert resumo["CDI"] == (TIPO_TAXA_DIARIA, 1, "2026-07-28", "2026-07-28")


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

    print("\nTabela de conferencia manual -- somar taxa diaria vs compor:\n")
    print(f"{'dias':>6s} {'taxa a.d. %':>12s} {'soma ingenua %':>15s} {'composto %':>12s} {'erro %':>9s}")
    for dias in (1, 21, 63, 126, 252):
        taxa = 0.0505  # ~13,5% ao ano, ordem de grandeza da Selic de out/2026
        pontos = [(f"dia {i}", taxa) for i in range(dias)]
        composto = acumular_taxa_diaria(pontos)
        soma = dias * taxa
        print(f"{dias:6d} {taxa:12.4f} {soma:15.4f} {composto:12.4f} {composto - soma:9.4f}")

    print("\n252 pregoes e um ano. Note o tamanho do erro de quem soma em vez de compor.")
