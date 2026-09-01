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