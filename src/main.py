import threading
import time
import traceback
from datetime import datetime
from zoneinfo import ZoneInfo

from coletor import coletar_whitelist, buscar_fundamentos, esconder_tokens
from banco import criar_tabelas, salvar_cotacoes, ja_tem_fundamento_hoje, salvar_fundamento
from whitelist import get_whitelist

INTERVALO_MINUTOS = 60

# Janela de coleta automatica (P0-5). O fuso e fixado em Brasilia de proposito:
# se um dia isso rodar em servidor com outro fuso, a janela continua certa.
# ZoneInfo (stdlib) em vez de offset fixo de -3h para acompanhar um eventual
# retorno do horario de verao sem mudar codigo.
FUSO_B3 = ZoneInfo("America/Sao_Paulo")
HORA_ABERTURA = 10
HORA_FECHAMENTO = 18

pausado = False
encerrar = False


def agora_em_brasilia():
    return datetime.now(FUSO_B3)


def esta_no_horario_de_pregao(momento=None):
    """Diz se `momento` cai na janela de coleta: dia util, das 10h as 18h.

    Sem argumento usa a hora corrente de Brasilia. O argumento existe para
    teste (ver test_pregao.py).

    Regras:
      - weekday() < 5 aceita segunda (0) a sexta (4); sabado e domingo ficam fora.
      - HORA_FECHAMENTO e exclusivo: 17:59 coleta, 18:00 em ponto nao. A ultima
        coleta do dia cai as 17:xx.

    LIMITACAO CONHECIDA E ACEITA (nao e bug): feriados nao sao considerados.
    Nao existe calendario de feriados no projeto, entao um feriado que caia em
    dia util -- Natal numa terca, Carnaval, 7 de setembro -- passa por esta
    funcao como True. A coleta vai rodar, as APIs vao devolver o ultimo preco
    fechado e o registro repetido entra na serie. Isso corta ~70% do lixo que o
    P0-5 atacava (madrugadas e fins de semana), nao 100%: sobram os ~9 feriados
    uteis do ano. Fechar esse furo e tarefa futura (calendario da B3 em
    config.py, ou a lib workalendar).
    """
    if momento is None:
        momento = agora_em_brasilia()

    dia_util = momento.weekday() < 5
    dentro_da_janela = HORA_ABERTURA <= momento.hour < HORA_FECHAMENTO
    return dia_util and dentro_da_janela


def checar_agora():
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Iniciando coleta de cotacoes...")
    resultado = coletar_whitelist()
    salvar_cotacoes(resultado)

    for ticker in get_whitelist():
        if ja_tem_fundamento_hoje(ticker):
            print(f"Fundamentos de {ticker} ja coletados hoje, pulando.")
            continue
        dados = buscar_fundamentos(ticker)
        if dados is not None:
            salvar_fundamento(ticker, dados)


def ciclo_de_coleta():
    """Um ciclo: coleta se estiver na janela de pregao, senao avisa e passa.

    Extraido do loop_automatico() no P2-1 para poder ser testado sem thread e
    sem relogio -- e para a guarda ficar num lugar so, em volta dele.
    """
    if esta_no_horario_de_pregao():
        checar_agora()
        return

    momento = agora_em_brasilia()
    print(
        f"\n[{momento.strftime('%d/%m %H:%M')} Brasilia] Fora do horario de "
        f"pregao (dias uteis, {HORA_ABERTURA}h-{HORA_FECHAMENTO}h). "
        "Coleta automatica pulada."
    )


# Depois de quantos ciclos falhados seguidos o aviso muda de tom. Dois ja
# significa que nao foi azar: ou a rede caiu de vez, ou o token morreu, ou tem
# bug. O numero e baixo de proposito -- o ciclo roda de hora em hora, entao
# dois sao duas horas de silencio.
FALHAS_PARA_ALERTAR = 2


