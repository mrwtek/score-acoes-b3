import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from coletor import coletar_whitelist, buscar_fundamentos
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


def loop_automatico():
    while not encerrar:
        if not pausado:
            if esta_no_horario_de_pregao():
                checar_agora()
            else:
                momento = agora_em_brasilia()
                print(
                    f"\n[{momento.strftime('%d/%m %H:%M')} Brasilia] Fora do horario de "
                    f"pregao (dias uteis, {HORA_ABERTURA}h-{HORA_FECHAMENTO}h). "
                    "Coleta automatica pulada."
                )
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
