import streamlit as st
import requests
import os
import json
import time
from datetime import datetime, timezone
from binance.client import Client
from dotenv import load_dotenv

# Configuracao da pagina
st.set_page_config(page_title="Análise BTC e ETH", layout="wide")

# Carregar variaveis de ambiente
load_dotenv()
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
client = Client(API_KEY, API_SECRET)

ARQUIVO_OPERACOES = "operacoes_reais.json"

# Funcoes auxiliares

def get_funding_history(symbol, start_time):
    url = "https://fapi.binance.com/fapi/v1/fundingRate"
    params = {"symbol": symbol, "limit": 1000, "startTime": start_time}
    data = requests.get(url, params=params).json()
    return [float(e["fundingRate"]) for e in data]

def calcular_apr(funding_rates):
    if not funding_rates:
        return 0.0
    media = sum(funding_rates) / len(funding_rates)
    return ((1 + media) ** (3 * 365)) - 1  # 3 períodos por dia

# (todas as funções auxiliares anteriores mantidas aqui)
def salvar_operacoes(ops):
    with open(ARQUIVO_OPERACOES, "w") as f:
        json.dump(ops, f, indent=2)

def carregar_operacoes():
    if os.path.exists(ARQUIVO_OPERACOES):
        with open(ARQUIVO_OPERACOES, "r") as f:
            return json.load(f)
    return []

def get_symbol_info(symbol_prefix):
    info = requests.get("https://fapi.binance.com/fapi/v1/exchangeInfo").json()
    for s in info["symbols"]:
        if s["symbol"].startswith(symbol_prefix) and s["contractType"] == "CURRENT_QUARTER":
            return s["symbol"]
    return None

