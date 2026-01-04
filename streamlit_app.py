import streamlit as st
import pandas as pd

from utils.sheets import ler_aba, append_aba, ler_ids_existentes
from utils.shopify import puxar_pedidos_pagos_em_lotes
from utils.sync import gerar_clientes

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
# 🔄 SINCRONIZAÇÃO SHOPIFY → PLANILHA (COM PROGRESSO)
# ======================================================
st.subheader("🔄 Sincronização de dados")

if st.button("🔄 Atualizar dados da Shopify"):

    progresso = st.progress(0)
    status = st.empty()

    ids_existentes = ler_ids_existentes(
        planilha=PLANILHA,
        aba="Pedidos Shopify",
        coluna_id="Pedido ID"
    )

    total_novos = 0
    total_processados = 0
    lote_atual = 0

    for lote in puxar_pedidos_pagos_em_lotes(lote_tamanho=500):
        lote_atual += 1
        df_lote = pd.DataFrame(lote)
        df_lote["Pedido ID"] = df_lote["Pedido ID"].astype(str)

        # Remove duplicados
        df_lote = df_lote[~df_lote["Pedido ID"].isin(ids_existentes)]

        if not df_lote.empty:
            append_aba(
                planilha=PLANILHA,
                aba="Pedidos Shopify",
                df=df_lote
            )

            ids_existentes.update(df_lote["Pedido ID"].tolist())
            total_novos += len(df_lote)

        total_processados += len(lote)

        # Atualiza UI
        progresso.progress(min(1.0, lote_atual * 0.05))
        status.info(
            f"📦 Lote {lote_atual} | "
            f"Pedidos processados: {total_processados} | "
            f"Novos inseridos: {total_novos}"
        )

    # ==================================================
    # 🔁 REGERAR CLIENTES
    # ==================================================
    status.info("🔄 Atualizando base de clientes...")

    df_pedidos = ler_aba(PLANILHA, "Pedidos Shopify")
    df_clientes = gerar_clientes(df_pedidos)

    # ⚠️ Clientes é base derivada → sobrescreve
    from utils.sheets import escrever_aba
    escrever_aba(
        planilha=PLANILHA,
        aba="Clientes Shopify",
        df=df_clientes
    )

    progresso.progress(1.0)
    status.success(
        f"✅ Sincronização concluída!\n"
        f"🆕 Pedidos novos: {total_novos}\n"
        f"👥 Clientes atualizados: {len(df_clientes)}"
    )

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

df.columns = df.columns.str.strip()
df["Classificação"] = df["Classificação"].astype(str)

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
def render_tabela(df, titulo, filtro_key):
    st.subheader(titulo)

    filtro = st.multiselect(
        "Filtrar por nível",
        options=["Campeão", "Leal", "Promissor", "Novo"],
        default=["Campeão", "Leal", "Promissor", "Novo"],
        key=filtro_key
    )

    if filtro:
        df = df[df["Classificação"].str.contains("|".join(filtro), na=False)]

    df = df.sort_values(["Prioridade", "Valor Total Gasto"], ascending=[True, False])

    st.dataframe(
        df[
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
