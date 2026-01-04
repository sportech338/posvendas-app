import streamlit as st
import pandas as pd

from utils.sheets import ler_aba
from utils.sync import sincronizar_shopify_com_planilha

# ======================================================
# CONFIGURAÇÃO GERAL
# ======================================================
st.set_page_config(
    page_title="Pós-vendas SporTech",
    layout="wide"
)

st.title("📦 Dashboard Pós-vendas — SporTech")
st.caption("Fluxo: Shopify → Google Sheets → Streamlit")
st.divider()

PLANILHA = "Clientes Shopify"

# ======================================================
# 🔄 SINCRONIZAÇÃO SHOPIFY → PLANILHA
# ======================================================
st.subheader("🔄 Sincronização de dados")

if st.button("🔄 Atualizar dados da Shopify"):
    with st.spinner("Buscando pedidos pagos na Shopify..."):
        resultado = sincronizar_shopify_com_planilha(PLANILHA)

    if resultado["status"] == "success":
        st.success(resultado["mensagem"])
        st.cache_data.clear()
        st.rerun()

    elif resultado["status"] == "warning":
        st.warning(resultado["mensagem"])

    else:
        st.error("❌ Erro inesperado durante a sincronização.")

st.divider()

# ======================================================
# 📄 CARREGAMENTO DA PLANILHA (CLIENTES)
# ======================================================
df = ler_aba(PLANILHA, "Clientes Shopify")

if df.empty:
    st.info("ℹ️ Nenhum dado encontrado na planilha.")
    st.stop()

df.columns = df.columns.str.strip()
df["Classificação"] = df["Classificação"].astype(str)

# Normalização de colunas numéricas
df["Qtd Pedidos"] = pd.to_numeric(df["Qtd Pedidos"], errors="coerce").fillna(0)

df["Valor Total Gasto"] = (
    df["Valor Total Gasto"]
    .astype(str)
    .str.replace("R$", "", regex=False)
    .str.replace(".", "", regex=False)
    .str.replace(",", ".", regex=False)
    .astype(float)
    .fillna(0)
)

# ======================================================
# 🔢 PRIORIDADE OPERACIONAL
# ======================================================
def calcular_prioridade(classificacao: str) -> int:
    c = classificacao.lower()

    # 🚨 EM RISCO
    if "🚨" in classificacao and "campeão" in c: return 1
    if "🚨" in classificacao and "leal" in c: return 2
    if "🚨" in classificacao and "promissor" in c: return 3
    if "🚨" in classificacao and "novo" in c: return 4

    # 🟢 BASE ATIVA
    if classificacao == "Campeão": return 5
    if classificacao == "Leal": return 6
    if classificacao == "Promissor": return 7
    if classificacao == "Novo": return 8

    # 💤 DORMENTES
    if "💤" in classificacao and "campeão" in c: return 9
    if "💤" in classificacao and "leal" in c: return 10
    if "💤" in classificacao and "promissor" in c: return 11
    if "💤" in classificacao and "novo" in c: return 12

    # ⛔ FORA DO PÓS-VENDAS
    if "não comprou" in c: return 99

    return 100


df["Prioridade"] = df["Classificação"].apply(calcular_prioridade)

# ======================================================
# 🚨 EM RISCO — AÇÃO IMEDIATA
# ======================================================
st.subheader("🚨 Em risco — Ação imediata")

df_risco = df[df["Classificação"].str.contains("🚨", na=False)]

filtro_risco = st.multiselect(
    "Filtrar por nível",
    options=["Campeão", "Leal", "Promissor", "Novo"],
    default=["Campeão", "Leal", "Promissor", "Novo"],
    key="filtro_risco"
)

if filtro_risco:
    df_risco = df_risco[
        df_risco["Classificação"].str.contains("|".join(filtro_risco), na=False)
    ]

df_risco = df_risco.sort_values(
    ["Prioridade", "Valor Total Gasto"],
    ascending=[True, False]
)

st.dataframe(
    df_risco[
        [
            "Classificação",
            "Cliente",
            "Email",
            "Primeira Compra",
            "Última Compra",
            "Qtd Pedidos",
            "Valor Total Gasto"
        ]
    ],
    use_container_width=True,
    height=420
)

st.divider()

# ======================================================
# 🟢 BASE ATIVA
# ======================================================
st.subheader("🟢 Base ativa")

df_ativo = df[
    (~df["Classificação"].str.contains("🚨", na=False)) &
    (~df["Classificação"].str.contains("💤", na=False)) &
    (~df["Classificação"].str.contains("não comprou", case=False, na=False))
]

filtro_ativo = st.multiselect(
    "Filtrar por nível",
    options=["Campeão", "Leal", "Promissor", "Novo"],
    default=["Campeão", "Leal", "Promissor", "Novo"],
    key="filtro_ativo"
)

if filtro_ativo:
    df_ativo = df_ativo[df_ativo["Classificação"].isin(filtro_ativo)]

df_ativo = df_ativo.sort_values(
    ["Prioridade", "Valor Total Gasto"],
    ascending=[True, False]
)

st.dataframe(
    df_ativo[
        [
            "Classificação",
            "Cliente",
            "Email",
            "Primeira Compra",
            "Última Compra",
            "Qtd Pedidos",
            "Valor Total Gasto"
        ]
    ],
    use_container_width=True,
    height=420
)

st.divider()

# ======================================================
# 💤 DORMENTES — REATIVAÇÃO
# ======================================================
st.subheader("💤 Dormentes — Reativação")

df_dorm = df[df["Classificação"].str.contains("💤", na=False)]

filtro_dorm = st.multiselect(
    "Filtrar por nível",
    options=["Campeão", "Leal", "Promissor", "Novo"],
    default=["Campeão", "Leal", "Promissor", "Novo"],
    key="filtro_dorm"
)

if filtro_dorm:
    df_dorm = df_dorm[
        df_dorm["Classificação"].str.contains("|".join(filtro_dorm), na=False)
    ]

df_dorm = df_dorm.sort_values(
    ["Prioridade", "Valor Total Gasto"],
    ascending=[True, False]
)

st.dataframe(
    df_dorm[
        [
            "Classificação",
            "Cliente",
            "Email",
            "Primeira Compra",
            "Última Compra",
            "Qtd Pedidos",
            "Valor Total Gasto"
        ]
    ],
    use_container_width=True,
    height=420
)

st.divider()

# ======================================================
# ⛔ FORA DO PÓS-VENDAS
# ======================================================
st.subheader("⛔ Fora do Pós-vendas")

df_out = df[df["Classificação"].str.contains("não comprou", case=False, na=False)]

st.metric("⛔ Não comprou ainda", len(df_out))
