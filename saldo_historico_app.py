import time
import json
from datetime import datetime, timezone
from binance.client import Client
from dotenv import load_dotenv
import os

load_dotenv()
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
client = Client(API_KEY, API_SECRET)

ARQUIVO_HISTORICO = "saldo_historico.json"

def salvar_saldo():
    while True:
        account_info = client.futures_account()
        total = float(account_info['totalWalletBalance'])
        timestamp = datetime.now(timezone.utc).isoformat()

        registro = {"timestamp": timestamp, "total": total}

        if os.path.exists(ARQUIVO_HISTORICO):
            with open(ARQUIVO_HISTORICO, "r") as f:
                historico = json.load(f)
        else:
            historico = []

        historico.append(registro)

        with open(ARQUIVO_HISTORICO, "w") as f:
            json.dump(historico, f, indent=2)

        time.sleep(3600)  # aguarda 1 hora antes de próxima consulta

if __name__ == "__main__":
    salvar_saldo()
