# clientes_app.py

import streamlit as st
import pandas as pd
from utils.sheets import ler_aba

# ======================================================
# CONFIGURAÇÃO GERAL
# ======================================================
st.set_page_config(
    page_title="Pós-vendas — Clientes SporTech",
    layout="wide"
)

st.title("📊 Painel de Clientes — Pós-vendas SporTech")
st.caption("Leitura direta da aba: Clientes Shopify")
st.divider()

PLANILHA = "Clientes Shopify"
ABA = "Clientes Shopify"

# ======================================================
# CARREGAMENTO DOS DADOS
# ======================================================
@st.cache_data(ttl=300)
def carregar_clientes():
    df = ler_aba(PLANILHA, ABA)
    return df

df = carregar_clientes()

if df.empty:
    st.warning("Nenhum cliente encontrado na planilha.")
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
    .str.replace(".", "", regex=False)
    .str.replace(",", ".", regex=False)
    .astype(float)
    .fillna(0)
)

df["Dias sem comprar"] = pd.to_numeric(
    df["Dias sem comprar"], errors="coerce"
).fillna(0)

# Texto
df["Classificação"] = df["Classificação"].astype(str)

# ======================================================
# MÉTRICAS TOPO
# ======================================================
c1, c2, c3, c4 = st.columns(4)

c1.metric("👥 Total de clientes", len(df))
c2.metric("💰 Faturamento total", f"R$ {df['Valor Total'].sum():,.2f}")
c3.metric("⭐ Campeões", len(df[df["Classificação"] == "Campeão"]))
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

# Aplica filtros
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
# TABELA PRINCIPAL
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

st.caption(
    f"Mostrando {len(df_filtrado)} de {len(df)} clientes"
)
