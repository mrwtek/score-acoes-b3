from banco import criar_tabelas, registrar_compra, registrar_venda, listar_posicoes


def mostrar_ajuda():
    print("""
Comandos disponiveis:
  buy TICKER QUANTIDADE PRECO   - registra uma compra (ex: buy PETR4 100 44.30)
  sell TICKER QUANTIDADE        - registra uma venda (ex: sell PETR4 50)
  show                          - lista as posicoes atuais
  help                          - mostra esta lista de comandos
  exit                          - encerra o programa
""")


def mostrar_posicoes():
    posicoes = listar_posicoes()
    if not posicoes:
        print("Nenhuma posicao registrada ainda.")
        return
    print(f"\n{'Ticker':<10}{'Quantidade':<15}{'Preco Medio':<15}{'Atualizado em'}")
    for ticker, quantidade, preco_medio, data_atualizacao in posicoes:
        print(f"{ticker:<10}{quantidade:<15}{preco_medio:<15.2f}{data_atualizacao}")


def main():
    criar_tabelas()
    mostrar_ajuda()

    while True:
        comando = input(">> ").strip().split()

        if not comando:
            continue

        acao = comando[0].lower()

        if acao == "help":
            mostrar_ajuda()
        elif acao == "show":
            mostrar_posicoes()
        elif acao == "buy" and len(comando) == 4:
            ticker = comando[1].upper()
            quantidade = int(comando[2])
            preco = float(comando[3])
            registrar_compra(ticker, quantidade, preco)
        elif acao == "sell" and len(comando) == 3:
            ticker = comando[1].upper()
            quantidade = int(comando[2])
            registrar_venda(ticker, quantidade)
        elif acao == "exit":
            print("Encerrando...")
            break
        else:
            print("Comando invalido. Digite 'help' para ver a lista.")


if __name__ == "__main__":
    main()