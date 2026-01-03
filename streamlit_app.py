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

# Garante string
df["Classificação"] = df["Classificação"].astype(str)

# ---------------- PRIORIDADE (ROBUSTA) ----------------
def calcular_prioridade(classificacao: str) -> int:
    if "🚨" in classificacao and "Campeão" in classificacao:
        return 1
    if "🚨" in classificacao and "Leal" in classificacao:
        return 2
    if "Campeão" in classificacao:
        return 3
    if "Leal" in classificacao:
        return 4
    if "Promissor" in classificacao:
        return 5
    if "Novo" in classificacao:
        return 6
    if "Dormente" in classificacao:
        return 7
    if "Não comprou ainda" in classificacao:
        return 8
    return 99

df["Prioridade"] = df["Classificação"].apply(calcular_prioridade)

# ---------------- KPIs ----------------
st.subheader("📊 Visão Geral")

c1, c2, c3, c4 = st.columns(4)

c1.metric("Total clientes", len(df))

c2.metric(
    "🚨 Campeões",
    (
        df["Classificação"].str.contains("🚨", na=False) &
        df["Classificação"].str.contains("Campeão", na=False)
    ).sum()
)

c3.metric(
    "🚨 Leais",
    (
        df["Classificação"].str.contains("🚨", na=False) &
        df["Classificação"].str.contains("Leal", na=False)
    ).sum()
)

c4.metric(
    "Dormentes",
    df["Classificação"].str.contains("Dormente", na=False).sum()
)

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
