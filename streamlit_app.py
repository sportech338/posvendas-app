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

    # 🚨 EM RISCO
    if "🚨" in classificacao and "campeão" in c:
        return 1
    if "🚨" in classificacao and "leal" in c:
        return 2
    if "🚨" in classificacao and "promissor" in c:
        return 3
    if "🚨" in classificacao and "novo" in c:
        return 4

    # 🟢 ATIVOS
    if classificacao == "Campeão":
        return 5
    if classificacao == "Leal":
        return 6
    if classificacao == "Promissor":
        return 7
    if classificacao == "Novo":
        return 8

    # 💤 DORMENTES
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

# ---------------- VISÃO GERAL (TODOS OS CARDS) ----------------
st.subheader("📊 Visão Geral — Classificação de Clientes")

def contar(texto):
    return df["Classificação"].str.fullmatch(texto, na=False).sum()

def contem(texto):
    return df["Classificação"].str.contains(texto, na=False).sum()

# ===== 🚨 EM RISCO =====
st.markdown("### 🚨 Em risco")

r1, r2, r3, r4 = st.columns(4)
r1.metric("🚨 Campeão", contem("🚨 Campeão"))
r2.metric("🚨 Leal", contem("🚨 Leal"))
r3.metric("🚨 Promissor", contem("🚨 Promissor"))
r4.metric("🚨 Novo", contem("🚨 Novo"))

st.divider()

# ===== 🟢 ATIVOS =====
st.markdown("### 🟢 Ativos")

a1, a2, a3, a4 = st.columns(4)
a1.metric("Campeão", contar("Campeão"))
a2.metric("Leal", contar("Leal"))
a3.metric("Promissor", contar("Promissor"))
a4.metric("Novo", contar("Novo"))

st.divider()

# ===== 💤 DORMENTES =====
st.markdown("### 💤 Dormentes")

d1, d2, d3, d4 = st.columns(4)
d1.metric("💤 Campeão", contem("💤 Campeão"))
d2.metric("💤 Leal", contem("💤 Leal"))
d3.metric("💤 Promissor", contem("💤 Promissor"))
d4.metric("💤 Novo", contem("💤 Novo"))

st.divider()

# ===== ⛔ NÃO COMPROU =====
st.markdown("### ⛔ Fora do Pós-vendas")

f1, _ = st.columns(2)
f1.metric("⛔ Não comprou ainda", contem("Não comprou"))

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
