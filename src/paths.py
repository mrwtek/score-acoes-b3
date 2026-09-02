from pathlib import Path

RAIZ_PROJETO = Path(__file__).resolve().parent.parent
PASTA_DATA = RAIZ_PROJETO / "data"
PASTA_DATA.mkdir(exist_ok=True)

CAMINHO_BANCO = PASTA_DATA / "acoes.db"
