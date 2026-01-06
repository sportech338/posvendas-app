# streamlit_app.py

import streamlit as st
import pandas as pd
import time

from utils.sync import sincronizar_shopify_completo
from utils.sheets import ler_aba
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

# ==============================
# AUTO-REFRESH A CADA 10 MIN
# ==============================
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = time.time()

if time.time() - st.session_state.last_refresh > 600:
    st.session_state.last_refresh = time.time()
    st.rerun()


st.title("📦 Pós-vendas SporTech")
st.caption("Shopify → Google Sheets → Dashboard de Clientes")
st.divider()


# ======================================================
# CONSTANTES
# ======================================================
PLANILHA = "Clientes Shopify"
ABA_CLIENTES = "Clientes Shopify"
ABA_PEDIDOS = "Pedidos Shopify"


# ======================================================
# 📦 CARREGAMENTO DOS CLIENTES (JÁ AGREGADOS)
# ======================================================
@st.cache_data(ttl=300)
def carregar_clientes():
    """
    Carrega dados JÁ AGREGADOS da aba 'Clientes Shopify'.
    
    Não precisa processar pedidos individualmente, pois a sincronização
    já fez a agregação e salvou na planilha.
    
    TTL: 5 minutos (300 segundos)
    """
    return ler_aba(PLANILHA, ABA_CLIENTES)


# ======================================================
# 🔄 SINCRONIZAÇÃO SHOPIFY
# ======================================================
st.subheader("🔄 Sincronização com Shopify")

col_sync1, col_sync2 = st.columns([3, 1])

with col_sync1:
    st.caption(
        "Sincroniza pedidos da Shopify, agrega clientes e atualiza a planilha. "
        "Execute sempre que houver novos pedidos."
    )

with col_sync2:
    if st.button("🔄 Sincronizar Agora", use_container_width=True, type="primary"):
        with st.spinner("🔄 Sincronizando com Shopify..."):
            try:
                resultado = sincronizar_shopify_completo(
                    nome_planilha=PLANILHA,
                    lote_tamanho=500
                )
                
                if resultado["status"] == "success":
                    st.success(resultado["mensagem"])
                    # Limpar cache específico
                    carregar_clientes.clear()
                    st.rerun()  # Recarregar app automaticamente
                elif resultado["status"] == "warning":
                    st.warning(resultado["mensagem"])
                else:
                    st.error(resultado["mensagem"])
                    
            except Exception as e:
                st.error(f"❌ Erro na sincronização: {str(e)}")

st.divider()


# ======================================================
# CARREGAR DADOS
# ======================================================
try:
    df = carregar_clientes()
except Exception as e:
    st.error(f"❌ Erro ao carregar dados: {str(e)}")
    st.info("💡 Execute a sincronização primeiro para criar a aba 'Clientes Shopify'")
    st.stop()
    
df["Último Pedido"] = pd.to_datetime(
    df["Último Pedido"],
    errors="coerce",
    dayfirst=True
)

# ======================================================
# 🧾 LOG — QUALIDADE DA COLUNA "ÚLTIMO PEDIDO"
# ======================================================
total_clientes = len(df)
sem_data = df["Último Pedido"].isna().sum()

st.caption(
    f"🧾 Log dados | Último Pedido inválido: {sem_data} / {total_clientes}"
)

with st.expander("🧪 Debug — Último Pedido com problema", expanded=False):
    df_debug = df[df["Último Pedido"].isna()].copy()
    
    st.write(f"Total registros com problema: {len(df_debug)}")
    
    if not df_debug.empty:
        st.dataframe(
            df_debug[[
                "Customer ID",
                "Cliente",
                "Email",
                "Último Pedido",
                "Qtd Pedidos",
                "Valor Total"
            ]],
            use_container_width=True,
            hide_index=True
        )


if df.empty:
    st.warning("⚠️ Nenhum cliente encontrado. Execute a sincronização primeiro.")
    st.stop()


# ======================================================
# 🔧 NORMALIZAÇÃO DE COLUNAS
# ======================================================
df.columns = df.columns.str.strip()

