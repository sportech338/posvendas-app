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
)
