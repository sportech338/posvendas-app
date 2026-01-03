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

# ---------------- PRIORIDADE (ROBUSTA E ESCALÁVEL) ----------------
def calcular_prioridade(classificacao: str) -> int:
    c = classificacao.lower()

    # 🚨 EM RISCO — prioridade máxima
    if "🚨" in classificacao and "campeão" in c:
        return 1
    if "🚨" in classificacao and "leal" in c:
        return 2
    if "🚨" in classificacao and "promissor" in c:
        return 3
    if "🚨" in classificacao and "novo" in c:
        return 4

    # 🏆 NORMAIS
    if "campeão" in c and "💤" not in classificacao:
        return 5
    if "leal" in c and "💤" not in classificacao:
        return 6
    if "promissor" in c and "💤" not in classificacao:
        return 7
    if "novo" in c and "💤" not in classificacao:
        return 8

    # 💤 DORMENTES (MENOR PRIORIDADE)
    if "💤" in classificacao and "campeão" in c:
        return 9
    if "💤" in classificacao and "leal" in c:
        return 10
    if "💤" in classificacao and "promissor" in c:
        return 11
    if "💤" in classificacao and "novo" in c:
        return 12

    # ⛔ NÃO COMPROU
    if "não comprou" in c:
        return 99

    return 100


df["Prioridade"] = df["Classificação"].apply(calcular_prioridade)

# ---------------- KPIs ----------------
st.subheader("📊 Visão Geral")

c1, c2, c3, c4, c5 = st.columns(5)

c1.metric("Total clientes", len(df))

c2.metric(
    "🚨 Campeões",
    df["Classificação"].str.contains("🚨") &
    df["Classificação"].str.contains("Campeão")
)

c3.metric(
    "🚨 Leais",
    df["Classificação"].str.contains("🚨") &
    df["Classificação"].str.contains("Leal")
)

c4.metric(
    "💤 Dormentes",
    df["Classificação"].str.contains("💤").sum()
)

c5.metric(
    "Campeões ativos",
    (
        df["Classificação"].str.contains("Campeão") &
        ~df["Classificação"].str.contains("🚨") &
        ~df["Classificação"].str.contains("💤")
    ).sum()
)

# ---------------- FILTROS ----------------
st.divider()
st.subheader("🔎 Filtros")

col1, col2 = st.columns(2)

with col1:
    filtro_class = st.multiselect(
        "Classificação",
        options=sorted(df["Classificação"].unique()),
        default=sorted(df["Classificação"].unique())
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

