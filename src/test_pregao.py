"""Testes do P0-5: coleta automatica restrita ao horario de pregao.

Roda sem pytest, no mesmo estilo dos outros scripts de teste do projeto:

    cd src && python test_pregao.py

Todos os casos usam datetimes sinteticos e deterministicos: nenhum depende da
hora em que o teste roda, nem do banco, nem das APIs.

Calendario usado como referencia (setembro de 2026):
    07/09 seg (feriado: Independencia)   09/09 qua   11/09 sex
    12/09 sab   13/09 dom                14/09 seg
"""

import contextlib
import inspect
import io
import threading
import time
from datetime import datetime, timezone

import main
from main import (
    FUSO_B3,
    HORA_ABERTURA,
    HORA_FECHAMENTO,
    esta_no_horario_de_pregao,
)


def momento(dia, hora, minuto=0):
    """Monta um datetime de setembro/2026 no fuso de Brasilia."""
    return datetime(2026, 9, dia, hora, minuto, tzinfo=FUSO_B3)


# --------------------------------------------------------------------------
# 1. O caso normal: dia util no meio do pregao
# --------------------------------------------------------------------------
def teste_01_dia_util_dentro_da_janela():
    assert esta_no_horario_de_pregao(momento(9, 14)), "quarta 14h deveria coletar"
    assert esta_no_horario_de_pregao(momento(8, 11, 30)), "terca 11h30 deveria coletar"
    assert esta_no_horario_de_pregao(momento(11, 16, 45)), "sexta 16h45 deveria coletar"


# --------------------------------------------------------------------------
# 2. O bug do P0-5: madrugada e noite nao podem mais coletar
# --------------------------------------------------------------------------
def teste_02_fora_da_janela_no_dia_util():
    assert not esta_no_horario_de_pregao(momento(9, 3)), "quarta 3h da manha nao pode coletar"
    assert not esta_no_horario_de_pregao(momento(9, 0)), "quarta meia-noite nao pode coletar"
    assert not esta_no_horario_de_pregao(momento(9, 21)), "quarta 21h nao pode coletar"
    assert not esta_no_horario_de_pregao(momento(9, 23, 59)), "quarta 23h59 nao pode coletar"


# --------------------------------------------------------------------------
# 3. Fim de semana esta fora em qualquer hora
# --------------------------------------------------------------------------
def teste_03_fim_de_semana_nunca_coleta():
    assert not esta_no_horario_de_pregao(momento(12, 14)), "sabado 14h nao pode coletar"
    assert not esta_no_horario_de_pregao(momento(13, 11)), "domingo 11h nao pode coletar"
    # inclusive nas horas que seriam validas num dia util
    for hora in range(24):
        assert not esta_no_horario_de_pregao(momento(12, hora)), f"sabado {hora}h coletou"
        assert not esta_no_horario_de_pregao(momento(13, hora)), f"domingo {hora}h coletou"


# --------------------------------------------------------------------------
# 4. As bordas exatas da janela (10h inclusivo, 18h exclusivo)
# --------------------------------------------------------------------------
def teste_04_bordas_da_janela():
    assert not esta_no_horario_de_pregao(momento(9, 9, 59)), "9h59 esta antes da abertura"
    assert esta_no_horario_de_pregao(momento(9, 10, 0)), "10h00 em ponto abre a janela"
    assert esta_no_horario_de_pregao(momento(9, 17, 59)), "17h59 e a ultima coleta do dia"
    assert not esta_no_horario_de_pregao(momento(9, 18, 0)), (
        "18h00 em ponto ja esta fora: HORA_FECHAMENTO e exclusivo"
    )
    assert not esta_no_horario_de_pregao(momento(9, 18, 30)), "18h30 esta fora"


