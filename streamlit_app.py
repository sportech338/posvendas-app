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

df["Classificação"] = df["Classificação"].astype(str)

# ---------------- PRIORIDADE ----------------
def calcular_prioridade(classificacao: str) -> int:
    c = classificacao.lower()

    if "🚨" in classificacao and "campeão" in c: return 1
    if "🚨" in classificacao and "leal" in c: return 2
    if "🚨" in classificacao and "promissor" in c: return 3
    if "🚨" in classificacao and "novo" in c: return 4

    if classificacao == "Campeão": return 5
    if classificacao == "Leal": return 6
    if classificacao == "Promissor": return 7
    if classificacao == "Novo": return 8

    if "💤" in classificacao and "campeão" in c: return 9
    if "💤" in classificacao and "leal" in c: return 10
    if "💤" in classificacao and "promissor" in c: return 11
    if "💤" in classificacao and "novo" in c: return 12

    if "não comprou" in c: return 99
    return 100


df["Prioridade"] = df["Classificação"].apply(calcular_prioridade)

# ---------------- VISÃO GERAL ----------------
st.subheader("📊 Visão Geral — Prioridades do Pós-vendas")

def conta(txt):
    return df["Classificação"].str.contains(txt, na=False).sum()

# ===== 🚨 EM RISCO (FOCO ABSOLUTO) =====
st.markdown("### 🚨 Ação imediata (Em risco)")

r1, r2, r3, r4 = st.columns(4)
r1.metric("🚨 Campeão", conta("🚨 Campeão"))
r2.metric("🚨 Leal", conta("🚨 Leal"))
r3.metric("🚨 Promissor", conta("🚨 Promissor"))
r4.metric("🚨 Novo", conta("🚨 Novo"))

st.divider()

# ===== 🟢 ATIVOS (CONTEXTO) =====
st.markdown("### 🟢 Base ativa")

a1, a2, a3, a4 = st.columns(4)
a1.metric("Campeão", (df["Classificação"] == "Campeão").sum())
a2.metric("Leal", (df["Classificação"] == "Leal").sum())
a3.metric("Promissor", (df["Classificação"] == "Promissor").sum())
a4.metric("Novo", (df["Classificação"] == "Novo").sum())

st.divider()

# ===== 💤 DORMENTES + ⛔ =====
st.markdown("### 💤 Backlog / Reativação")

d1, d2, d3, d4, d5 = st.columns(5)
d1.metric("💤 Campeão", conta("💤 Campeão"))
d2.metric("💤 Leal", conta("💤 Leal"))
d3.metric("💤 Promissor", conta("💤 Promissor"))
d4.metric("💤 Novo", conta("💤 Novo"))
d5.metric("⛔ Não comprou", conta("Não comprou"))

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

# ---------------- TABELA ----------------
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
