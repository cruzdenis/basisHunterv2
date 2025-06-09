import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime, timezone
from binance.client import Client
from dotenv import load_dotenv
import requests

load_dotenv()
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
client = Client(API_KEY, API_SECRET)

ARQUIVO_OPERACOES = "operacoes_reais.json"

def carregar_operacoes():
    if os.path.exists(ARQUIVO_OPERACOES):
        with open(ARQUIVO_OPERACOES, "r") as f:
            return json.load(f)
    return []

def get_saldos():
    account_info = client.futures_account()
    total = float(account_info['totalWalletBalance'])
    disponivel = float(account_info['availableBalance'])
    return total, disponivel

def get_funding_historico(symbol, inicio, fim):
    url = "https://fapi.binance.com/fapi/v1/fundingRate"
    params = {"symbol": symbol, "startTime": int(inicio.timestamp() * 1000), "endTime": int(fim.timestamp() * 1000), "limit": 1000}
    response = requests.get(url, params=params)
    data = response.json()
    return sum(float(rate['fundingRate']) for rate in data)

st.set_page_config(page_title="Histórico de Operações", layout="wide")

st.title("📊 Histórico Completo de Operações")

operacoes = carregar_operacoes()

abertas = [op for op in operacoes if op['status'] == 'aberta']
fechadas = [op for op in operacoes if op['status'] == 'fechada']

def calcular_pnl(ops, fechada=True):
    total_funding = total_basis = total_taxa = 0

    for op in ops:
        data_abertura = datetime.strptime(op['data_entrada'], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        data_fechamento = datetime.now(timezone.utc) if not fechada else datetime.strptime(op.get('data_saida', datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)

        funding_real = get_funding_historico(op['symbol_perpetuo'], data_abertura, data_fechamento)
        pnl_funding = funding_real * op['volume_usd']

        if fechada:
            pnl_basis = (op['preco_saida_futuro'] - op['preco_entrada_futuro'] +
                         op['preco_entrada_perp'] - op['preco_saida_perp']) * (op['volume_usd'] / op['preco_entrada_perp'])
        else:
            preco_atual_perp = float(client.futures_symbol_ticker(symbol=op["symbol_perpetuo"])["price"])
            preco_atual_futuro = float(requests.get(f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={op['symbol_futuro']}").json()["price"])

            pnl_futuro = (preco_atual_futuro - op['preco_entrada_futuro']) * (op['volume_usd'] / op['preco_entrada_perp'])
            pnl_perp = (op['preco_entrada_perp'] - preco_atual_perp) * (op['volume_usd'] / op['preco_entrada_perp'])

            pnl_basis = pnl_futuro + pnl_perp

        taxa = op.get('taxa_abertura', 0.0)

        total_funding += pnl_funding
        total_basis += pnl_basis
        total_taxa += taxa

    total_geral = total_funding + total_basis - total_taxa
    return total_funding, total_basis, total_taxa, total_geral

# Inicializa variáveis
funding_ab = basis_ab = taxa_ab = geral_ab = 0
funding_fc = basis_fc = taxa_fc = geral_fc = 0

# Operações Abertas
st.subheader("📌 Operações em Andamento")
if abertas:
    df_abertas = pd.DataFrame(abertas)
    st.dataframe(df_abertas, use_container_width=True)
    funding_ab, basis_ab, taxa_ab, geral_ab = calcular_pnl(abertas, fechada=False)

    cols_abertas = st.columns(4)
    cols_abertas[0].metric("Subtotal PnL Funding", f"${funding_ab:.2f}")
    cols_abertas[1].metric("Subtotal PnL Basis", f"${basis_ab:.2f}")
    cols_abertas[2].metric("Subtotal Taxas", f"-${taxa_ab:.2f}")
    cols_abertas[3].metric("Subtotal Geral", f"${geral_ab:.2f}")
else:
    st.info("Nenhuma operação aberta.")

st.divider()

# Operações Fechadas
st.subheader("📁 Operações Finalizadas")
if fechadas:
    df_fechadas = pd.DataFrame(fechadas)
    st.dataframe(df_fechadas, use_container_width=True)
    funding_fc, basis_fc, taxa_fc, geral_fc = calcular_pnl(fechadas, fechada=True)
    st.metric("Subtotal Operações Fechadas", f"${geral_fc:.2f}")
else:
    st.info("Nenhuma operação fechada.")

st.divider()

# Total Geral
st.subheader("💼 Resumo Geral")
total_funding = funding_ab + funding_fc
total_basis = basis_ab + basis_fc
total_taxa = taxa_ab + taxa_fc
total_geral = geral_ab + geral_fc

cols = st.columns(4)
cols[0].metric("Total PnL Funding", f"${total_funding:.2f}")
cols[1].metric("Total PnL Basis", f"${total_basis:.2f}")
cols[2].metric("Total Taxas", f"-${total_taxa:.2f}")
cols[3].metric("Total Geral", f"${total_geral:.2f}")

# Saldo Corretora
st.subheader("🏦 Saldo na Corretora")
total_saldo, saldo_disponivel = get_saldos()
st.metric("Saldo Total da Conta", f"${total_saldo:.2f}")
st.metric("Saldo Disponível", f"${saldo_disponivel:.2f}")
