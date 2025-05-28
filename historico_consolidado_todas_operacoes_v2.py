import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime

st.set_page_config(page_title="📋 Histórico Consolidado", layout="wide")

ARQUIVO_OPERACOES = "operacoes_reais.json"

# Carregar operações
def carregar_operacoes():
    if os.path.exists(ARQUIVO_OPERACOES):
        with open(ARQUIVO_OPERACOES, "r") as f:
            return json.load(f)
    return []

operacoes = carregar_operacoes()

# Gerar histórico consolidado
historico = []
for op in operacoes:
    preco_entrada_perp = op["preco_entrada_perp"]
    preco_entrada_fut = op["preco_entrada_futuro"]
    preco_saida_perp = op.get("preco_saida_perp", preco_entrada_perp)
    preco_saida_fut = op.get("preco_saida_futuro", preco_entrada_fut)
    dias = max((datetime.now() - datetime.strptime(op["data_entrada"], "%Y-%m-%d %H:%M:%S")).days, 1)
    funding = op.get("funding_rate_entrada_diario", 0) * dias
    pnl_funding = op["volume_usd"] * funding
    pnl_basis = ((preco_saida_fut - preco_entrada_fut) + (preco_entrada_perp - preco_saida_perp)) * (op["volume_usd"] / preco_entrada_perp)
    taxas = op.get("taxa_abertura", 0)
    pnl_total = pnl_funding + pnl_basis - taxas

    historico.append({
        "Data Entrada": op["data_entrada"],
        "Ativo": op["symbol_perpetuo"],
        "Volume (USD)": op["volume_usd"],
        "Funding PNL": pnl_funding,
        "Basis PNL": pnl_basis,
        "Taxas": taxas,
        "PnL Total": pnl_total,
        "Status": op["status"]
    })

df = pd.DataFrame(historico)

# Exibir tabela histórica
st.title("📋 Histórico Consolidado de Operações")
st.dataframe(df, use_container_width=True)

# Exibir totais por status
st.divider()
st.subheader("📈 Totais Consolidados")

resumo = df.groupby("Status").agg({
    "Volume (USD)": "sum",
    "Funding PNL": "sum",
    "Basis PNL": "sum",
    "Taxas": "sum",
    "PnL Total": "sum"
}).reset_index()

col1, col2 = st.columns(2)

for _, row in resumo.iterrows():
    col = col1 if row["Status"] == "aberta" else col2
    col.metric(f"Operações {row['Status'].capitalize()}", "")
    col.metric("Volume Total (USD)", f"${row['Volume (USD)']:,.2f}")
    col.metric("Total Funding PNL", f"${row['Funding PNL']:,.2f}")
    col.metric("Total Basis PNL", f"${row['Basis PNL']:,.2f}")
    col.metric("Total Taxas", f"-${row['Taxas']:,.2f}")
    col.metric("Total Geral", f"${row['PnL Total']:,.2f}")