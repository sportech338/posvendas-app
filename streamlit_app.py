# streamlit_app.py

import streamlit as st
import pandas as pd

from utils.sync import sincronizar_incremental, carregar_dados_planilha, calcular_estatisticas
from utils.classificacao import calcular_ciclo_medio


# ======================================================
# CONFIGURAÇÃO GERAL
# ======================================================
st.set_page_config(
    page_title="Pós-vendas SporTech",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.title("📦 Pós-vendas SporTech")
st.caption("Shopify → Google Sheets → Dashboard atualizado automaticamente")
st.divider()


# ======================================================
# 📦 CARREGAMENTO COM AUTO-SYNC
# ======================================================
@st.cache_data(ttl=300)
def carregar_dados_com_sync():
    """
    Carrega dados COM sincronização automática a cada 5 min.
    
    1. Sincroniza (adiciona novos pedidos)
    2. Carrega da planilha (instantâneo)
    """
    # Sincronizar primeiro
    resultado = sincronizar_incremental()
    
    # Carregar da planilha
    df_clientes = carregar_dados_planilha()
    
    return df_clientes, resultado


# ======================================================
# 🔄 BOTÃO DE SINCRONIZAÇÃO MANUAL
# ======================================================
st.subheader("🔄 Sincronização com Shopify")

col_info, col_btn = st.columns([3, 1])

with col_info:
    st.caption(
        "✨ **Sincronização automática a cada 5 minutos**  \n"
        "Detecta e adiciona novos pedidos automaticamente!"
    )

with col_btn:
    if st.button("🔄 Sincronizar Agora", use_container_width=True, type="primary"):
        carregar_dados_com_sync.clear()
        st.rerun()

st.divider()


# ======================================================
# CARREGAR DADOS
# ======================================================
try:
    with st.spinner("🔄 Sincronizando com Shopify..."):
        df_clientes, resultado_sync = carregar_dados_com_sync()
        
        # Mostrar resultado da sincronização
        if resultado_sync.get("novos_pedidos", 0) > 0:
            st.success(f"🆕 {resultado_sync['novos_pedidos']} novos pedidos encontrados!")
        
except Exception as e:
    st.error(f"❌ Erro ao carregar dados: {str(e)}")
    st.info("💡 Execute a primeira sincronização para criar as abas necessárias")
    st.stop()

if df_clientes.empty:
    st.warning("⚠️ Nenhum cliente encontrado.")
    st.stop()


# ======================================================
# 📊 ANÁLISE DE CICLO DE COMPRA
# ======================================================
with st.expander("📊 Análise de Ciclo de Compra — Ajustar Thresholds", expanded=False):
    st.write("### Validação dos critérios de classificação")
    
    try:
        ciclo = calcular_ciclo_medio(df_clientes)
        
        if ciclo["total_recorrentes"] >= 5:
            col1, col2 = st.columns(2)
            
            with col1:
                st.metric(
                    "📅 Ciclo médio de compra (mediana)", 
                    f"{ciclo['ciclo_mediana']:.0f} dias"
                )
            
            with col2:
                st.metric(
                    "📊 Clientes recorrentes analisados",
                    ciclo['total_recorrentes']
                )
            
            st.caption(f"Média: {ciclo['ciclo_media']:.1f} dias")
            
            st.write("**💡 Thresholds sugeridos baseados nos seus dados:**")
            
            col_t1, col_t2, col_t3 = st.columns(3)
            
            with col_t1:
                st.success(
                    f"**🟢 Ativo**\n\n"
                    f"Até {ciclo['threshold_ativo']} dias"
                )
            
            with col_t2:
                st.warning(
                    f"**🚨 Em Risco**\n\n"
                    f"{ciclo['threshold_ativo']} - {ciclo['threshold_risco']} dias"
                )
            
            with col_t3:
                st.error(
                    f"**💤 Dormente**\n\n"
                    f"Mais de {ciclo['threshold_risco']} dias"
                )
            
            st.info(
                f"📌 **Atualmente usando:** Ativo < 45 dias | Em Risco 45-90 dias | Dormente > 90 dias\n\n"
                f"💡 Para ajustar, modifique os thresholds em `utils/sync.py` na função `sincronizar_incremental()`"
            )
        else:
            st.warning(
                f"⚠️ Poucos clientes recorrentes para análise estatística "
                f"(encontrados: {ciclo['total_recorrentes']}, mínimo: 5)"
            )
            st.info(
                "Os thresholds atuais (45/90 dias) são estimativas genéricas. "
                "Ajuste conforme seu negócio crescer."
            )
    except Exception as e:
        st.error(f"❌ Erro ao calcular ciclo de compra: {str(e)}")

st.divider()


# ======================================================
# 📈 MÉTRICAS TOPO
# ======================================================
stats = calcular_estatisticas(df_clientes)

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "👥 Total de clientes", 
    f"{stats['total_clientes']:,}".replace(",", ".")
)

