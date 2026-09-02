import shutil
from datetime import datetime
from pathlib import Path

RAIZ_PROJETO = Path(__file__).resolve().parent.parent
PASTA_DATA = RAIZ_PROJETO / "data"
PASTA_DATA.mkdir(exist_ok=True)

CAMINHO_BANCO = PASTA_DATA / "acoes.db"
PASTA_BACKUPS = PASTA_DATA / "backups"


def fazer_backup():
    if not CAMINHO_BANCO.exists():
        print("Banco ainda nao existe, backup nao necessario.")
        return

    PASTA_BACKUPS.mkdir(exist_ok=True)

    prefixo_hoje = f"acoes_{datetime.now().strftime('%Y%m%d')}_"
    if list(PASTA_BACKUPS.glob(f"{prefixo_hoje}*.db")):
        print("Backup de hoje ja existe, pulando.")
        return

    nome_backup = f"acoes_{datetime.now().strftime('%Y%m%d_%H%M')}.db"
    destino = PASTA_BACKUPS / nome_backup
    shutil.copy2(CAMINHO_BANCO, destino)
    print(f"Backup criado em {destino}")
