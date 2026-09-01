from banco import listar_tickers_em_carteira

WHITELIST_BASE = [
    "PETR4",
    "VALE3",
    "ITUB4",
    "BBDC4",
    "WEGE3",
]


def get_whitelist():
    tickers_carteira = listar_tickers_em_carteira()
    combinado = set(WHITELIST_BASE) | set(tickers_carteira)
    return sorted(combinado)