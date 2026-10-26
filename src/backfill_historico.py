"""
Preenche `cotacoes_historicas` com a serie diaria da brapi para cada ticker da
whitelist.

NAO e script de uso unico, ao contrario do backfill_transacoes.py. O plano free
da brapi so entrega os ultimos 3 meses, e essa janela desliza todo dia: rodando
este script periodicamente (uma vez por mes ja basta), a serie no banco vai
crescendo alem dos 3 meses e qualquer buraco de coleta se fecha sozinho, desde
que o buraco ainda esteja dentro da janela.

O que esta antes da janela e perda permanente neste plano. Em 26/10/2026 o
alcance comecava em 28/07/2026.

Uso:
    python backfill_historico.py              # whitelist inteira
    python backfill_historico.py PETR4 VALE3  # so esses tickers
"""
import sys
import time

from banco import (
    contar_cotacoes_historicas,
    criar_tabelas,
    normalizar_ticker,
    salvar_cotacoes_historicas,
)
from coletor import INTERVALO_HISTORICO_PADRAO, buscar_historico
from whitelist import get_whitelist

# A brapi responde 20 requisicoes por minuto com concorrencia 1 (headers
# ratelimit-limit e x-brapi-concurrency-limit). 3s seria o limite exato;
# 3.5s deixa folga para o caso de o relogio do servidor contar diferente.
PAUSA_ENTRE_CHAMADAS = 3.5


def backfill(tickers, intervalo=INTERVALO_HISTORICO_PADRAO):
    total_novas = 0
    falhas = []

    for posicao, ticker in enumerate(tickers):
        if posicao > 0:
            time.sleep(PAUSA_ENTRE_CHAMADAS)

        pontos = buscar_historico(ticker, intervalo)
        if pontos is None:
            falhas.append(ticker)
            continue

        if not pontos:
            print(f"{ticker}: a API respondeu sem nenhum pregao no periodo.")
            continue

        novas, descartados = salvar_cotacoes_historicas(ticker, pontos)
        total_novas += novas

        aviso_descarte = f", {descartados} ponto(s) descartado(s) sem data ou fechamento" if descartados else ""
        print(f"{ticker}: {len(pontos)} pregoes recebidos, {novas} novos no banco{aviso_descarte}")

    return total_novas, falhas


def imprimir_resumo():
    linhas = contar_cotacoes_historicas()
    if not linhas:
        print("\nTabela cotacoes_historicas ainda vazia.")
        return

    print(f"\n{'ticker':10s} {'linhas':>7s}  periodo no banco")
    for ticker, quantidade, primeira, ultima in linhas:
        print(f"{ticker:10s} {quantidade:7d}  {primeira} -> {ultima}")


def main():
    criar_tabelas()

    argumentos = sys.argv[1:]
    tickers = [normalizar_ticker(t) for t in argumentos] if argumentos else get_whitelist()

    print(f"Buscando historico ({INTERVALO_HISTORICO_PADRAO}) de {len(tickers)} ticker(s).")
    print(f"Com a pausa de {PAUSA_ENTRE_CHAMADAS}s entre chamadas, isso leva "
          f"cerca de {int(len(tickers) * PAUSA_ENTRE_CHAMADAS)}s.\n")

    total_novas, falhas = backfill(tickers)

    print(f"\n{total_novas} linha(s) nova(s) gravada(s).")
    if falhas:
        print(f"Falharam (nada gravado): {', '.join(falhas)}")

    imprimir_resumo()


if __name__ == "__main__":
    main()