# Validar colunas obrigatórias (AGORA USA "Nível")
colunas_obrigatorias = [
    "Customer ID",
    "Cliente", 
    "Email", 
    "Estado", 
    "Nível",
    "Qtd Pedidos", 
    "Valor Total", 
    "Último Pedido", 
    "Dias sem comprar"
]

colunas_faltantes = set(colunas_obrigatorias) - set(df.columns)

if colunas_faltantes:
    st.error(f"❌ Colunas faltantes na planilha: {', '.join(colunas_faltantes)}")
    st.info("💡 Execute a sincronização completa para corrigir a estrutura da planilha")
    st.stop()


# ======================================================
# 📊 ANÁLISE DE CICLO DE COMPRA
# ======================================================
with st.expander("📊 Análise de Ciclo de Compra — Ajustar Thresholds", expanded=False):
    st.write("### Validação dos critérios de classificação")
    
    try:
        ciclo = calcular_ciclo_medio(df)
        
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
                f"💡 Para ajustar, modifique os thresholds em `utils/sync.py` na função `sincronizar_shopify_completo()`"
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
# 📈 MÉTRICAS TOPO (AGORA USA "Nível")
# ======================================================
col1, col2, col3, col4 = st.columns(4)

total_clientes = len(df)
faturamento_total = df["Valor Total"].sum()
total_campeoes = len(df[df["Nível"] == "Campeão"])
total_em_risco = len(df[df["Estado"] == "🚨 Em risco"])

col1.metric("👥 Total de clientes", f"{total_clientes:,}".replace(",", "."))

col2.metric(
    "💰 Faturamento total",
    f"R$ {faturamento_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
)

col3.metric("🏆 Campeões", total_campeoes)
col4.metric("🚨 Em risco", total_em_risco)

st.divider()


# ======================================================
# 📋 CONFIGURAÇÃO DAS TABELAS (AGORA USA "Nível")
# ======================================================
COLUNAS_DISPLAY = [
    "Cliente",
    "Email",
    "Estado",
    "Nível",
    "Qtd Pedidos",
    "Valor Total",
    "Último Pedido",
    "Dias sem comprar"
]

CLASSIFICACOES = ["Iniciante", "Promissor", "Leal", "Campeão"]


# ======================================================
# FUNÇÃO AUXILIAR: FORMATAR TABELA
# ======================================================
def formatar_tabela(df_input: pd.DataFrame) -> pd.DataFrame:
    """
    Formata DataFrame para exibição:
    - Valor Total → formato brasileiro (R$ 1.234,56)
    - Último Pedido → data brasileira (dd/mm/yyyy)
    """
    df_display = df_input[COLUNAS_DISPLAY].copy()
    
    # Formatar valor monetário
    df_display["Valor Total"] = df_display["Valor Total"].apply(
        lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    )
    
    # ======================================================
    # FORMATAR DATA (ROBUSTO — SEM DEPENDER DO DTYPE)
    # ======================================================
    df_display["Último Pedido"] = (
        pd.to_datetime(
            df_input["Último Pedido"],
            errors="coerce",
            dayfirst=True
        )
        .dt.strftime("%d/%m/%Y %H:%M")
        .fillna("-")
    )
    
    return df_display


# ======================================================
# 🟢 BASE ATIVA (AGORA USA "Nível")
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

df_ativa = (
    df[
        (df["Estado"] == "🟢 Ativo") &
        (df["Nível"].isin(filtro_ativa))
    ]
    .sort_values("Último Pedido", ascending=False)
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
# 🚨 EM RISCO (AGORA USA "Nível")
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

df_risco = (
    df[
        (df["Estado"] == "🚨 Em risco") &
        (df["Nível"].isin(filtro_risco))
    ]
    .sort_values("Último Pedido", ascending=False)
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
# 💤 DORMENTES (AGORA USA "Nível")
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

df_dormentes = (
    df[
        (df["Estado"] == "💤 Dormente") &
        (df["Nível"].isin(filtro_dormentes))
    ]
    .sort_values("Último Pedido", ascending=False)
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
    f"🔄 Cache: 5 minutos | "
    f"📅 Última atualização: {pd.Timestamp.now().strftime('%d/%m/%Y %H:%M:%S')} | "
    f"📊 Total de registros: {len(df)}"
)
