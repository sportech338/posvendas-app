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

    total_processados = 0  # tudo que veio da Shopify
    total_novos = 0        # só o que entrou na planilha

    # ==================================================
    # 2. BUSCA SHOPIFY POR LOTES
    # ==================================================
    for lote in puxar_pedidos_pagos_em_lotes(lote_tamanho):

        df_lote = pd.DataFrame(lote)

        # Conta TODOS os pedidos retornados pela Shopify
        total_processados += len(df_lote)

        if df_lote.empty:
            continue

        # ==================================================
        # 🔒 BLINDAGEM DE COLUNAS (EVITA KEYERROR)
        # ==================================================
        for col in ["Cancelled At", "Total Refunded", "Valor Total"]:
            if col not in df_lote.columns:
                if col == "Total Refunded":
                    df_lote[col] = 0
                else:
                    df_lote[col] = None

        # ==================================================
        # ❌ REMOVE CANCELADOS
        # ==================================================
        df_lote = df_lote[df_lote["Cancelled At"].isna()]

        # ==================================================
        # ❌ REMOVE TOTALMENTE REEMBOLSADOS
        # ==================================================
        df_lote = df_lote[
            df_lote["Total Refunded"] < df_lote["Valor Total"]
        ]

        if df_lote.empty:
            continue

        # ==================================================
        # 🔒 NORMALIZAÇÃO DE ID
        # ==================================================
        df_lote["Pedido ID"] = (
            df_lote["Pedido ID"]
            .astype(str)
            .str.replace(".0", "", regex=False)
            .str.strip()
        )

        # ==================================================
        # ❌ REMOVE DUPLICADOS JÁ NA PLANILHA
        # ==================================================
        df_lote = df_lote[
            ~df_lote["Pedido ID"].isin(ids_existentes)
        ]

        if df_lote.empty:
            continue

        # ==================================================
        # ✅ APPEND NA ABA "Pedidos Shopify"
        # ==================================================
        append_aba(
            planilha=nome_planilha,
            aba="Pedidos Shopify",
            df=df_lote
        )

        ids_existentes.update(df_lote["Pedido ID"].tolist())
        total_novos += len(df_lote)

    # ==================================================
    # 3. RETORNO FINAL
    # ==================================================
    return {
        "status": "success",
        "mensagem": (
            "✅ Pedidos sincronizados com sucesso\n"
            f"📦 Pedidos processados (Shopify): {total_processados}\n"
            f"🆕 Pedidos novos adicionados: {total_novos}"
        )
    }
