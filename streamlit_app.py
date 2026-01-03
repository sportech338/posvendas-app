import streamlit as st
import pandas as pd
from utils.sheets import carregar_aba

# ---------------- CONFIGURAÇÃO DA PÁGINA ----------------
st.set_page_config(
    page_title="Pós-vendas SporTech",
    layout="wide"
)

st.title("📦 Dashboard Pós-vendas — SporTech")
st.caption("Shopify + Google Sheets")
st.divider()

# ---------------- PLANILHA ----------------
PLANILHA = "Clientes Shopify"  # NOME EXATO DA PLANILHA

# ---------------- CONEXÃO ----------------
st.subheader("🔗 Conexão com dados")

try:
    df_clientes = carregar_aba(PLANILHA, "Clientes Shopify")
    df_pedidos = carregar_aba(PLANILHA, "Pedidos Shopify")
    df_ignorados = carregar_aba(PLANILHA, "Pedidos Ignorados")

    st.success("Planilha conectada com sucesso ✅")

except Exception as e:
    st.error("Erro ao conectar com Google Sheets")
    st.exception(e)
    st.stop()

# ---------------- PAINEL OPERACIONAL ----------------
st.divider()
st.header("📋 Fila de Pós-Vendas")

# Normalizar colunas
df_pedidos.columns = df_pedidos.columns.str.strip()
df_ignorados.columns = df_ignorados.columns.str.strip()
df_clientes.columns = df_clientes.columns.str.strip()

# Remover pedidos ignorados
ids_ignorados = set(df_ignorados["Pedido ID"].astype(str))

df_fila = df_pedidos.copy()
df_fila["Pedido ID"] = df_fila["Pedido ID"].astype(str)
df_fila = df_fila[~df_fila["Pedido ID"].isin(ids_ignorados)]

# Converter data
df_fila["Data Pedido"] = pd.to_datetime(
    df_fila["Data Pedido"],
    errors="coerce"
)

df_fila = df_fila.sort_values("Data Pedido")

# Cruzar com clientes
df_fila["Customer ID"] = df_fila["Customer ID"].astype(str)
df_clientes["Customer ID"] = df_clientes["Customer ID"].astype(str)

df_fila = df_fila.merge(
    df_clientes[
        ["Customer ID", "Cliente", "Email"]
    ],
    on="Customer ID",
    how="left"
)

# ---------------- FILTROS ----------------
st.subheader("🔎 Filtros")

col1, col2 = st.columns(2)

with col1:
    status_opcoes = df_fila["Status"].unique().tolist()
    status_filtro = st.multiselect(
        "Status do pedido",
        options=status_opcoes,
        default=status_opcoes
    )

with col2:
    data_min = st.date_input(
        "Pedidos a partir de",
        df_fila["Data Pedido"].min().date()
    )

df_fila = df_fila[
    (df_fila["Status"].isin(status_filtro)) &
    (df_fila["Data Pedido"].dt.date >= data_min)
]

# ---------------- TABELA FINAL ----------------
st.caption("Pedidos válidos aguardando ação do pós-vendas")

st.dataframe(
    df_fila[
        [
            "Pedido ID",
            "Data Pedido",
            "Cliente",
            "Email",
            "Status"
        ]
    ],
    use_container_width=True,
    height=520
)
