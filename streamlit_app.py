# streamlit_app.py

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
    with st.spinner("🔄 Sincronizando pedidos pagos da Shopify..."):
        resultado = sincronizar_shopify_com_planilha(
            nome_planilha=PLANILHA,
            lote_tamanho=500
        )

    st.success(resultado["mensagem"])
    st.cache_data.clear()
    st.rerun()

st.divider()

# ======================================================
# 📄 CARREGAMENTO DA PLANILHA (CLIENTES)
# ======================================================
df = ler_aba(PLANILHA, "Clientes Shopify")

if df.empty:
    st.info("ℹ️ Nenhum dado encontrado na planilha.")
    st.stop()

# ======================================================
# 🧹 NORMALIZAÇÃO DE COLUNAS
# ======================================================
df.columns = df.columns.str.strip()

# Datas
df["Primeira_Compra"] = pd.to_datetime(df["Primeira_Compra"], errors="coerce")
df["Ultima_Compra"] = pd.to_datetime(df["Ultima_Compra"], errors="coerce")

# Numéricos
df["Qtd_Pedidos"] = pd.to_numeric(df["Qtd_Pedidos"], errors="coerce").fillna(0)
df["Valor_Total_Gasto"] = pd.to_numeric(
    df["Valor_Total_Gasto"],
    errors="coerce"
).fillna(0)

# Texto
df["Classificação"] = df["Classificação"].astype(str)

# ======================================================
# PRIORIDADE OPERACIONAL
# ======================================================
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

# ======================================================
# FUNÇÃO AUXILIAR DE TABELA
# ======================================================
def render_tabela(df_base, titulo, filtro_key):
    st.subheader(titulo)

    filtro = st.multiselect(
        "Filtrar por nível",
        options=["Campeão", "Leal", "Promissor", "Novo"],
        default=["Campeão", "Leal", "Promissor", "Novo"],
        key=filtro_key
    )

    df = df_base.copy()

    if filtro:
        df = df[df["Classificação"].str.contains("|".join(filtro), na=False)]

    df = df.sort_values(
        ["Prioridade", "Ultima_Compra"],
        ascending=[True, False]
    )

    st.dataframe(
        df[
            [
                "Classificação",
                "Cliente",
                "Email",
                "Primeira_Compra",
                "Ultima_Compra",
                "Qtd_Pedidos",
                "Valor_Total_Gasto"
            ]
        ],
        use_container_width=True,
        height=420
    )

    st.divider()

# ======================================================
# SEÇÕES
# ======================================================
render_tabela(
    df[df["Classificação"].str.contains("🚨", na=False)],
    "🚨 Em risco — Ação imediata",
    "risco"
)

render_tabela(
    df[
        (~df["Classificação"].str.contains("🚨", na=False)) &
        (~df["Classificação"].str.contains("💤", na=False)) &
        (~df["Classificação"].str.contains("não comprou", case=False, na=False))
    ],
    "🟢 Base ativa",
    "ativo"
)

render_tabela(
    df[df["Classificação"].str.contains("💤", na=False)],
    "💤 Dormentes — Reativação",
    "dorm"
)

st.subheader("⛔ Fora do Pós-vendas")
st.metric(
    "⛔ Não comprou ainda",
    len(df[df["Classificação"].str.contains("não comprou", case=False, na=False)])
)
