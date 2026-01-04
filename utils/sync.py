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
    if df_pedidos.empty:
        return pd.DataFrame()

    df = df_pedidos.copy()
    df["Data de criação"] = pd.to_datetime(df["Data de criação"])

    clientes = (
        df
        .groupby("Customer ID", dropna=True)
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
# SINCRONIZAÇÃO INCREMENTAL
# ======================================================
def sincronizar_shopify_com_planilha(
    nome_planilha: str = "Clientes Shopify",
    lote_tamanho: int = 500
) -> dict:
    """
    Shopify → Pedidos Shopify (append incremental)
            → Clientes Shopify (recalculado)
    """

    # =========================
    # IDS JÁ EXISTENTES
    # =========================
    ids_existentes = ler_ids_existentes(
        planilha=nome_planilha,
        aba="Pedidos Shopify",
        coluna_id="Pedido ID"
    )

    total_novos = 0

    # =========================
    # LOOP POR LOTES
    # =========================
    for lote in puxar_pedidos_pagos_em_lotes(lote_tamanho):

        df_lote = pd.DataFrame(lote)
        df_lote["Pedido ID"] = df_lote["Pedido ID"].astype(str)

        # Remove pedidos já existentes
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

    if total_novos == 0:
        return {
            "status": "success",
            "mensagem": "Nenhum pedido novo encontrado."
        }

    # =========================
    # REGERAR CLIENTES
    # =========================
    df_pedidos = ler_aba(nome_planilha, "Pedidos Shopify")
    df_clientes = gerar_clientes(df_pedidos)

    # ⚠️ Clientes pode sobrescrever (base derivada)
    append_aba(
        planilha=nome_planilha,
        aba="Clientes Shopify",
        df=df_clientes
    )

    return {
        "status": "success",
        "mensagem": (
            f"Sincronização concluída com sucesso.\n"
            f"🆕 Pedidos novos: {total_novos}\n"
            f"👥 Clientes atualizados: {len(df_clientes)}"
        )
    }
