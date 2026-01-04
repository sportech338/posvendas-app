# streamlit_app.py

import streamlit as st
from utils.sync import sincronizar_shopify_com_planilha

# ======================================================
# CONFIGURAÇÃO GERAL
# ======================================================
st.set_page_config(
    page_title="Sync Pedidos Shopify — SporTech",
    layout="wide"
)

st.title("🔄 Sincronização de Pedidos — SporTech")
st.caption("Shopify → Google Sheets (aba Pedidos Shopify)")
st.divider()

PLANILHA = "Clientes Shopify"

# ======================================================
# 🔄 SINCRONIZAÇÃO SHOPIFY → PEDIDOS SHOPIFY
# ======================================================

if st.button("🔄 Atualizar pedidos pagos"):
    with st.spinner("Buscando pedidos pagos na Shopify..."):
        resultado = sincronizar_shopify_com_planilha(
            nome_planilha=PLANILHA,
            lote_tamanho=500
        )

    st.success(resultado["mensagem"])
    st.cache_data.clear()
