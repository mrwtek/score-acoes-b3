"""
Diario de teses: registra o que voce achou e confere depois contra o mercado.

Para que serve: separar "eu estava certo" de "deu certo". Uma compra pode
subir por um motivo que nao tem nada a ver com a sua razao para comprar, e aos
tres meses voce lembra do resultado, nunca do raciocinio. Com a tese escrita
antes, da para saber qual das duas coisas aconteceu.

Tres regras que o formato impoe:

1. PRAZO OBRIGATORIO. Tese sem prazo nao pode falhar -- sempre da para dizer
   "ainda vai voltar". So o que pode falhar ensina.
2. CRITERIO ESCRITO ANTES. O que, exatamente, faz esta tese estar certa? Sem
   isso, no vencimento voce vai escolher o criterio que faz voce ter acertado.
3. BENCHMARK, NAO VALOR ABSOLUTO. Subir 8% quando o IBOV subiu 20% nao e
   acerto, e perder de forma mais lenta. A conferencia e sempre contra o IBOV
   e contra o CDI.

Uso:
    python teses.py            # painel das teses abertas
"""
from datetime import datetime, timedelta

from banco import hoje_b3, listar_teses, salvar_tese
from indices import (
    CODIGO_IBOV,
    acumular_taxa_diaria,
    carregar_serie_indice,
    carregar_serie_ticker,
    variacao_percentual,
)


def abrir_tese(ticker, premissa, criterio, horizonte_dias, preco_abertura=None,
               score_abertura=None, data_abertura=None):
    """Registra uma tese. O preco vem da serie historica se nao for informado."""
    data_abertura = data_abertura or hoje_b3()

    if preco_abertura is None:
        serie = carregar_serie_ticker(ticker, fim=data_abertura)
        if not serie:
            raise ValueError(
                f"sem preco para {ticker} ate {data_abertura}. "
                f"Rode backfill_historico.py antes."
            )
        preco_abertura = serie[-1][1]

    return salvar_tese(ticker, data_abertura, preco_abertura, premissa,
                       criterio, horizonte_dias, score_abertura)


def _ultima_data_comum(ticker, inicio):
    """Ultima data em que ticker, IBOV e CDI existem todos. None se faltar algo.

    As tres series terminam em dias diferentes -- o BCB publica a taxa com
    alguns dias de atraso. Comparar rendimento sobre janelas diferentes nao
    compara nada, entao a conferencia corta todas na data mais curta.
    """
    pontas = []
    for serie in (carregar_serie_ticker(ticker, inicio),
                  carregar_serie_indice(CODIGO_IBOV, inicio),
                  carregar_serie_indice("CDI", inicio)):
        if not serie:
            return None
        pontas.append(serie[-1][0])
    return min(pontas)


def conferir(tese):
    """Devolve como a tese esta indo, ou None se ainda nao der para medir."""
    inicio = tese["data_abertura"]
    fim = _ultima_data_comum(tese["ticker"], inicio)
    if fim is None or fim <= inicio:
        return None

    serie_papel = carregar_serie_ticker(tese["ticker"], inicio, fim)
    retorno = variacao_percentual(serie_papel)
    ibov = variacao_percentual(carregar_serie_indice(CODIGO_IBOV, inicio, fim))
    cdi = acumular_taxa_diaria(carregar_serie_indice("CDI", inicio, fim))

    if retorno is None or ibov is None:
        return None

    abertura = datetime.strptime(inicio, "%Y-%m-%d")
    vencimento = abertura + timedelta(days=tese["horizonte_dias"])
    hoje = datetime.strptime(hoje_b3(), "%Y-%m-%d")

    return {
        "ate": fim,
        "preco_atual": serie_papel[-1][1],
        "retorno": retorno,
        "ibov": ibov,
        "cdi": cdi,
        "vs_ibov": retorno - ibov,
        "vs_cdi": retorno - cdi,
        "dias_corridos": (hoje - abertura).days,
        "dias_restantes": (vencimento - hoje).days,
        "vencimento": vencimento.strftime("%Y-%m-%d"),
        "vencida": hoje >= vencimento,
    }


def imprimir_painel(apenas_abertas=True):
    teses = listar_teses(apenas_abertas=apenas_abertas)
    if not teses:
        print("Nenhuma tese registrada.")
        return

    print(f"Painel de teses -- hoje e {hoje_b3()}\n")

    for tese in teses:
        print(f"[{tese['id']}] {tese['ticker']}  aberta em {tese['data_abertura']} "
              f"a R$ {tese['preco_abertura']:.2f}  ({tese['status']})")
        print(f"     premissa: {tese['premissa']}")
        print(f"     criterio: {tese['criterio']}")

        resultado = conferir(tese)
        if resultado is None:
            print("     ainda sem pregao novo para medir.\n")
            continue

        marca = "VENCIDA" if resultado["vencida"] else f"faltam {resultado['dias_restantes']}d"
        print(f"     ate {resultado['ate']}: R$ {resultado['preco_atual']:.2f}  "
              f"{resultado['retorno']:+.2f}%")
        print(f"     IBOV {resultado['ibov']:+.2f}%  |  CDI {resultado['cdi']:+.2f}%")
        print(f"     vs IBOV {resultado['vs_ibov']:+.2f} pp  |  "
              f"vs CDI {resultado['vs_cdi']:+.2f} pp")
        print(f"     vencimento {resultado['vencimento']} ({marca})\n")

    print("Rendimento acima do CDI nao prova que a tese estava certa -- so que")
    print("rendeu. Acertar pelo motivo errado conta como erro no diario.")


if __name__ == "__main__":
    imprimir_painel()