def get_prices(symbol_spot, symbol_future):
    perp_price = float(client.futures_symbol_ticker(symbol=symbol_spot)["price"])
    fut_price = float(requests.get(f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={symbol_future}").json()["price"])
    return perp_price, fut_price

def get_recent_funding(symbol, limit=3):
    url = "https://fapi.binance.com/fapi/v1/fundingRate"
    params = {"symbol": symbol, "limit": limit}
    data = requests.get(url, params=params).json()
    return sum([float(i["fundingRate"]) for i in data]) if data else 0.0

def estimate_days_to_expiry(symbol_future):
    try:
        date_part = symbol_future.split("_")[-1]
        expiry = datetime.strptime("20" + date_part, "%Y%m%d").replace(tzinfo=timezone.utc)
        return max((expiry - datetime.now(timezone.utc)).days, 1)
    except:
        return 90

def calcular_qty(volume_usd, preco, symbol):
    qty = volume_usd / preco
    info = client.futures_exchange_info()
    step = 0.001
    for s in info['symbols']:
        if s['symbol'] == symbol:
            for f in s['filters']:
                if f['filterType'] == 'LOT_SIZE':
                    step = float(f['stepSize'])
    qty = qty - (qty % step)
    return round(qty, 8)

def executar_ordem(symbol_spot, symbol_future, volume):
    preco_perp, preco_fut = get_prices(symbol_spot, symbol_future)
    qty_perp = calcular_qty(volume, preco_perp, symbol_spot)
    qty_fut = calcular_qty(volume, preco_fut, symbol_future)

    client.futures_create_order(symbol=symbol_spot, side="SELL", type="MARKET", quantity=qty_perp)
    client.futures_create_order(symbol=symbol_future, side="BUY", type="MARKET", quantity=qty_fut)

    nova_ordem = {
        "data_entrada": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "symbol_perpetuo": symbol_spot,
        "symbol_futuro": symbol_future,
        "preco_entrada_perp": preco_perp,
        "preco_entrada_futuro": preco_fut,
        "volume_usd": volume,
        "funding_rate_entrada_diario": get_recent_funding(symbol_spot),
        "status": "aberta"
    }
    operacoes = carregar_operacoes()
    operacoes.append(nova_ordem)
    salvar_operacoes(operacoes)

# Função para desenhar o quadro de um ativo
def mostrar_analise_ativo(nome, symbol_spot, symbol_prefix, volume, modo_auto):
    symbol_future = get_symbol_info(symbol_prefix)
    if not symbol_future:
        st.error(f"Não encontrado contrato futuro para {nome}")
        return

    preco_perp, preco_fut = get_prices(symbol_spot, symbol_future)
    dias_venc = estimate_days_to_expiry(symbol_future)
    basis_pct = (preco_fut - preco_perp) / preco_perp
    basis_dia = basis_pct / dias_venc
    funding_diario = get_recent_funding(symbol_spot)
    relacao_fb = funding_diario / basis_dia if basis_dia else 0
    gatilho = (funding_diario > 0.0003) or (funding_diario > 1.5 * basis_dia)

    st.subheader(f"{nome}")
    st.markdown(f"""
    - **Preço Perpétuo ({symbol_spot}):** `${preco_perp:,.2f}`  
    - **Preço Futuro Trimestral:** `${preco_fut:,.2f}`  
    - **Dias até o vencimento:** `{dias_venc}`  
    - **Basis Total:** `{basis_pct:.4%}` → Diário `{basis_dia:.4%}`  
    - **Funding Rate Diário (3 períodos):** `{funding_diario:.4%}`  
    - **Relação Funding/Basis:** `{relacao_fb:.2f}`  
    - **{'🟢 Gatilho de Entrada Ativado' if gatilho else '🔴 Sem Gatilho'}**
    """)

    if st.button(f"🚀 Executar Arbitragem Manual - {nome}"):
        executar_ordem(symbol_spot, symbol_future, volume)
        st.success("✅ Ordem manual executada!")

# Interface
st.title("🔹 Análise Simultânea BTC e ETH com Execução")
volume = st.number_input("Volume (USD) por operação", min_value=50.0, value=100.0, step=50.0)
modo_auto = st.toggle("🚀 Modo Automático de Trade")
filtro_ativo = st.selectbox("Filtrar ativo:", ["Todos", "BTC", "ETH"])
col_btc, col_eth = st.columns(2)

if filtro_ativo in ["Todos", "BTC"]:
    with col_btc:
        mostrar_analise_ativo("Bitcoin (BTC)", "BTCUSDT", "BTCUSDT", volume, modo_auto)

if filtro_ativo in ["Todos", "ETH"]:
    with col_eth:
        mostrar_analise_ativo("Ethereum (ETH)", "ETHUSDT", "ETHUSDT", volume, modo_auto)

# Autorefresh com contador
if modo_auto:
    countdown_placeholder = st.empty()
    for i in range(600, 0, -1):
        mins, secs = divmod(i, 60)
        countdown_placeholder.info(f"🔄 Próxima atualização automática em {mins}m {secs}s")
        time.sleep(1)

    st.experimental_rerun()
else:
    st.info("⏸️ Atualização automática desativada.")


# ========== OPERACOES ABERTAS ==========
st.divider()
st.subheader("📂 Operações Abertas")

operacoes = carregar_operacoes()
abertas = [op for op in operacoes if op.get("status") == "aberta"]

if abertas:
    total_funding = total_basis = total_taxa = total_total = 0.0

    for idx, ordem in enumerate(abertas):
        try:
            preco_atual_perp = float(client.futures_symbol_ticker(symbol=ordem["symbol_perpetuo"])["price"])
            preco_atual_fut = float(requests.get(f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={ordem['symbol_futuro']}").json()["price"])
            data_ts = int(datetime.strptime(ordem["data_entrada"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).timestamp() * 1000)
            taxas = get_funding_history(ordem["symbol_perpetuo"], start_time=data_ts)
            pnl_funding = sum(taxas) * ordem["volume_usd"]
            apr = calcular_apr(taxas)
            pnl_futuro = (preco_atual_fut - ordem["preco_entrada_futuro"]) * (ordem["volume_usd"] / ordem["preco_entrada_perp"])
            pnl_perp = (ordem["preco_entrada_perp"] - preco_atual_perp) * (ordem["volume_usd"] / ordem["preco_entrada_perp"])
            pnl_basis = pnl_futuro + pnl_perp
            taxa_abertura = ordem.get("taxa_abertura", round(ordem["volume_usd"] * 2 * 0.0004, 2))
            pnl_total = pnl_funding + pnl_basis - taxa_abertura

            total_funding += pnl_funding
            total_basis += pnl_basis
            total_taxa += taxa_abertura
            total_total += pnl_total
        except Exception as e:
            st.warning(f"Erro ao calcular PnL: {str(e)}")
            pnl_funding = pnl_basis = apr = pnl_futuro = pnl_perp = pnl_total = taxa_abertura = 0.0

        with st.container():
            st.markdown(f"### Ordem #{idx+1} — {ordem['symbol_perpetuo']}")
            col1, col2 = st.columns([2, 1])
            with col1:
                st.markdown(f'''
**Entrada:** `{ordem['data_entrada']}`  
**Volume:** `${ordem['volume_usd']}`  
**Funding Entrada:** `{ordem['funding_rate_entrada_diario']:.4%}`  
**Timestamp Ref.:** `{datetime.fromtimestamp(ordem.get('funding_timestamp_entrada', 0)/1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC") if ordem.get('funding_timestamp_entrada') else "N/A"}`
''')
            with col2:
                st.metric("PnL Funding", f"${pnl_funding:.2f}")
                st.metric("PnL Futuro", f"${pnl_futuro:.2f}")
                st.metric("PnL Perp", f"${pnl_perp:.2f}")
                st.metric("PnL Basis", f"${pnl_basis:.2f}")
                st.metric("Taxa Abertura", f"-${taxa_abertura:.2f}")
                st.metric("PnL Total", f"${pnl_total:.2f}")
                st.metric("APR Est.", f"{apr*100:.2f}%")

        st.divider()
        if st.button(f"❌ Fechar Ordem #{idx+1}", key=f"fechar_{idx}"):
            try:
                preco_atual_perp = float(client.futures_symbol_ticker(symbol=ordem["symbol_perpetuo"])["price"])
                preco_atual_fut = float(requests.get(f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={ordem['symbol_futuro']}").json()["price"])
                qty_perp = calcular_qty(ordem["volume_usd"], ordem["preco_entrada_perp"], ordem["symbol_perpetuo"])
                qty_fut = calcular_qty(ordem["volume_usd"], ordem["preco_entrada_futuro"], ordem["symbol_futuro"])
                client.futures_create_order(symbol=ordem["symbol_perpetuo"], side="BUY", type="MARKET", quantity=qty_perp)
                client.futures_create_order(symbol=ordem["symbol_futuro"], side="SELL", type="MARKET", quantity=qty_fut)
                ordem["status"] = "fechada"
                ordem["preco_saida_perp"] = preco_atual_perp
                ordem["preco_saida_futuro"] = preco_atual_fut
                salvar_operacoes(operacoes)
                st.success(f"✅ Ordem #{idx+1} fechada com sucesso!")
            except Exception as e:
                st.error(f"Erro ao fechar a ordem: {e}")

    st.subheader("📊 Resumo Total das Operações Abertas")
    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
    col_f1.metric("Total PnL Funding", f"${total_funding:.2f}")
    col_f2.metric("Total PnL Basis", f"${total_basis:.2f}")
    col_f3.metric("Total Taxas", f"-${total_taxa:.2f}")
    col_f4.metric("Total PnL Geral", f"${total_total:.2f}")
else:
    st.info("Nenhuma operação aberta.")
