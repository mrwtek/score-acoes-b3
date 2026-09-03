import os
from dotenv import load_dotenv

from paths import RAIZ_PROJETO

CAMINHO_ENV = RAIZ_PROJETO / ".env"
load_dotenv(CAMINHO_ENV)

BRAPI_TOKEN = os.getenv("BRAPI_TOKEN")
BOLSAI_TOKEN = os.getenv("BOLSAI_TOKEN")

if not BRAPI_TOKEN or not BOLSAI_TOKEN:
    faltando = []
    if not BRAPI_TOKEN:
        faltando.append("BRAPI_TOKEN")
    if not BOLSAI_TOKEN:
        faltando.append("BOLSAI_TOKEN")
    raise RuntimeError(
        f"Token(s) ausente(s): {', '.join(faltando)}. "
        f"Verifique se o arquivo .env existe em {CAMINHO_ENV} e contem essas variaveis."
    )