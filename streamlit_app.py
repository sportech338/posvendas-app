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
# 📊 PAINEL DE CLIENTES
# ======================================================
st.subheader("📊 Painel de Clientes")

ABA_CLIENTES = "Clientes Shopify"

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

# Datas
df["Primeiro Pedido"] = pd.to_datetime(df["Primeiro Pedido"], errors="coerce")
df["Último Pedido"] = pd.to_datetime(df["Último Pedido"], errors="coerce")

# Numéricos
df["Qtd Pedidos"] = pd.to_numeric(df["Qtd Pedidos"], errors="coerce").fillna(0)

df["Valor Total"] = (
    df["Valor Total"]
    .astype(str)
    .str.replace("R$", "", regex=False)
    .str.replace(" ", "", regex=False)
    .str.replace(".", "", regex=False)
    .str.replace(",", ".", regex=False)
)

df["Valor Total"] = pd.to_numeric(
    df["Valor Total"],
    errors="coerce"
).fillna(0)


df["Dias sem comprar"] = pd.to_numeric(
    df["Dias sem comprar"], errors="coerce"
).fillna(0)

df["Classificação"] = df["Classificação"].astype(str)

# ======================================================
# MÉTRICAS
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
# FILTROS
# ======================================================
st.subheader("🔎 Filtros")

col1, col2, col3 = st.columns(3)

with col1:
    filtro_class = st.multiselect(
        "Classificação",
        options=sorted(df["Classificação"].unique()),
        default=sorted(df["Classificação"].unique())
    )

with col2:
    min_dias = int(df["Dias sem comprar"].min())
    max_dias = int(df["Dias sem comprar"].max())

    filtro_dias = st.slider(
        "Dias sem comprar",
        min_value=min_dias,
        max_value=max_dias,
        value=(min_dias, max_dias)
    )

with col3:
    ordem = st.selectbox(
        "Ordenar por",
        [
            "Último Pedido (mais recente)",
            "Último Pedido (mais antigo)",
            "Maior Valor Total",
            "Maior Qtd Pedidos"
        ]
    )

# ======================================================
# APLICA FILTROS
# ======================================================
df_filtrado = df[
    (df["Classificação"].isin(filtro_class)) &
    (df["Dias sem comprar"].between(filtro_dias[0], filtro_dias[1]))
]

# Ordenação
if ordem == "Último Pedido (mais recente)":
    df_filtrado = df_filtrado.sort_values("Último Pedido", ascending=False)
elif ordem == "Último Pedido (mais antigo)":
    df_filtrado = df_filtrado.sort_values("Último Pedido", ascending=True)
elif ordem == "Maior Valor Total":
    df_filtrado = df_filtrado.sort_values("Valor Total", ascending=False)
elif ordem == "Maior Qtd Pedidos":
    df_filtrado = df_filtrado.sort_values("Qtd Pedidos", ascending=False)

st.divider()

# ======================================================
# TABELA
# ======================================================
st.subheader("📋 Clientes")

st.dataframe(
    df_filtrado[
        [
            "Cliente",
            "Email",
            "Classificação",
            "Qtd Pedidos",
            "Valor Total",
            "Primeiro Pedido",
            "Último Pedido",
            "Dias sem comprar"
        ]
    ],
    use_container_width=True,
    height=550
)

st.caption(f"Mostrando {len(df_filtrado)} de {len(df)} clientes")
