# utils/sync.py

import pandas as pd

from utils.shopify import puxar_pedidos_pagos_em_lotes
from utils.sheets import (
    append_aba,
    ler_aba,
    ler_ids_existentes,
    escrever_aba
)

# ======================================================
# GERA CLIENTES A PARTIR DOS PEDIDOS
# ======================================================
def gerar_clientes(df_pedidos: pd.DataFrame) -> pd.DataFrame:
    """
    Consolida a base de clientes a partir da aba 'Pedidos Shopify'
    """
    if df_pedidos.empty:
        return pd.DataFrame()

    df = df_pedidos.copy()
    df["Data de criação"] = pd.to_datetime(df["Data de criação"], errors="coerce")

    clientes = (
        df
        .dropna(subset=["Customer ID"])
        .groupby("Customer ID")
        .agg(
            Cliente=("Cliente", "first"),
            Email=("Email", "first"),
            Qtd_Pedidos=("Pedido ID", "count"),
            Valor_Total_Gasto=("Valor Total", "sum"),
            Primeira_Compra=("Data de criação", "min"),
            Ultima_Compra=("Data de criação", "max"),
        )
        .reset_index()
    )

    return clientes


# ======================================================
# SINCRONIZAÇÃO SHOPIFY → PLANILHA (INCREMENTAL)
# ======================================================
def sincronizar_shopify_com_planilha(
    nome_planilha: str = "Clientes Shopify",
    lote_tamanho: int = 500
) -> dict:
    """
    Fluxo completo:
    1. Shopify → Pedidos Shopify (append incremental)
    2. Pedidos Shopify → Clientes Shopify (regerado)
    """

    # ==================================================
    # 1. LER IDS JÁ EXISTENTES (ANTI-DUPLICAÇÃO)
    # ==================================================
    ids_existentes = ler_ids_existentes(
        planilha=nome_planilha,
        aba="Pedidos Shopify",
        coluna_id="Pedido ID"
    )

    total_novos = 0

    # ==================================================
    # 2. BUSCAR PEDIDOS EM LOTES
    # ==================================================
    for lote in puxar_pedidos_pagos_em_lotes(lote_tamanho):

        df_lote = pd.DataFrame(lote)
        df_lote["Pedido ID"] = df_lote["Pedido ID"].astype(str)

        # Remove pedidos já registrados
        df_lote = df_lote[
            ~df_lote["Pedido ID"].isin(ids_existentes)
        ]

        if df_lote.empty:
            continue

        # Append incremental
        append_aba(
            planilha=nome_planilha,
            aba="Pedidos Shopify",
            df=df_lote
        )

        ids_existentes.update(df_lote["Pedido ID"].tolist())
        total_novos += len(df_lote)

    # ==================================================
    # 3. SE NÃO HOUVE NOVOS PEDIDOS
    # ==================================================
    if total_novos == 0:
        return {
            "status": "success",
            "mensagem": "Nenhum pedido novo encontrado."
        }

    # ==================================================
    # 4. REGERAR BASE DE CLIENTES (DERIVADA)
    # ==================================================
    df_pedidos = ler_aba(nome_planilha, "Pedidos Shopify")
    df_clientes = gerar_clientes(df_pedidos)

    # ⚠️ Clientes é base derivada → SOBRESCREVE
    escrever_aba(
        planilha=nome_planilha,
        aba="Clientes Shopify",
        df=df_clientes
    )

    # ==================================================
    # 5. RETORNO PARA O STREAMLIT
    # ==================================================
    return {
        "status": "success",
        "mensagem": (
            f"✅ Sincronização concluída com sucesso\n"
            f"🆕 Pedidos novos: {total_novos}\n"
            f"👥 Clientes atualizados: {len(df_clientes)}"
        )
    }
