import streamlit as st
import pandas as pd
from utils.sheets import carregar_aba

# ---------------- CONFIG ----------------
st.set_page_config(
    page_title="Pós-vendas SporTech",
    layout="wide"
)

st.title("📦 Dashboard Pós-vendas — SporTech")
st.caption("Leitura direta da classificação definida na planilha")
st.divider()

# ---------------- PLANILHA ----------------
PLANILHA = "Clientes Shopify"

# ---------------- LOAD ----------------
df = carregar_aba(PLANILHA, "Clientes Shopify")
df.columns = df.columns.str.strip()

# ---------------- MAPA DE PRIORIDADE ----------------
PRIORIDADE_MAP = {
    "🚨 Campeão": 1,
    "🚨 Leal": 2,
    "Campeão": 3,
    "Leal": 4,
    "Promissor": 5,
    "Novo": 6,
    "Dormente": 7,
    "Não comprou ainda": 8,
}

df["Prioridade"] = df["Classificação"].map(PRIORIDADE_MAP).fillna(99).astype(int)

# ---------------- KPIs ----------------
st.subheader("📊 Visão Geral")

c1, c2, c3, c4 = st.columns(4)

c1.metric("Total clientes", len(df))
c2.metric("🚨 Campeões", (df["Classificação"] == "🚨 Campeão").sum())
c3.metric("🚨 Leais", (df["Classificação"] == "🚨 Leal").sum())
c4.metric("Dormentes", (df["Classificação"] == "Dormente").sum())

# ---------------- FILTROS ----------------
st.divider()
st.subheader("🔎 Filtros")

col1, col2 = st.columns(2)

with col1:
    filtro_class = st.multiselect(
        "Classificação",
        options=sorted(df["Classificação"].dropna().unique()),
        default=sorted(df["Classificação"].dropna().unique())
    )

with col2:
    busca = st.text_input("Buscar cliente ou email")

df_view = df[df["Classificação"].isin(filtro_class)]

if busca:
    busca = busca.lower()
    df_view = df_view[
        df_view["Cliente"].str.lower().str.contains(busca, na=False) |
        df_view["Email"].str.lower().str.contains(busca, na=False)
    ]

# ---------------- TABELA PRINCIPAL ----------------
st.divider()
st.subheader("📋 Fila de Prioridade do Pós-vendas")

df_view = df_view.sort_values(
    by=["Prioridade", "Valor Total Gasto"],
    ascending=[True, False]
)

st.dataframe(
    df_view[
        [
            "Prioridade",
            "Classificação",
            "Cliente",
            "Email",
            "Qtd Pedidos",
            "Valor Total Gasto",
            "Última Compra",
        ]
    ],
    use_container_width=True,
    height=520
)
