import streamlit as st
import pandas as pd
import json

st.set_page_config(page_title="Histórico de Saldo", layout="wide")

st.title("📈 Histórico do Saldo Total da Corretora")

ARQUIVO_HISTORICO = "saldo_historico.json"

def carregar_historico():
    try:
        with open(ARQUIVO_HISTORICO, "r") as f:
            historico = json.load(f)
            return pd.DataFrame(historico)
    except:
        return pd.DataFrame(columns=["timestamp", "total"])

df = carregar_historico()

if not df.empty:
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    st.line_chart(df['total'])
else:
    st.info("Nenhum dado histórico disponível.")