def rodar_ciclo_protegido():
    """Roda um ciclo sem deixar excecao nenhuma escapar. Devolve se deu certo.

    ESTA FUNCAO E O P2-1 DO LADO DO main.py. O coletor.py agora trata erro de
    rede, mas tratar rede nao cobre o resto: um bug no banco, um ticker novo
    que quebra uma conversao, um disco cheio. Qualquer um deles subindo pela
    thread a mata, e a thread e `daemon=True` -- ninguem reinicia e ninguem
    percebe, porque o prompt `>>` continua respondendo normalmente. Foi esse o
    modo de falha de 28/10/2026: sete semanas de programa vivo sem coletar.

    Engolir excecao e quase sempre errado, e aqui e a escolha certa pelo mesmo
    motivo que a torna perigosa: o ciclo e repetido. Perder um ciclo custa uma
    hora de serie; perder a thread custou sete semanas. O traceback inteiro vai
    para a tela -- engolido e invisivel nao sao a mesma coisa.

    `except Exception` nao pega KeyboardInterrupt nem SystemExit, que herdam de
    BaseException. Ctrl-C continua encerrando.
    """
    try:
        ciclo_de_coleta()
        return True
    except Exception as erro:
        momento = agora_em_brasilia()
        print(f"\n[{momento.strftime('%d/%m %H:%M:%S')} Brasilia] ERRO no ciclo de "
              f"coleta: {erro.__class__.__name__}: {esconder_tokens(erro)}")
        # o traceback passa pelo filtro de token: foi um traceback que vazou o
        # BRAPI_TOKEN em 28/10, porque a brapi o recebe na query string
        print(esconder_tokens(traceback.format_exc()))
        print("A thread de coleta CONTINUA viva. O proximo ciclo tenta de novo.")
        return False


def loop_automatico():
    falhas_seguidas = 0

    while not encerrar:
        if not pausado:
            if rodar_ciclo_protegido():
                falhas_seguidas = 0
            else:
                falhas_seguidas += 1
                if falhas_seguidas >= FALHAS_PARA_ALERTAR:
                    print(f"ATENCAO: {falhas_seguidas} ciclos seguidos falharam. "
                          f"Isso nao e mais azar de rede -- confira token, banco "
                          f"e o traceback acima antes de confiar na serie.")

        for _ in range(INTERVALO_MINUTOS * 60):
            if encerrar:
                break
            time.sleep(1)


def mostrar_ajuda():
    print("""
Comandos disponiveis:
  help          - mostra esta lista de comandos
  whitelistshow - mostra os tickers monitorados
  pause         - pausa a coleta automatica
  resume        - retoma a coleta automatica
  checknow      - forca uma coleta imediata
  exit          - encerra o programa
""")


def main():
    global pausado, encerrar

    criar_tabelas()

    thread_coleta = threading.Thread(target=loop_automatico, daemon=True)
    thread_coleta.start()

    mostrar_ajuda()

    while True:
        comando = input(">> ").strip().lower()

        if comando == "help":
            mostrar_ajuda()
        elif comando == "whitelistshow":
            print("Tickers monitorados:", ", ".join(get_whitelist()))
        elif comando == "pause":
            pausado = True
            print("Coleta automatica pausada.")
        elif comando == "resume":
            pausado = False
            print("Coleta automatica retomada.")
        elif comando == "checknow":
            # Pedido manual e explicito: roda a qualquer hora, mas avisa quando
            # o dado vai ser extraordinario.
            if not esta_no_horario_de_pregao():
                print(
                    "AVISO: fora do horario de pregao. A coleta vai rodar porque "
                    "foi pedida na mao, mas o preco tende a ser repeticao do "
                    "ultimo fechamento -- dado extraordinario na serie."
                )
            checar_agora()
        elif comando == "exit":
            encerrar = True
            print("Encerrando...")
            break
        else:
            print("Comando nao reconhecido. Digite 'help' para ver a lista.")


if __name__ == "__main__":
    main()