# --------------------------------------------------------------------------
# 5. As bordas da semana (sexta fecha, segunda abre)
# --------------------------------------------------------------------------
def teste_05_bordas_da_semana():
    assert esta_no_horario_de_pregao(momento(11, 17, 59)), "sexta 17h59 ainda coleta"
    assert not esta_no_horario_de_pregao(momento(11, 18, 0)), "sexta 18h fecha a semana"
    assert not esta_no_horario_de_pregao(momento(14, 9, 59)), "segunda 9h59 ainda nao abriu"
    assert esta_no_horario_de_pregao(momento(14, 10, 0)), "segunda 10h abre a semana"


# --------------------------------------------------------------------------
# 6. LIMITACAO ACEITA: feriado em dia util ainda coleta (nao e bug)
# --------------------------------------------------------------------------
def teste_06_feriado_em_dia_util_ainda_coleta():
    # 07/09/2026 e uma segunda-feira, feriado da Independencia. Sem calendario
    # de feriados no projeto, a funcao so ve "segunda, 14h" e libera. O registro
    # repetido entra na serie -- comportamento esperado, documentado na docstring
    # de esta_no_horario_de_pregao().
    assert esta_no_horario_de_pregao(momento(7, 14)), (
        "se isto falhar, alguem implementou calendario de feriados sem atualizar "
        "a docstring e este teste"
    )


# --------------------------------------------------------------------------
# 7. O fuso e de Brasilia, nao o da maquina
# --------------------------------------------------------------------------
def teste_07_usa_fuso_de_brasilia():
    assert str(FUSO_B3) == "America/Sao_Paulo"

    # 14h em Brasilia = 17h UTC. O mesmo instante, escrito nos dois fusos, tem
    # que dar a mesma resposta -- e o que garante que rodar em servidor UTC nao
    # desloca a janela.
    em_brasilia = momento(9, 14)
    em_utc = em_brasilia.astimezone(timezone.utc)
    assert em_utc.hour == 17, "conta de referencia errada: 14h -03:00 e 17h UTC"
    assert esta_no_horario_de_pregao(em_brasilia) == esta_no_horario_de_pregao(em_utc), (
        "o mesmo instante deu respostas diferentes conforme o fuso escrito"
    )

    # 23h UTC de quarta = 20h de quarta em Brasilia: fora nos dois casos
    fora = datetime(2026, 9, 9, 23, 0, tzinfo=timezone.utc)
    assert not esta_no_horario_de_pregao(fora)

    # e a chamada sem argumento retorna bool, nao None nem numpy.bool_
    assert isinstance(esta_no_horario_de_pregao(), bool)


# --------------------------------------------------------------------------
# 8. Contrato: o que o P0-5 mexeu e o que ele nao podia mexer
# --------------------------------------------------------------------------
def teste_08_contrato_do_p0_5():
    assert (HORA_ABERTURA, HORA_FECHAMENTO) == (10, 18), "a janela pedida foi 10h-18h"

    # A coleta automatica consulta a janela; a coleta em si nao (quem decide
    # QUANDO e o loop, nao o checar_agora).
    #
    # Desde o P2-1 a checagem mora em ciclo_de_coleta(), e nao mais no corpo do
    # loop: o loop chama rodar_ciclo_protegido(), que embrulha o ciclo num
    # try/except para erro inesperado nao matar a thread. O contrato do P0-5
    # nao mudou, so desceu um nivel.
    fonte_loop = inspect.getsource(main.loop_automatico)
    fonte_ciclo = inspect.getsource(main.ciclo_de_coleta)
    assert "esta_no_horario_de_pregao" in fonte_ciclo, "o ciclo nao esta checando a janela"
    assert "rodar_ciclo_protegido" in fonte_loop, (
        "o loop deixou de passar pela guarda do P2-1 -- uma excecao volta a "
        "matar a thread de coleta"
    )
    assert "esta_no_horario_de_pregao" not in inspect.getsource(main.checar_agora), (
        "a coleta em si nao deveria decidir horario"
    )

    # o loop pula a coleta mas continua vivo: dorme igual e so sai via encerrar
    assert "encerrar" in fonte_loop and "time.sleep" in fonte_loop, (
        "o loop precisa continuar dormindo e so sair via encerrar"
    )

    # checknow segue coletando, com aviso quando esta fora do pregao
    fonte_main = inspect.getsource(main.main)
    trecho_checknow = fonte_main.split('elif comando == "checknow":')[1].split("elif comando")[0]
    assert "checar_agora()" in trecho_checknow, "checknow deixou de coletar"
    assert "AVISO" in trecho_checknow, "checknow nao avisa quando esta fora do pregao"

    # os outros comandos do CLI seguem intactos
    for comando in ["help", "whitelistshow", "pause", "resume", "exit"]:
        assert f'comando == "{comando}"' in fonte_main, f"comando {comando} desapareceu do CLI"

    assert main.INTERVALO_MINUTOS == 60, "o intervalo do loop nao era escopo do P0-5"


