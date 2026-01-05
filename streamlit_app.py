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
ABA_PEDIDOS = "Pedidos Shopify"


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
# 📦 CARREGAMENTO DOS PEDIDOS (FONTE DA VERDADE)
# ======================================================
@st.cache_data(ttl=300)
def carregar_pedidos():
    return ler_aba(PLANILHA, ABA_PEDIDOS)

df_pedidos = carregar_pedidos()

if df_pedidos.empty:
    st.warning("Nenhum pedido encontrado na aba Pedidos Shopify.")
    st.stop()


# ======================================================
# 🔧 NORMALIZAÇÃO DE DATAS (ISO SHOPIFY)
# ======================================================
df_pedidos.columns = df_pedidos.columns.str.strip()

df_pedidos["Data de criação"] = (
    pd.to_datetime(df_pedidos["Data de criação"], errors="coerce", utc=True)
    .dt.tz_convert("America/Sao_Paulo")
    .dt.tz_localize(None)
)

# ======================================================
# 🔑 CHAVE DO CLIENTE (EMAIL → CUSTOMER ID)
# ======================================================
df_pedidos["cliente_key"] = (
    df_pedidos["Email"]
    .astype(str)
    .str.lower()
    .str.strip()
)

df_pedidos.loc[df_pedidos["cliente_key"] == "", "cliente_key"] = (
    "ID_" + df_pedidos["Customer ID"].astype(str)
)

# ======================================================
# 🔢 GARANTE TIPOS
# ======================================================
df_pedidos["Valor Total"] = pd.to_numeric(
    df_pedidos["Valor Total"], errors="coerce"
).fillna(0)


# ======================================================
# 🧮 RECÁLCULO DAS MÉTRICAS DE CLIENTES
# ======================================================
df = (
    df_pedidos
    .groupby("cliente_key")
    .agg(
        Cliente=("Cliente", "last"),
        Email=("Email", "last"),
        Qtd_Pedidos=("Pedido ID", "count"),
        Valor_Total=("Valor Total", "sum"),
        Primeiro_Pedido=("Data de criação", "min"),
        Ultimo_Pedido=("Data de criação", "max"),
    )
    .reset_index(drop=True)
)

# Padroniza nomes para o painel
df = df.rename(columns={
    "Valor_Total": "Valor Total",
    "Primeiro_Pedido": "Primeiro Pedido",
    "Ultimo_Pedido": "Último Pedido",
})

# ======================================================
# 📆 DIAS SEM COMPRAR
# ======================================================
hoje = pd.Timestamp.now(tz="America/Sao_Paulo").tz_localize(None)
df["Dias sem comprar"] = (hoje - df["Último Pedido"]).dt.days


# ======================================================
# 🏷️ CLASSIFICAÇÃO (EXEMPLO — AJUSTE SEU CRITÉRIO)
# ======================================================
def classificar(row):
    if row["Dias sem comprar"] >= 90:
        return "💤 Dormente"
    if row["Dias sem comprar"] >= 45:
        return "🚨 Em risco"
    if row["Qtd_Pedidos"] >= 5:
        return "Campeão"
    if row["Qtd_Pedidos"] >= 3:
        return "Leal"
    if row["Qtd_Pedidos"] >= 2:
        return "Promissor"
    return "Novo"

df["Classificação"] = df.apply(classificar, axis=1)


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

c3.metric("🏆 Campeões", len(df[df["Classificação"] == "Campeão"]))
c4.metric("🚨 Em risco", len(df[df["Classificação"].str.contains("🚨", na=False)]))

st.divider()


# ======================================================
# 📋 TABELAS
# ======================================================
COLUNAS = [
    "Cliente",
    "Email",
    "Classificação",
    "Qtd_Pedidos",
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
