import requests
from config import BRAPI_TOKEN, BOLSAI_TOKEN
from whitelist import get_whitelist


def buscar_dados_acao(ticker):
    url = f"https://brapi.dev/api/quote/{ticker}"
    params = {"token": BRAPI_TOKEN}
    resposta = requests.get(url, params=params)
    dados = resposta.json()

    if "results" not in dados:
        print(f"ERRO ao buscar {ticker}: {dados}")
        return None

    return dados["results"][0]


def coletar_whitelist():
    dados_coletados = []
    for ticker in get_whitelist():
        dados = buscar_dados_acao(ticker)
        if dados is not None:
            dados_coletados.append(dados)
            print(f"Coletado: {ticker}")
    return dados_coletados

# A brapi no plano free so aceita os ranges 1d, 5d, 1mo e 3mo - 6mo para cima
# exige o plano Pro. 3mo rende 63 pregoes por ticker. Como a janela desliza, o
# backfill rodado periodicamente vai estendendo a serie no banco; e por isso que
# ele nao e script de uso unico.
INTERVALO_HISTORICO_PADRAO = "3mo"

# Nova funcao, entao ja nasce com timeout. As duas funcoes acima continuam sem,
# junto com retry e checagem de status - isso e o P2-1 e vale para o coletor
# inteiro de uma vez, nao de passagem.
TIMEOUT_SEGUNDOS = 30


def buscar_historico(ticker, intervalo=INTERVALO_HISTORICO_PADRAO):
    """Devolve a lista de pregoes diarios da brapi, ou None se a chamada falhar.

    Cada item vem no formato {date, open, high, low, close, volume,
    adjustedClose}, com `date` em epoch de segundos.
    """
    url = f"https://brapi.dev/api/quote/{ticker}"
    params = {"token": BRAPI_TOKEN, "range": intervalo, "interval": "1d"}

    try:
        resposta = requests.get(url, params=params, timeout=TIMEOUT_SEGUNDOS)
    except requests.RequestException as erro:
        print(f"ERRO de rede ao buscar historico de {ticker}: {erro}")
        return None

    if resposta.status_code != 200:
        # o 400 de range indisponivel no plano cai aqui com a mensagem da
        # propria brapi, que e explicita sobre qual range faltou
        print(f"ERRO HTTP {resposta.status_code} no historico de {ticker}: {resposta.text[:200]}")
        return None

    dados = resposta.json()
    if "results" not in dados or not dados["results"]:
        print(f"ERRO ao buscar historico de {ticker}: {dados}")
        return None

    return dados["results"][0].get("historicalDataPrice") or []


def buscar_fundamentos(ticker):
    url = f"https://api.usebolsai.com/api/v1/fundamentals/{ticker}"
    headers = {"X-API-Key": BOLSAI_TOKEN}
    resposta = requests.get(url, headers=headers)
    dados = resposta.json()

    if "pl" not in dados:
        print(f"ERRO ao buscar fundamentos de {ticker}: {dados}")
        return None

    return dados

if __name__ == "__main__":
    resultado = coletar_whitelist()
    print(f"\nTotal de ações coletadas: {len(resultado)}")