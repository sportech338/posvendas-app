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
# 🔧 NORMALIZAÇÃO E LIMPEZA
# ======================================================
# Limpar nomes das colunas
df_pedidos.columns = df_pedidos.columns.str.strip()

# 🔢 CONVERTER VALOR TOTAL PRIMEIRO (ANTES DE QUALQUER AGRUPAMENTO)
df_pedidos["Valor Total"] = pd.to_numeric(
    df_pedidos["Valor Total"], errors="coerce"
).fillna(0)

# Normalizar datas
df_pedidos["Data de criação"] = (
    pd.to_datetime(df_pedidos["Data de criação"], errors="coerce", utc=True)
    .dt.tz_convert("America/Sao_Paulo")
    .dt.tz_localize(None)
)

# ======================================================
# 🔑 CHAVE DO CLIENTE
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
# 🧮 RECÁLCULO DAS MÉTRICAS DE CLIENTES
# ======================================================
df = (
    df_pedidos
    .groupby("cliente_key", as_index=False)
    .agg(
        Cliente=("Cliente", "last"),
        Email=("Email", "last"),
        Qtd_Pedidos=("Pedido ID", "count"),
        Valor_Total=("Valor Total", "sum"),  # Soma dos valores
        Primeiro_Pedido=("Data de criação", "min"),
        Ultimo_Pedido=("Data de criação", "max"),
    )
)

# Renomear coluna para padronizar
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
# 🏷️ NIVEL (força do cliente)
# ======================================================
def calcular_nivel(qtd):
    if qtd >= 5:
        return "Campeão"
    if qtd >= 3:
        return "Leal"
    if qtd >= 2:
        return "Promissor"
    return "Novo"

df["Nivel"] = df["Qtd_Pedidos"].apply(calcular_nivel)


# ======================================================
# 🚦 ESTADO (situação atual)
# ======================================================
def calcular_estado(dias):
    if dias >= 90:
        return "💤 Dormente"
    if dias >= 45:
        return "🚨 Em risco"
    return "🟢 Ativo"

df["Estado"] = df["Dias sem comprar"].apply(calcular_estado)


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

c3.metric("🏆 Campeões", len(df[df["Nivel"] == "Campeão"]))
c4.metric("🚨 Em risco", len(df[df["Estado"] == "🚨 Em risco"]))

st.divider()


# ======================================================
# 📋 CONFIGURAÇÃO DAS TABELAS
# ======================================================
COLUNAS = [
    "Cliente",
    "Email",
    "Estado",
    "Nivel",
    "Qtd_Pedidos",
    "Valor Total",
    "Último Pedido",
    "Dias sem comprar"
]

NIVEIS = ["Novo", "Promissor", "Leal", "Campeão"]


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
    (df["Estado"] == "🟢 Ativo") &
    (df["Nivel"].isin(filtro_ativa))
].sort_values(
    ["Valor Total", "Último Pedido"],
    ascending=[False, False]
)

# Formatar valor para exibição
df_ativa_display = df_ativa[COLUNAS].copy()
df_ativa_display["Valor Total"] = df_ativa_display["Valor Total"].apply(
    lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
)

st.dataframe(df_ativa_display, use_container_width=True, height=420)
st.caption(f"{len(df_ativa)} clientes ativos")
st.divider()


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
    (df["Estado"] == "🚨 Em risco") &
    (df["Nivel"].isin(filtro_risco))
].sort_values(
    ["Dias sem comprar", "Valor Total"],
    ascending=[False, False]
)

# Formatar valor para exibição
df_risco_display = df_risco[COLUNAS].copy()
df_risco_display["Valor Total"] = df_risco_display["Valor Total"].apply(
    lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
)

st.dataframe(df_risco_display, use_container_width=True, height=420)
st.caption(f"{len(df_risco)} clientes em risco")
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
    (df["Estado"] == "💤 Dormente") &
    (df["Nivel"].isin(filtro_dorm))
].sort_values(
    ["Dias sem comprar"],
    ascending=False
)

# Formatar valor para exibição
df_dormentes_display = df_dormentes[COLUNAS].copy()
df_dormentes_display["Valor Total"] = df_dormentes_display["Valor Total"].apply(
    lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
)

st.dataframe(df_dormentes_display, use_container_width=True, height=420)
st.caption(f"{len(df_dormentes)} clientes dormentes")
