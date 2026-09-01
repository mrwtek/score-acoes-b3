import threading
import time
from datetime import datetime

from coletor import coletar_whitelist, buscar_fundamentos
from banco import criar_tabelas, salvar_cotacoes, ja_tem_fundamento_hoje, salvar_fundamento
from whitelist import get_whitelist

INTERVALO_MINUTOS = 60

pausado = False
encerrar = False


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
            checar_agora()
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
            checar_agora()
        elif comando == "exit":
            encerrar = True
            print("Encerrando...")
            break
        else:
            print("Comando nao reconhecido. Digite 'help' para ver a lista.")


if __name__ == "__main__":
    main()