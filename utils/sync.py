# utils/sync.py

import pandas as pd

from utils.shopify import puxar_pedidos_pagos_em_lotes
from utils.sheets import (
    append_aba,
    ler_ids_existentes
)

# ======================================================
# SINCRONIZAÇÃO SHOPIFY → PLANILHA (SOMENTE PEDIDOS)
# ======================================================
def sincronizar_shopify_com_planilha(
    nome_planilha: str = "Clientes Shopify",
    lote_tamanho: int = 500
) -> dict:
    """
    Fluxo:
    Shopify → Pedidos Shopify (append incremental)

    ⚠️ NÃO mexe em Clientes Shopify
    """

    # ==================================================
    # 1. IDS JÁ EXISTENTES (ANTI-DUPLICAÇÃO)
    # ==================================================
    ids_existentes = ler_ids_existentes(
        planilha=nome_planilha,
        aba="Pedidos Shopify",
        coluna_id="Pedido ID"
    )

    total_novos = 0
    total_processados = 0

    # ==================================================
    # 2. BUSCA SHOPIFY POR LOTES
    # ==================================================
    for lote in puxar_pedidos_pagos_em_lotes(lote_tamanho):

        df_lote = pd.DataFrame(lote)
        total_processados += len(df_lote)

        if df_lote.empty:
            continue

        # 🔒 Normalização de ID
        df_lote["Pedido ID"] = (
            df_lote["Pedido ID"]
            .astype(str)
            .str.replace(".0", "", regex=False)
            .str.strip()
        )

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

    # ==================================================
    # 3. RETORNO
    # ==================================================
    return {
        "status": "success",
        "mensagem": (
            "✅ Pedidos sincronizados com sucesso\n"
            f"📦 Pedidos processados: {total_processados}\n"
            f"🆕 Pedidos novos: {total_novos}"
        )
    }
