import streamlit as st
import pandas as pd

from utils.sheets import ler_aba, append_aba, ler_ids_existentes, escrever_aba
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
# 🔄 SINCRONIZAÇÃO SHOPIFY → PLANILHA (PROGRESSO REAL)
# ======================================================
st.subheader("🔄 Sincronização de dados")

if st.button("🔄 Atualizar dados da Shopify"):

    status = st.empty()
    st.cache_data.clear()
    ids_existentes = ler_ids_existentes(
        planilha=PLANILHA,
        aba="Pedidos Shopify",
        coluna_id="Pedido ID"
    )

    total_lidos = 0
    total_novos = 0
    lote_atual = 0

    with st.spinner("🔍 Buscando pedidos pagos desde 2023..."):

        for lote in puxar_pedidos_pagos_em_lotes(
            lote_tamanho=500,
            data_inicio="2023-01-01T00:00:00-03:00"
        ):
            lote_atual += 1
            df_lote = pd.DataFrame(lote)

            total_lidos += len(df_lote)

            df_lote["Pedido ID"] = df_lote["Pedido ID"].astype(str)

            # Remove duplicados
            df_lote = df_lote[
                ~df_lote["Pedido ID"].isin(ids_existentes)
            ]

            if not df_lote.empty:
                append_aba(
                    planilha=PLANILHA,
                    aba="Pedidos Shopify",
                    df=df_lote
                )

                ids_existentes.update(df_lote["Pedido ID"].tolist())
                total_novos += len(df_lote)

            status.info(
                f"📦 Lote {lote_atual}\n"
                f"📥 Pedidos lidos: {total_lidos}\n"
                f"🆕 Pedidos novos: {total_novos}"
            )

    # ==================================================
    # 🔁 REGERAR CLIENTES (BASE DERIVADA)
    # ==================================================
    status.info("🔄 Recalculando base de clientes...")

    df_pedidos = ler_aba(PLANILHA, "Pedidos Shopify")
    df_clientes = gerar_clientes(df_pedidos)

    escrever_aba(
        planilha=PLANILHA,
        aba="Clientes Shopify",
        df=df_clientes
    )

    status.success(
        "✅ Sincronização concluída com sucesso!\n\n"
        f"📥 Pedidos lidos: {total_lidos}\n"
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

# ✅ Limpa espaços nos nomes das colunas
df.columns = df.columns.str.strip()

# ✅ Garante que a coluna de data exista (aceita 3 variações)
if "Última Compra" not in df.columns:
    if "Ultima Compra" in df.columns:
        df = df.rename(columns={"Ultima Compra": "Última Compra"})
    elif "Ultima_Compra" in df.columns:
        df = df.rename(columns={"Ultima_Compra": "Última Compra"})

# ✅ Agora converte com segurança
df["Última Compra"] = pd.to_datetime(df["Última Compra"], errors="coerce")

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

    df = df.sort_values(
        ["Prioridade", "Última Compra"],
        ascending=[True, False]
    )
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
