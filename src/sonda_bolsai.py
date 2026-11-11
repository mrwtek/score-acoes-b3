import requests
from config import BOLSAI_TOKEN

url = "https://api.usebolsai.com/api/v1/fundamentals/PETR4"
headers = {"X-API-Key": BOLSAI_TOKEN}

resposta = requests.get(url, headers=headers)
dados = resposta.json()

print(dados)