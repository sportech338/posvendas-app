import streamlit as st
import pandas as pd
from utils.sheets import carregar_aba

# ---------------- CONFIGURAÇÃO ----------------
st.set_page_config(
    page_title="Pós-vendas SporTech",
    layout="wide"
)

st.title("📦 Dashboard Pós-vendas — SporTech")
st.caption("Shopify + Google Sheets")
st.divider()

# ---------------- PLANILHA ----------------
PLANILHA = "Clientes Shopify"  # nome EXATO da planilha no Drive

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

# ---------------- NORMALIZAÇÃO ----------------
df_clientes.columns = df_clientes.columns.str.strip()
df_pedidos.columns = df_pedidos.columns.str.strip()
df_ignorados.columns = df_ignorados.columns.str.strip()

# ---------------- MAPA DE COLUNAS (ROBUSTO) ----------------
def achar_coluna(df, possiveis):
    for c in df.columns:
        for p in possiveis:
            if p.lower() in c.lower():
                return c
    return None

COL_PEDIDO_ID = achar_coluna(df_pedidos, ["pedido", "order"])
COL_DATA = achar_coluna(df_pedidos, ["data", "created", "process"])
COL_STATUS = achar_coluna(df_pedidos, ["status"])
COL_CUSTOMER = achar_coluna(df_pedidos, ["customer", "cliente", "id cliente"])

COL_CLIENTE_ID = achar_coluna(df_clientes, ["customer", "cliente", "id"])
COL_NOME = achar_coluna(df_clientes, ["nome", "name"])
COL_EMAIL = achar_coluna(df_clientes, ["email", "e-mail"])

COL_IGNORADOS = achar_coluna(df_ignorados, ["pedido", "order"])

# Validação mínima
colunas_obrigatorias = {
    "Pedido ID": COL_PEDIDO_ID,
    "Data": COL_DATA,
    "Status": COL_STATUS,
    "Customer ID": COL_CUSTOMER
}

for nome, col in colunas_obrigatorias.items():
    if col is None:
        st.error(f"Coluna obrigatória não encontrada: {nome}")
        st.stop()

# ---------------- FILA DE PÓS-VENDAS ----------------
st.divider()
st.header("📋 Fila Operacional de Pós-Vendas")

# Remover pedidos ignorados
ids_ignorados = set(df_ignorados[COL_IGNORADOS].astype(str))

df_fila = df_pedidos.copy()
df_fila[COL_PEDIDO_ID] = df_fila[COL_PEDIDO_ID].astype(str)
df_fila = df_fila[~df_fila[COL_PEDIDO_ID].isin(ids_ignorados)]

# Converter data
df_fila[COL_DATA] = pd.to_datetime(df_fila[COL_DATA], errors="coerce")

# Ordenar
df_fila = df_fila.sort_values(COL_DATA)

# Cruzar com clientes
df_clientes[COL_CLIENTE_ID] = df_clientes[COL_CLIENTE_ID].astype(str)
df_fila[COL_CUSTOMER] = df_fila[COL_CUSTOMER].astype(str)

df_fila = df_fila.merge(
    df_clientes[
        [COL_CLIENTE_ID, COL_NOME, COL_EMAIL]
    ],
    left_on=COL_CUSTOMER,
    right_on=COL_CLIENTE_ID,
    how="left"
)

# ---------------- FILTROS ----------------
st.subheader("🔎 Filtros")

col1, col2 = st.columns(2)

with col1:
    status_opcoes = df_fila[COL_STATUS].dropna().unique().tolist()
    status_filtro = st.multiselect(
        "Status do pedido",
        options=status_opcoes,
        default=status_opcoes
    )

with col2:
    data_min = st.date_input(
        "Pedidos a partir de",
        df_fila[COL_DATA].min().date()
    )

df_fila = df_fila[
    (df_fila[COL_STATUS].isin(status_filtro)) &
    (df_fila[COL_DATA].dt.date >= data_min)
]

# ---------------- TABELA FINAL ----------------
st.caption("Pedidos válidos aguardando ação do time de pós-vendas")

st.dataframe(
    df_fila[
        [
            COL_PEDIDO_ID,
            COL_DATA,
            COL_NOME,
            COL_EMAIL,
            COL_STATUS
        ]
    ].rename(columns={
        COL_PEDIDO_ID: "Pedido",
        COL_DATA: "Data",
        COL_NOME: "Cliente",
        COL_EMAIL: "Email",
        COL_STATUS: "Status"
    }),
    use_container_width=True,
    height=520
)
