import streamlit as st
import requests
import json
import os
from datetime import datetime, timezone
from binance.client import Client
from dotenv import load_dotenv

st.set_page_config(page_title="🔄 Arbitragem com Rolagem de Futuro", layout="wide")

ARQUIVO_OPERACOES = "operacoes_reais.json"

load_dotenv()
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
client = Client(API_KEY, API_SECRET)

def carregar_operacoes():
    if os.path.exists(ARQUIVO_OPERACOES):
        with open(ARQUIVO_OPERACOES, "r") as f:
            return json.load(f)
    return []

def salvar_operacoes(ops):
    with open(ARQUIVO_OPERACOES, "w") as f:
        json.dump(ops, f, indent=2)

def calcular_qty(volume_usd, preco, symbol):
    info = client.futures_exchange_info()
    step = 0.001
    for s in info['symbols']:
        if s['symbol'] == symbol:
            for f in s['filters']:
                if f['filterType'] == 'LOT_SIZE':
                    step = float(f['stepSize'])
    qty = volume_usd / preco
    qty = qty - (qty % step)
    return round(qty, 8)

def get_next_quarter_symbol(symbol_prefix):
    info = requests.get("https://fapi.binance.com/fapi/v1/exchangeInfo").json()
    futures = sorted(
        [s["symbol"] for s in info["symbols"] 
         if s["symbol"].startswith(symbol_prefix) and s["contractType"] == "NEXT_QUARTER"]
    )
    return futures[0] if futures else None

st.title("🔄 Arbitragem com Rolagem de Contrato Futuro")

operacoes = carregar_operacoes()
abertas = [op for op in operacoes if op["status"] == "aberta"]

if abertas:
    for idx, ordem in enumerate(abertas):
        with st.container():
            st.markdown(f"### 📘 Ordem #{idx+1} — {ordem['symbol_perpetuo']}")
            col1, col2 = st.columns([2, 1])
            with col1:
                st.markdown(f"""
**Entrada:** `{ordem['data_entrada']}`  
**Volume:** `${ordem['volume_usd']}`  
**Contrato Futuro Atual:** `{ordem['symbol_futuro']}`  
**Preço Entrada Futuro:** `${ordem['preco_entrada_futuro']}`
""")

            if st.button(f"🔄 Rolar Futuro #{idx+1}", key=f"rolar_{idx}"):
                try:
                    novo_symbol_fut = get_next_quarter_symbol(ordem["symbol_perpetuo"])

                    if not novo_symbol_fut:
                        st.error("Nenhum contrato futuro seguinte encontrado!")
                        st.stop()

                    preco_atual_futuro = float(requests.get(f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={ordem['symbol_futuro']}").json()["price"])
                    preco_novo_futuro = float(requests.get(f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={novo_symbol_fut}").json()["price"])

                    qty_fut_atual = calcular_qty(ordem["volume_usd"], ordem["preco_entrada_futuro"], ordem["symbol_futuro"])
                    qty_fut_novo = calcular_qty(ordem["volume_usd"], preco_novo_futuro, novo_symbol_fut)

                    client.futures_create_order(symbol=ordem["symbol_futuro"], side="SELL", type="MARKET", quantity=qty_fut_atual)
                    client.futures_create_order(symbol=novo_symbol_fut, side="BUY", type="MARKET", quantity=qty_fut_novo)

                    ordem["symbol_futuro_anterior"] = ordem["symbol_futuro"]
                    ordem["preco_saida_futuro"] = preco_atual_futuro
                    ordem["symbol_futuro"] = novo_symbol_fut
                    ordem["preco_entrada_futuro"] = preco_novo_futuro
                    ordem["data_rolagem"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                    ordem["taxa_rolagem"] = round(ordem["volume_usd"] * 2 * 0.0004, 2)

                    salvar_operacoes(operacoes)

                    st.success(f"🔄 Rolagem realizada com sucesso para contrato {novo_symbol_fut}!")

                except Exception as e:
                    st.error(f"Erro ao realizar rolagem: {e}")
else:
    st.info("Nenhuma operação aberta disponível para rolagem.")