col2.metric(
    "💰 Faturamento total",
    f"R$ {stats['faturamento_total']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
)

col3.metric("🏆 Campeões", stats['campeoes'])
col4.metric("🚨 Em risco", stats['em_risco'])

st.divider()


# ======================================================
# 📋 CONFIGURAÇÃO DAS TABELAS
# ======================================================
COLUNAS_DISPLAY = [
    "Cliente",
    "Email",
    "Estado",
    "Nível",
    "Qtd Pedidos",
    "Valor Total",
    "Ultimo Pedido",
    "Dias sem comprar"
]

CLASSIFICACOES = ["Novo", "Promissor", "Leal", "Campeão"]


# ======================================================
# FUNÇÃO AUXILIAR: FORMATAR TABELA
# ======================================================
def formatar_tabela(df_input: pd.DataFrame) -> pd.DataFrame:
    """
    Formata DataFrame para exibição:
    - Valor Total → formato brasileiro (R$ 1.234,56)
    - Ultimo Pedido → data brasileira (dd/mm/yyyy)
    """
    if df_input.empty:
        return pd.DataFrame(columns=COLUNAS_DISPLAY)
    
    df_display = df_input[COLUNAS_DISPLAY].copy()
    
    # Formatar valor monetário
    df_display["Valor Total"] = df_display["Valor Total"].apply(
        lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    )
    
    # Formatar data
    if pd.api.types.is_datetime64_any_dtype(df_input["Ultimo Pedido"]):
        df_display["Ultimo Pedido"] = df_input["Ultimo Pedido"].dt.strftime("%d/%m/%Y %H:%M")
    
    return df_display


# ======================================================
# 🟢 BASE ATIVA
# ======================================================
st.subheader("🟢 Base ativa")

col_filtro1, col_info1 = st.columns([3, 1])

with col_filtro1:
    filtro_ativa = st.multiselect(
        "Filtrar Base ativa por nível",
        CLASSIFICACOES,
        default=CLASSIFICACOES,
        key="filtro_ativa"
    )

df_ativa = df_clientes[
    (df_clientes["Estado"] == "🟢 Ativo") &
    (df_clientes["Nível"].isin(filtro_ativa))
].sort_values(
    ["Valor Total", "Ultimo Pedido"],
    ascending=[False, False]
)

with col_info1:
    st.metric("Total", len(df_ativa))

if not df_ativa.empty:
    df_ativa_display = formatar_tabela(df_ativa)
    st.dataframe(
        df_ativa_display, 
        use_container_width=True, 
        height=400,
        hide_index=True
    )
else:
    st.info("Nenhum cliente encontrado com os filtros selecionados.")

st.divider()


# ======================================================
# 🚨 EM RISCO
# ======================================================
st.subheader("🚨 Em risco — ação imediata")

col_filtro2, col_info2 = st.columns([3, 1])

with col_filtro2:
    filtro_risco = st.multiselect(
        "Filtrar Em risco por nível",
        CLASSIFICACOES,
        default=CLASSIFICACOES,
        key="filtro_risco"
    )

df_risco = df_clientes[
    (df_clientes["Estado"] == "🚨 Em risco") &
    (df_clientes["Nível"].isin(filtro_risco))
].sort_values(
    ["Dias sem comprar", "Valor Total"],
    ascending=[False, False]
)

with col_info2:
    st.metric("Total", len(df_risco))

if not df_risco.empty:
    df_risco_display = formatar_tabela(df_risco)
    st.dataframe(
        df_risco_display, 
        use_container_width=True, 
        height=400,
        hide_index=True
    )
else:
    st.info("✅ Nenhum cliente em risco no momento!")

st.divider()


# ======================================================
# 💤 DORMENTES
# ======================================================
st.subheader("💤 Dormentes — reativação")

col_filtro3, col_info3 = st.columns([3, 1])

with col_filtro3:
    filtro_dormentes = st.multiselect(
        "Filtrar Dormentes por nível",
        CLASSIFICACOES,
        default=CLASSIFICACOES,
        key="filtro_dormentes"
    )

df_dormentes = df_clientes[
    (df_clientes["Estado"] == "💤 Dormente") &
    (df_clientes["Nível"].isin(filtro_dormentes))
].sort_values(
    ["Dias sem comprar"],
    ascending=False
)

with col_info3:
    st.metric("Total", len(df_dormentes))

if not df_dormentes.empty:
    df_dormentes_display = formatar_tabela(df_dormentes)
    st.dataframe(
        df_dormentes_display, 
        use_container_width=True, 
        height=400,
        hide_index=True
    )
else:
    st.info("✅ Nenhum cliente dormente no momento!")


# ======================================================
# 📊 RODAPÉ COM INFORMAÇÕES
# ======================================================
st.divider()
st.caption(
    f"🔄 Atualização automática: 5 minutos | "
    f"📅 Última carga: {pd.Timestamp.now().strftime('%d/%m/%Y %H:%M:%S')} | "
    f"📊 Total de registros: {len(df_clientes)}"
)
