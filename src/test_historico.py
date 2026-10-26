"""Testes do backfill de precos historicos (P3-4).

Roda sem pytest, no mesmo estilo dos outros scripts de teste do projeto:

    cd src && python test_historico.py

Todos os casos usam dados sinteticos e um banco temporario. Nada aqui toca o
data/acoes.db nem chama a API.
"""

import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import banco
from banco import FUSO_B3, _data_do_ponto, normalizar_ticker


def epoch_da_meia_noite(ano, mes, dia):
    """Epoch que a brapi manda: meia-noite em Sao Paulo, nao em UTC."""
    return int(datetime(ano, mes, dia, tzinfo=FUSO_B3).timestamp())


def ponto(ano, mes, dia, close=10.0, **extras):
    # close=None simula o pregao que volta sem fechamento; nesse caso OHLC
    # tambem nao existe, entao nao da para derivar nada dele
    base = {
        "date": epoch_da_meia_noite(ano, mes, dia),
        "open": None if close is None else close - 0.5,
        "high": None if close is None else close + 0.3,
        "low": None if close is None else close - 0.8,
        "close": close,
        "adjustedClose": close,
        "volume": 1_000_000,
    }
    base.update(extras)
    return base


class BancoTemporario:
    """Troca o banco de verdade por um arquivo descartavel durante o teste."""

    def __enter__(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.caminho = Path(self.pasta.name) / "teste.db"

        self.caminho_original = banco.CAMINHO_BANCO
        self.backup_original = banco.fazer_backup

        banco.CAMINHO_BANCO = self.caminho
        banco.fazer_backup = lambda: None  # nao faz backup do banco real
        banco.criar_tabelas()
        return self

    def __exit__(self, *_):
        banco.CAMINHO_BANCO = self.caminho_original
        banco.fazer_backup = self.backup_original
        self.pasta.cleanup()
        return False

    def linhas(self):
        conexao = sqlite3.connect(self.caminho)
        resultado = conexao.execute("""
            SELECT ticker, data, abertura, maxima, minima,
                   fechamento, fechamento_ajustado, volume
            FROM cotacoes_historicas ORDER BY ticker, data
        """).fetchall()
        conexao.close()
        return resultado


# --------------------------------------------------------------------------
# 1. Normalizacao de ticker acontece na escrita
# --------------------------------------------------------------------------
def teste_01_normalizar_ticker():
    assert normalizar_ticker("petr4") == "PETR4"
    assert normalizar_ticker("  VALE3  ") == "VALE3"
    assert normalizar_ticker("PETR4.SA") == "PETR4", "o sufixo .SA tem que sair"
    assert normalizar_ticker("petr4.sa") == "PETR4"
    assert normalizar_ticker("MXRF11") == "MXRF11", "FII nao pode ser alterado"


def teste_02_normalizacao_vale_para_o_que_e_gravado():
    with BancoTemporario() as temporario:
        banco.salvar_cotacoes_historicas("petr4.sa", [ponto(2026, 7, 28)])
        assert temporario.linhas()[0][0] == "PETR4", (
            "o ticker foi gravado sem normalizar -- o join entre as fontes quebra assim"
        )


# --------------------------------------------------------------------------
# 3. A data sai do epoch no fuso da B3, nao no fuso da maquina
# --------------------------------------------------------------------------
def teste_03_data_vem_do_fuso_da_b3():
    assert _data_do_ponto({"date": epoch_da_meia_noite(2026, 7, 28)}) == "2026-07-28"
    assert _data_do_ponto({"date": epoch_da_meia_noite(2026, 10, 26)}) == "2026-10-26"


def teste_04_epoch_cru_da_brapi_cai_no_dia_certo():
    # valor real observado na resposta da brapi em 26/10/2026: 03:00 UTC,
    # que e meia-noite em Sao Paulo
    assert _data_do_ponto({"date": 1785207600}) == "2026-07-28"
    assert _data_do_ponto({"date": 1792983600}) == "2026-10-26"

    conferencia = datetime.fromtimestamp(1785207600, tz=timezone.utc)
    assert conferencia.hour == 3, "premissa do teste mudou: o epoch nao e mais 03:00 UTC"


def teste_05_data_invalida_vira_none():
    assert _data_do_ponto({}) is None, "ponto sem campo date"
    assert _data_do_ponto({"date": None}) is None
    assert _data_do_ponto({"date": "quarta-feira"}) is None


# --------------------------------------------------------------------------
# 6. Gravacao: todas as colunas chegam ao banco
# --------------------------------------------------------------------------
def teste_06_grava_todas_as_colunas():
    with BancoTemporario() as temporario:
        banco.salvar_cotacoes_historicas("PETR4", [
            {"date": epoch_da_meia_noite(2026, 7, 28), "open": 41.02, "high": 41.77,
             "low": 40.88, "close": 41.21, "adjustedClose": 40.0986, "volume": 29946800},
        ])

        ticker, data, abertura, maxima, minima, fechamento, ajustado, volume = temporario.linhas()[0]
        assert (ticker, data) == ("PETR4", "2026-07-28")
        assert (abertura, maxima, minima) == (41.02, 41.77, 40.88)
        assert fechamento == 41.21
        assert ajustado == 40.0986, "o ajustado nao pode ser confundido com o fechamento cru"
        assert volume == 29946800


# --------------------------------------------------------------------------
# 7. Reexecucao: o backfill roda de novo sem duplicar
# --------------------------------------------------------------------------
def teste_07_rodar_duas_vezes_nao_duplica():
    with BancoTemporario() as temporario:
        pontos = [ponto(2026, 7, 28), ponto(2026, 7, 29, close=11.0)]

        primeira = banco.salvar_cotacoes_historicas("PETR4", pontos)
        segunda = banco.salvar_cotacoes_historicas("PETR4", pontos)
        novas_primeira, novas_segunda = primeira.novas, segunda.novas

        assert novas_primeira == 2, f"primeira execucao deveria gravar 2, gravou {novas_primeira}"
        assert novas_segunda == 0, (
            f"segunda execucao gravou {novas_segunda} -- o UNIQUE(ticker, data) "
            f"nao esta segurando e o backfill periodico duplicaria a serie"
        )
        assert len(temporario.linhas()) == 2


def teste_08_reexecucao_preserva_o_valor_original():
    with BancoTemporario() as temporario:
        banco.salvar_cotacoes_historicas("PETR4", [ponto(2026, 7, 28, close=41.21)])
        banco.salvar_cotacoes_historicas("PETR4", [ponto(2026, 7, 28, close=99.99)])

        assert temporario.linhas()[0][5] == 41.21, (
            "INSERT OR IGNORE deveria manter a linha antiga, nao sobrescrever"
        )


def teste_09_dias_novos_entram_sem_mexer_nos_antigos():
    with BancoTemporario() as temporario:
        banco.salvar_cotacoes_historicas("PETR4", [ponto(2026, 7, 28), ponto(2026, 7, 29)])
        novas = banco.salvar_cotacoes_historicas("PETR4", [ponto(2026, 7, 29), ponto(2026, 7, 30)]).novas

        assert novas == 1, f"so o dia 30 era novo, mas gravou {novas}"
        assert len(temporario.linhas()) == 3, "e assim que a janela deslizante estende a serie"


# --------------------------------------------------------------------------
# 10. Casos de borda do dado que chega da API
# --------------------------------------------------------------------------
def teste_10_ponto_sem_fechamento_e_descartado():
    with BancoTemporario() as temporario:
        resultado = banco.salvar_cotacoes_historicas("PETR4", [
            ponto(2026, 7, 28),
            ponto(2026, 7, 29, close=None),
        ])

        assert (resultado.novas, resultado.descartadas) == (1, 1), f"esperado (1, 1), veio {resultado}"
        assert len(temporario.linhas()) == 1, "linha sem fechamento nao serve para calcular retorno"


def teste_11_ponto_sem_data_e_descartado():
    with BancoTemporario() as temporario:
        resultado = banco.salvar_cotacoes_historicas("PETR4", [
            ponto(2026, 7, 28),
            {"close": 10.0, "volume": 1},
        ])

        assert (resultado.novas, resultado.descartadas) == (1, 1)
        assert len(temporario.linhas()) == 1


def teste_12_ajustado_ausente_vira_null_e_nao_copia_o_fechamento():
    with BancoTemporario() as temporario:
        banco.salvar_cotacoes_historicas("PETR4", [ponto(2026, 7, 28, close=41.21, adjustedClose=None)])

        fechamento, ajustado = temporario.linhas()[0][5:7]
        assert fechamento == 41.21
        assert ajustado is None, (
            "copiar o fechamento para o ajustado esconderia proventos nao contabilizados; "
            "NULL deixa o buraco visivel"
        )


def teste_13_lista_vazia_nao_quebra():
    with BancoTemporario() as temporario:
        resultado = banco.salvar_cotacoes_historicas("PETR4", [])
        assert (resultado.novas, resultado.descartadas) == (0, 0)
        assert temporario.linhas() == []


# --------------------------------------------------------------------------
# 14. O UNIQUE e por (ticker, data), nao so por data
# --------------------------------------------------------------------------
def teste_14_tickers_diferentes_coexistem_no_mesmo_dia():
    with BancoTemporario() as temporario:
        banco.salvar_cotacoes_historicas("PETR4", [ponto(2026, 7, 28, close=41.0)])
        novas = banco.salvar_cotacoes_historicas("VALE3", [ponto(2026, 7, 28, close=55.0)]).novas

        assert novas == 1, "VALE3 foi bloqueada por uma linha de PETR4 do mesmo dia"
        assert len(temporario.linhas()) == 2


def teste_15_resumo_reporta_periodo_por_ticker():
    with BancoTemporario():
        banco.salvar_cotacoes_historicas("PETR4", [
            ponto(2026, 7, 28), ponto(2026, 7, 29), ponto(2026, 7, 30),
        ])
        banco.salvar_cotacoes_historicas("VALE3", [ponto(2026, 7, 29)])

        resumo = dict((linha[0], linha[1:]) for linha in banco.contar_cotacoes_historicas())
        assert resumo["PETR4"] == (3, "2026-07-28", "2026-07-30")
        assert resumo["VALE3"] == (1, "2026-07-29", "2026-07-29")


# --------------------------------------------------------------------------
# 16. O pregao de hoje so fica de fora ENQUANTO a sessao esta aberta
#
# A versao anterior destes testes fixava "hoje nunca entra". Isso estava
# errado e apagou 13 linhas reais em 26/10/2026 -- ver
# data_limite_para_historico() no banco.py. Agora cada teste diz
# explicitamente se o pregao esta aberto ou fechado.
# --------------------------------------------------------------------------
def ponto_de_hoje(close=10.0):
    hoje = datetime.strptime(banco.hoje_b3(), "%Y-%m-%d")
    return ponto(hoje.year, hoje.month, hoje.day, close=close)


class PregaoAberto:
    """Finge que a sessao de hoje ainda esta em andamento."""

    def __enter__(self):
        self.original = banco.data_limite_para_historico
        banco.data_limite_para_historico = lambda momento=None: banco.hoje_b3()
        return self

    def __exit__(self, *_):
        banco.data_limite_para_historico = self.original
        return False


class PregaoFechado:
    """Finge que a sessao de hoje ja terminou."""

    def __enter__(self):
        self.original = banco.data_limite_para_historico
        banco.data_limite_para_historico = lambda momento=None: None
        return self

    def __exit__(self, *_):
        banco.data_limite_para_historico = self.original
        return False


def teste_16_barra_de_hoje_e_ignorada_com_pregao_aberto():
    with BancoTemporario() as temporario, PregaoAberto():
        resultado = banco.salvar_cotacoes_historicas("PETR4", [ponto_de_hoje()])

        assert resultado.novas == 0, (
            "a barra do dia corrente foi gravada -- com INSERT OR IGNORE ela "
            "ficaria congelada errada para sempre"
        )
        assert resultado.em_andamento == 1
        assert temporario.linhas() == []


def teste_17_hoje_e_ignorado_sem_bloquear_os_dias_fechados():
    with BancoTemporario() as temporario, PregaoAberto():
        resultado = banco.salvar_cotacoes_historicas("PETR4", [
            ponto(2026, 7, 28),
            ponto(2026, 7, 29),
            ponto_de_hoje(),
        ])

        assert resultado.novas == 2, "os dois pregoes fechados tinham que entrar"
        assert resultado.em_andamento == 1
        assert len(temporario.linhas()) == 2


def teste_18_dia_em_andamento_nao_conta_como_descarte():
    with BancoTemporario(), PregaoAberto():
        resultado = banco.salvar_cotacoes_historicas("PETR4", [ponto_de_hoje()])

        assert resultado.descartadas == 0, (
            "ignorar o pregao de hoje e rotina; so dado corrompido conta como descarte"
        )


def teste_19_barra_de_hoje_ENTRA_depois_do_fechamento():
    with BancoTemporario() as temporario, PregaoFechado():
        resultado = banco.salvar_cotacoes_historicas("BBAS3", [ponto_de_hoje(close=17.47)])

        assert resultado.novas == 1, (
            "a barra de hoje foi recusada depois do fechamento. Foi assim que "
            "13 pregoes reais de 26/10/2026 foram apagados: naquele dia os "
            "bancos cairam de verdade e a regra leu isso como dado corrompido"
        )
        assert resultado.em_andamento == 0
        assert temporario.linhas()[0][5] == 17.47


def teste_20_queda_violenta_nao_e_motivo_para_descartar():
    # numeros reais de 23/10 -> 26/10/2026: BBAS3 -29,33%, confirmado no
    # Investidor10 no mesmo dia. Implausibilidade nao e criterio para apagar.
    with BancoTemporario() as temporario, PregaoFechado():
        banco.salvar_cotacoes_historicas("BBAS3", [
            ponto(2026, 10, 23, close=24.72),
            ponto_de_hoje(close=17.47),
        ])

        fechamentos = [linha[5] for linha in temporario.linhas()]
        assert fechamentos == [24.72, 17.47], (
            "a queda de 29% foi filtrada. Quando a fonte e o codigo discordam, "
            "confira com uma segunda fonte -- nao deduza do formato do numero"
        )


def teste_21_data_limite_segue_o_horario_do_pregao():
    from datetime import datetime as dt
    from banco import FUSO_B3, data_limite_para_historico

    durante = dt(2026, 10, 26, 15, 0, tzinfo=FUSO_B3)
    depois = dt(2026, 10, 26, 18, 30, tzinfo=FUSO_B3)

    assert data_limite_para_historico(durante) == "2026-10-26", "pregao aberto: exclui hoje"
    assert data_limite_para_historico(depois) is None, "pregao fechado: nao exclui nada"


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

    print("\nTabela de conferencia manual -- o que a API manda vs o que vai para o banco:\n")
    casos = {
        "pregao normal": ponto(2026, 7, 28, close=41.21),
        "com provento (ajustado < fechamento)": ponto(2026, 7, 29, close=41.21, adjustedClose=40.0986),
        "sem ajustado": ponto(2026, 7, 30, close=41.21, adjustedClose=None),
        "sem fechamento": ponto(2026, 7, 31, close=None),
        "sem data": {"close": 41.21, "volume": 1},
        "data invalida": {"date": "ontem", "close": 41.21},
    }

    print(f"{'caso':38s} {'data gravada':14s} {'fechamento':>11s} {'ajustado':>10s}  destino")
    for rotulo, caso in casos.items():
        data = _data_do_ponto(caso)
        fechamento = caso.get("close")
        ajustado = caso.get("adjustedClose")
        descartado = data is None or fechamento is None
        destino = "DESCARTADO" if descartado else "gravado"
        print(f"{rotulo:38s} {str(data):14s} {str(fechamento):>11s} {str(ajustado):>10s}  {destino}")
