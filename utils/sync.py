# utils/sync.py

import pandas as pd

from utils.shopify import puxar_pedidos_pagos_em_lotes
from utils.sheets import (
    append_aba,
    ler_ids_existentes
)

# ======================================================
# SINCRONIZAÇÃO SHOPIFY → PLANILHA
# ======================================================
def sincronizar_shopify_com_planilha(
    nome_planilha: str = "Clientes Shopify",
    lote_tamanho: int = 500
) -> dict:
    """
    Fluxo:
    Shopify →
      → Pedidos Shopify (válidos)
      → Pedidos Ignorados (cancelados / reembolsados)

    ⚠️ NÃO mexe em Clientes Shopify
    """

    # ==================================================
    # IDS JÁ EXISTENTES
    # ==================================================
    ids_pedidos = ler_ids_existentes(
        planilha=nome_planilha,
        aba="Pedidos Shopify",
        coluna_id="Pedido ID"
    )

    ids_ignorados = ler_ids_existentes(
        planilha=nome_planilha,
        aba="Pedidos Ignorados",
        coluna_id="Pedido ID"
    )

    total_processados = 0
    total_novos = 0
    total_ignorados = 0

    # ==================================================
    # BUSCA SHOPIFY
    # ==================================================
    for lote in puxar_pedidos_pagos_em_lotes(lote_tamanho):

        df = pd.DataFrame(lote)
        total_processados += len(df)

        if df.empty:
            continue

        # 🔒 Normalização de ID
        df["Pedido ID"] = (
            df["Pedido ID"]
            .astype(str)
            .str.replace(".0", "", regex=False)
            .str.strip()
        )

        # ==================================================
        # IDENTIFICA CANCELADOS / REEMBOLSADOS
        # ==================================================
        df_cancelados = df[
            (df["Cancelled At"].notna()) |
            (df["Total Refunded"] >= df["Valor Total"])
        ].copy()

        if not df_cancelados.empty:
            df_cancelados["Motivo"] = df_cancelados.apply(
                lambda r: "CANCELADO"
                if pd.notna(r["Cancelled At"])
                else "REEMBOLSADO",
                axis=1
            )

            df_cancelados_final = df_cancelados[
                ["Pedido ID", "Data de criação", "Financial Status", "Cancelled At", "Motivo"]
            ].rename(columns={
                "Financial Status": "Status",
                "Cancelled At": "Data de cancelamento"
            })

            df_cancelados_final = df_cancelados_final[
                ~df_cancelados_final["Pedido ID"].isin(ids_ignorados)
            ]

            if not df_cancelados_final.empty:
                append_aba(
                    planilha=nome_planilha,
                    aba="Pedidos Ignorados",
                    df=df_cancelados_final
                )

                ids_ignorados.update(df_cancelados_final["Pedido ID"].tolist())
                total_ignorados += len(df_cancelados_final)

        # ==================================================
        # PEDIDOS VÁLIDOS (NÃO CANCELADOS)
        # ==================================================
        df_validos = df[
            (df["Cancelled At"].isna()) &
            (df["Total Refunded"] < df["Valor Total"])
        ]

        df_validos = df_validos[
            ~df_validos["Pedido ID"].isin(ids_pedidos)
        ]

        if df_validos.empty:
            continue

        # ❌ REMOVE COLUNAS INTERNAS
        df_validos_final = df_validos.drop(
            columns=["Cancelled At", "Total Refunded", "Financial Status"],
            errors="ignore"
        )

        append_aba(
            planilha=nome_planilha,
            aba="Pedidos Shopify",
            df=df_validos_final
        )

        ids_pedidos.update(df_validos_final["Pedido ID"].tolist())
        total_novos += len(df_validos_final)

    # ==================================================
    # RETORNO
    # ==================================================
    return {
        "status": "success",
        "mensagem": (
            "✅ Sincronização concluída\n\n"
            f"📦 Pedidos processados: {total_processados}\n"
            f"🆕 Pedidos válidos adicionados: {total_novos}\n"
            f"🚫 Pedidos ignorados: {total_ignorados}"
        )
    }