# --------------------------------------------------------------------------
# 9. Aceite do ESTADO.md, testado de verdade: rodar o loop as 22h nao coleta
# --------------------------------------------------------------------------
def rodar_um_ciclo_do_loop(dentro_do_pregao):
    """Roda loop_automatico por um ciclo com a janela forcada.

    Substitui `esta_no_horario_de_pregao` e `checar_agora` por dublês, para nao
    tocar nas APIs nem no banco, e encurta o intervalo para o teste terminar em
    menos de um segundo. Devolve (nº de coletas, loop continuou vivo, o que foi
    impresso).
    """
    originais = (
        main.esta_no_horario_de_pregao,
        main.checar_agora,
        main.INTERVALO_MINUTOS,
    )
    coletas = []

    main.esta_no_horario_de_pregao = lambda momento=None: dentro_do_pregao
    main.checar_agora = lambda: coletas.append(1)
    main.INTERVALO_MINUTOS = 1
    main.encerrar = False
    main.pausado = False

    saida = io.StringIO()
    try:
        with contextlib.redirect_stdout(saida):
            thread = threading.Thread(target=main.loop_automatico, daemon=True)
            thread.start()
            time.sleep(0.5)
            vivo = thread.is_alive()
            main.encerrar = True
            thread.join(timeout=5)
        assert not thread.is_alive(), "o loop nao respondeu ao encerrar"
    finally:
        (
            main.esta_no_horario_de_pregao,
            main.checar_agora,
            main.INTERVALO_MINUTOS,
        ) = originais
        main.encerrar = False

    return len(coletas), vivo, saida.getvalue()


def teste_09_loop_fora_do_pregao_nao_coleta_e_nao_morre():
    coletas, vivo, impresso = rodar_um_ciclo_do_loop(dentro_do_pregao=False)

    assert coletas == 0, (
        "o loop chamou a coleta fora do pregao -- e o bug que o P0-5 corrige "
        "(rodar as 22h nao pode inserir linha em cotacoes)"
    )
    assert vivo, (
        "o loop encerrou sozinho fora do pregao; ele tem que continuar rodando "
        "e apenas pular o ciclo"
    )
    assert "ora do horario de pregao" in impresso, (
        "o loop deveria avisar na tela por que pulou o ciclo"
    )


def teste_10_loop_dentro_do_pregao_coleta_normalmente():
    coletas, vivo, _ = rodar_um_ciclo_do_loop(dentro_do_pregao=True)

    assert coletas == 1, f"dentro do pregao esperava 1 coleta, houve {coletas}"
    assert vivo, "o loop deveria seguir vivo depois de coletar"


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

    print("\nTabela de conferencia manual (setembro/2026, horario de Brasilia):\n")
    dias = {7: "seg (FERIADO)", 9: "qua", 11: "sex", 12: "sab", 13: "dom"}
    horas = [3, 9, 10, 14, 17, 18, 21]

    print("dia               " + "".join(f"{h:>7}h" for h in horas))
    for dia, nome in dias.items():
        linha = f"{dia:02d}/09 {nome:<12}"
        for hora in horas:
            marca = "SIM" if esta_no_horario_de_pregao(momento(dia, hora)) else "-"
            linha += f"{marca:>8}"
        print(linha)
    print("\n  SIM = coleta automatica roda | - = pulada (checknow roda de todo jeito)")
