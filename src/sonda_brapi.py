import requests
from config import BRAPI_TOKEN

url = "https://brapi.dev/api/quote/PETR4"
params = {"token": BRAPI_TOKEN}

resposta = requests.get(url, params=params)
dados = resposta.json()

print(dados)