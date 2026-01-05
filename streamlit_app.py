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
df_pedidos.columns = df_pedidos.columns.str.strip()

# ✅ Valores já convertidos automaticamente por ler_aba() em utils/sheets.py
# Não precisa mais fazer conversão manual aqui!

# Normalizar datas
df_pedidos["Data de criação"] = (
    pd.to_datetime(df_pedidos["Data de criação"], errors="coerce", utc=True)
    .dt.tz_convert("America/Sao_Paulo")
    .dt.tz_localize(None)
)


# ======================================================
# 🔑 CHAVE DO CLIENTE (MELHORADO: USA CUSTOMER ID)
# ======================================================
# ✅ Customer ID é único por cliente na Shopify
# ✅ Email pode mudar, mas Customer ID permanece o mesmo
df_pedidos["cliente_key"] = (
    df_pedidos["Customer ID"]
    .astype(str)
    .str.strip()
)

# Fallback para clientes sem Customer ID (casos raros)
df_pedidos.loc[df_pedidos["cliente_key"] == "", "cliente_key"] = (
    "EMAIL_" + df_pedidos["Email"].astype(str).str.lower().str.strip()
)


# ======================================================
# 🧮 AGREGAÇÃO DE CLIENTES
# ======================================================
df = (
    df_pedidos
    .groupby("cliente_key", as_index=False)
    .agg(
        Customer_ID=("Customer ID", "first"),
        Cliente=("Cliente", "last"),
        Email=("Email", "last"),
        Qtd_Pedidos=("Pedido ID", "count"),
        Valor_Total=("Valor Total", "sum"),
        Primeiro_Pedido=("Data de criação", "min"),
        Ultimo_Pedido=("Data de criação", "max"),
    )
)

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
# 📊 ANÁLISE DE CICLO DE COMPRA (VALIDAÇÃO DE THRESHOLDS)
# ======================================================
with st.expander("📊 Análise de Ciclo de Compra - Ajustar Thresholds", expanded=False):
    st.write("### Validação dos critérios de classificação")
    
    # Calcular ciclo médio para clientes recorrentes
    clientes_recorrentes = df[df["Qtd_Pedidos"] >= 2].copy()
    
    if len(clientes_recorrentes) >= 5:  # Mínimo de 5 clientes para análise
        clientes_recorrentes["Dias_Total"] = (
            clientes_recorrentes["Último Pedido"] - 
            clientes_recorrentes["Primeiro Pedido"]
        ).dt.days
        
        clientes_recorrentes["Ciclo_Medio"] = (
            clientes_recorrentes["Dias_Total"] / 
            (clientes_recorrentes["Qtd_Pedidos"] - 1)
        )
        
        ciclo_mediana = clientes_recorrentes["Ciclo_Medio"].median()
        ciclo_media = clientes_recorrentes["Ciclo_Medio"].mean()
        
        st.metric("📅 Ciclo médio de compra (mediana)", f"{ciclo_mediana:.0f} dias")
        st.caption(f"Média: {ciclo_media:.0f} dias")
        
        st.write("**💡 Thresholds sugeridos baseados nos seus dados:**")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.success(f"**🟢 Ativo**\n\nAté {ciclo_mediana * 1.5:.0f} dias")
        
        with col2:
            st.warning(f"**🚨 Em Risco**\n\n{ciclo_mediana * 1.5:.0f} - {ciclo_mediana * 3:.0f} dias")
        
        with col3:
            st.error(f"**💤 Dormente**\n\nMais de {ciclo_mediana * 3:.0f} dias")
        
        st.info(
            f"📌 **Atualmente usando:** Ativo < 45 dias | Em Risco 45-90 dias | Dormente > 90 dias\n\n"
            f"Ajuste os valores na função `calcular_estado()` baseado na análise acima."
        )
    else:
        st.warning("⚠️ Poucos clientes recorrentes para análise estatística (mínimo: 5)")
        st.info("Os thresholds atuais (45/90 dias) são estimativas genéricas. Ajuste conforme seu negócio crescer.")

st.divider()


# ======================================================
# 🏷️ NIVEL (MELHORADO: considera valor + recência)
# ======================================================
def calcular_nivel(row):
    """
    Classifica cliente baseado em RFM (Recency, Frequency, Monetary)
    Alinhado com modelo de Escada de Valor do pós-vendas
    """
    qtd = row["Qtd_Pedidos"]
    valor = row["Valor Total"]
    dias = row["Dias sem comprar"]
    
    # 🏆 Campeão: Alto valor + frequência + comprou recentemente
    if (qtd >= 5 or valor >= 5000) and dias < 60:
        return "Campeão"
    
    # 💙 Leal: Compra regularmente com bom valor
    if (qtd >= 3 or valor >= 2000) and dias < 90:
        return "Leal"
    
    # ⭐ Promissor: Mostra potencial (2+ compras ou ticket alto)
    if (qtd >= 2 or valor >= 500) and dias < 120:
        return "Promissor"
    
    # 🆕 Novo: Primeira compra recente
    if qtd == 1 and dias < 90:
        return "Novo"
    
    # Fallback: classificar como Novo
    return "Novo"

df["Nivel"] = df.apply(calcular_nivel, axis=1)


# ======================================================
# 🚦 ESTADO (situação atual)
# ======================================================
def calcular_estado(dias):
    """
    Classificação temporal baseada em dias desde última compra
    TODO: Ajustar thresholds baseado na análise de ciclo de compra
    """
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

df_dormentes_display = df_dormentes[COLUNAS].copy()
df_dormentes_display["Valor Total"] = df_dormentes_display["Valor Total"].apply(
    lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
)

st.dataframe(df_dormentes_display, use_container_width=True, height=420)
st.caption(f"{len(df_dormentes)} clientes dormentes")
