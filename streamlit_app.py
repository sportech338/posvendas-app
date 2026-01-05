# streamlit_app.py

import streamlit as st
import pandas as pd

from utils.sync import sincronizar_shopify_com_planilha
from utils.sheets import ler_aba

# ======================================================
# CONFIGURAÇÃO GERAL
# ======================================================
st.set_page_config(
    page_title="Pós-vendas SporTech",
    layout="wide"
)

st.title("📦 Pós-vendas SporTech")
st.caption("Shopify → Google Sheets → Painel de Clientes")
st.divider()

PLANILHA = "Clientes Shopify"
ABA_CLIENTES = "Clientes Shopify"

# ======================================================
# 🔄 SINCRONIZAÇÃO SHOPIFY
# ======================================================
st.subheader("🔄 Sincronização de pedidos")

if st.button("🔄 Atualizar pedidos pagos"):
    with st.spinner("Buscando pedidos pagos na Shopify..."):
        resultado = sincronizar_shopify_com_planilha(
            nome_planilha=PLANILHA,
            lote_tamanho=500
        )

    st.success(resultado["mensagem"])
    st.cache_data.clear()

st.divider()

# ======================================================
# 📊 CARREGAMENTO DOS CLIENTES
# ======================================================
@st.cache_data(ttl=300)
def carregar_clientes():
    return ler_aba(PLANILHA, ABA_CLIENTES)

df = carregar_clientes()

if df.empty:
    st.warning("Nenhum cliente encontrado na aba Clientes Shopify.")
    st.stop()

# ======================================================
# NORMALIZAÇÃO
# ======================================================
df.columns = df.columns.str.strip()

df["Primeiro Pedido"] = pd.to_datetime(df["Primeiro Pedido"], errors="coerce")
df["Último Pedido"] = pd.to_datetime(df["Último Pedido"], errors="coerce")

df["Qtd Pedidos"] = pd.to_numeric(df["Qtd Pedidos"], errors="coerce").fillna(0)

df["Valor Total"] = (
    df["Valor Total"]
    .astype(str)
    .str.replace("R$", "", regex=False)
    .str.replace(" ", "", regex=False)
    .str.replace(".", "", regex=False)
    .str.replace(",", ".", regex=False)
)

df["Valor Total"] = pd.to_numeric(df["Valor Total"], errors="coerce").fillna(0)

df["Dias sem comprar"] = pd.to_numeric(
    df["Dias sem comprar"], errors="coerce"
).fillna(0)

df["Classificação"] = df["Classificação"].astype(str)

# ======================================================
# 📈 MÉTRICAS TOPO
# ======================================================
c1, c2, c3, c4 = st.columns(4)

c1.metric("👥 Total de clientes", len(df))

faturamento = df["Valor Total"].sum()
c2.metric(
    "💰 Faturamento total",
    f"R$ {faturamento:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
)

c3.metric("🏆 Campeões", len(df[df["Classificação"].str.contains("Campeão", na=False)]))
c4.metric("🚨 Em risco", len(df[df["Classificação"].str.contains("🚨", na=False)]))

st.divider()

# ======================================================
# 📋 TABELAS
# ======================================================
COLUNAS = [
    "Cliente",
    "Email",
    "Classificação",
    "Qtd Pedidos",
    "Valor Total",
    "Último Pedido",
    "Dias sem comprar"
]

NIVEIS = ["Campeão", "Leal", "Promissor", "Novo"]

# ======================================================
# 🚨 EM RISCO
# ======================================================
st.subheader("🚨 Em risco — ação imediata")

filtro_risco = st.multiselect(
    "Filtrar Em risco por nível",
    NIVEIS,
    default=NIVEIS,
    key="risco"
)

df_risco = df[
    df["Classificação"].str.contains("🚨", na=False) &
    df["Classificação"].str.contains("|".join(filtro_risco), na=False)
].sort_values(
    ["Dias sem comprar", "Valor Total"],
    ascending=[False, False]
)

st.dataframe(df_risco[COLUNAS], use_container_width=True, height=420)
st.caption(f"{len(df_risco)} clientes em risco")
st.divider()

# ======================================================
# 🟢 BASE ATIVA
# ======================================================
st.subheader("🟢 Base ativa")

filtro_ativa = st.multiselect(
    "Filtrar Base ativa por nível",
    NIVEIS,
    default=NIVEIS,
    key="ativa"
)

df_ativa = df[
    (~df["Classificação"].str.contains("🚨", na=False)) &
    (~df["Classificação"].str.contains("💤", na=False)) &
    (df["Classificação"].str.contains("|".join(filtro_ativa), na=False))
].sort_values(
    ["Valor Total", "Último Pedido"],
    ascending=[False, False]
)

st.dataframe(df_ativa[COLUNAS], use_container_width=True, height=420)
st.caption(f"{len(df_ativa)} clientes ativos")
st.divider()

# ======================================================
# 💤 DORMENTES
# ======================================================
st.subheader("💤 Dormentes — reativação")

filtro_dorm = st.multiselect(
    "Filtrar Dormentes por nível",
    NIVEIS,
    default=NIVEIS,
    key="dormentes"
)

df_dormentes = df[
    df["Classificação"].str.contains("💤", na=False) &
    df["Classificação"].str.contains("|".join(filtro_dorm), na=False)
].sort_values(
    ["Dias sem comprar"],
    ascending=False
)

st.dataframe(df_dormentes[COLUNAS], use_container_width=True, height=420)
st.caption(f"{len(df_dormentes)} clientes dormentes")
