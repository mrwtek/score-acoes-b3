"""
Preenche a tabela `indices` com Ibovespa (brapi) e Selic/CDI (Banco Central).

Como o backfill_historico.py, NAO e script de uso unico: roda junto com ele,
uma vez por mes. O Ibovespa herda o teto de 3 meses do plano free da brapi;
Selic e CDI nao tem teto nenhum, o SGS e aberto.

Por padrao as taxas sao buscadas desde o primeiro dia que existe em
`cotacoes_historicas`, para o benchmark cobrir exatamente o periodo que da
para comparar. Puxar Selic de 2010 nao ajudaria em nada sem preco de acao do
mesmo dia do outro lado.

Uso:
    python backfill_indices.py              # desde o inicio da serie de precos
    python backfill_indices.py 2026-01-01   # desde a data informada
"""
import sys
import time
from datetime import datetime, timedelta

from banco import (
    FUSO_B3,
    contar_cotacoes_historicas,
    contar_indices,
    criar_tabelas,
    salvar_indices,
)
from indices import (
    CODIGO_IBOV,
    SERIES_BCB,
    TIPOS,
    buscar_ibov,
    buscar_serie_bcb,
)

# Mesma pausa do backfill_historico.py, pelo limite de 20 req/min da brapi.
# O BCB nao documenta limite, mas nao custa ser educado com ele tambem.
PAUSA_ENTRE_CHAMADAS = 3.5

# Usado so quando cotacoes_historicas ainda esta vazia.
DIAS_PADRAO_SEM_SERIE = 365


def data_inicial_padrao():
    """Primeiro dia da serie de precos, ou um ano atras se ela nao existir."""
    linhas = contar_cotacoes_historicas()
    if linhas:
        return min(primeira for _, _, primeira, _ in linhas)

    inicio = datetime.now(FUSO_B3) - timedelta(days=DIAS_PADRAO_SEM_SERIE)
    return inicio.strftime("%Y-%m-%d")


def coletar_ibov():
    pontos = buscar_ibov()
    if pontos is None:
        print("IBOV: falhou, nada gravado.")
        return False

    resultado = salvar_indices(CODIGO_IBOV, TIPOS[CODIGO_IBOV], pontos)
    print(f"IBOV: {len(pontos)} pregoes recebidos, {resultado.novas} novos no banco"
          f"{_sufixo(resultado)}")
    return True


def coletar_taxas(data_inicial):
    falhas = []
    for nome in sorted(SERIES_BCB):
        time.sleep(PAUSA_ENTRE_CHAMADAS)

        pontos = buscar_serie_bcb(nome, data_inicial)
        if pontos is None:
            falhas.append(nome)
            continue

        resultado = salvar_indices(nome, TIPOS[nome], pontos)
        print(f"{nome}: {len(pontos)} dias recebidos, {resultado.novas} novos no banco"
              f"{_sufixo(resultado)}")
    return falhas


def _sufixo(resultado):
    partes = []
    if resultado.descartadas:
        partes.append(f"{resultado.descartadas} descartado(s)")
    if resultado.em_andamento:
        partes.append(f"{resultado.em_andamento} do dia em andamento, ignorado(s)")
    return f" ({', '.join(partes)})" if partes else ""


def imprimir_resumo():
    linhas = contar_indices()
    if not linhas:
        print("\nTabela indices ainda vazia.")
        return

    print(f"\n{'codigo':8s} {'tipo':13s} {'linhas':>7s}  periodo no banco")
    for codigo, tipo, quantidade, primeira, ultima in linhas:
        print(f"{codigo:8s} {tipo:13s} {quantidade:7d}  {primeira} -> {ultima}")

    # A defasagem entre as fontes nao e bug, mas atrapalha quem comparar
    # rendimento sem perceber: o BCB publica a taxa com alguns dias de atraso.
    ultimas = {codigo: ultima for codigo, _, _, _, ultima in linhas}
    if len(set(ultimas.values())) > 1:
        print("\nAtencao: as series terminam em datas diferentes "
              f"({', '.join(f'{c} em {d}' for c, d in sorted(ultimas.items()))}).")
        print("Para comparar rendimento acumulado, corte todas na data mais antiga.")


def main():
    criar_tabelas()

    argumentos = sys.argv[1:]
    data_inicial = argumentos[0] if argumentos else data_inicial_padrao()

    try:
        datetime.strptime(data_inicial, "%Y-%m-%d")
    except ValueError:
        print(f"Data invalida: {data_inicial!r}. Use o formato AAAA-MM-DD.")
        return

    print(f"Ibovespa: ultimos 3 meses (teto do plano free da brapi).")
    print(f"Selic e CDI: desde {data_inicial}.\n")

    ok_ibov = coletar_ibov()
    falhas = coletar_taxas(data_inicial)

    if not ok_ibov:
        falhas.insert(0, CODIGO_IBOV)
    if falhas:
        print(f"\nFalharam (nada gravado): {', '.join(falhas)}")

    imprimir_resumo()


if __name__ == "__main__":
    main()
