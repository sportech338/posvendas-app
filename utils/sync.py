# utils/sync.py

import pandas as pd

from utils.shopify import puxar_pedidos_pagos_em_lotes
from utils.sheets import (
    append_aba,
    ler_aba,
    ler_ids_existentes
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
    Fluxo:
    Shopify → Pedidos Shopify (append incremental)
           → Clientes Shopify (recalculado)
    """

    # ==================================================
    # 1. IDS JÁ EXISTENTES
    # ==================================================
    ids_existentes = ler_ids_existentes(
        planilha=nome_planilha,
        aba="Pedidos Shopify",
        coluna_id="Pedido ID"
    )

    total_novos = 0

    # ==================================================
    # 2. BUSCA POR LOTES
    # ==================================================
    for lote in puxar_pedidos_pagos_em_lotes(lote_tamanho):

        df_lote = pd.DataFrame(lote)
        df_lote["Pedido ID"] = df_lote["Pedido ID"].astype(str)

        # Remove duplicados
        df_lote = df_lote[
            ~df_lote["Pedido ID"].isin(ids_existentes)
        ]

        if df_lote.empty:
            continue

        append_aba(
            planilha=nome_planilha,
            aba="Pedidos Shopify",
            df=df_lote
        )

        ids_existentes.update(df_lote["Pedido ID"].tolist())
        total_novos += len(df_lote)

    # ==================================================
    # 3. NENHUM PEDIDO NOVO
    # ==================================================
    if total_novos == 0:
        return {
            "status": "success",
            "mensagem": "Nenhum pedido novo encontrado."
        }

    # ==================================================
    # 4. REGERAR CLIENTES (DERIVADO)
    # ==================================================
    df_pedidos = ler_aba(nome_planilha, "Pedidos Shopify")
    df_clientes = gerar_clientes(df_pedidos)

    # ⚠️ Base derivada → pode sobrescrever
    append_aba(
        planilha=nome_planilha,
        aba="Clientes Shopify",
        df=df_clientes
    )

    # ==================================================
    # 5. RETORNO
    # ==================================================
    return {
        "status": "success",
        "mensagem": (
            f"✅ Sincronização concluída\n"
            f"🆕 Pedidos novos: {total_novos}\n"
            f"👥 Clientes atualizados: {len(df_clientes)}"
        )
    }
