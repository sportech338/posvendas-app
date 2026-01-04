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
    - NÃO perde pedidos guest
    - Valores financeiros corretos
    """
    if df_pedidos.empty:
        return pd.DataFrame()

    df = df_pedidos.copy()

    # -------------------------------
    # Datas
    # -------------------------------
    df["Data de criação"] = pd.to_datetime(
        df["Data de criação"],
        errors="coerce"
    )

    # -------------------------------
    # Normalização de valores (CRÍTICO)
    # -------------------------------
    df["Valor Total"] = (
        df["Valor Total"]
        .astype(str)
        .str.replace("R$", "", regex=False)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
        .astype(float)
        .fillna(0)
    )

    # -------------------------------
    # Chave única de cliente
    # Customer ID se existir, senão Email
    # -------------------------------
    df["Cliente_Key"] = df["Customer ID"].astype(str).str.strip()
    df.loc[df["Cliente_Key"] == "", "Cliente_Key"] = df["Email"]

    # -------------------------------
    # Agrupamento final
    # -------------------------------
    clientes = (
        df
        .groupby("Cliente_Key", as_index=False)
        .agg(
            Cliente=("Cliente", "first"),
            Email=("Email", "first"),
            Qtd_Pedidos=("Pedido ID", "count"),
            Valor_Total_Gasto=("Valor Total", "sum"),
            Primeira_Compra=("Data de criação", "min"),
            Ultima_Compra=("Data de criação", "max"),
        )
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
           → Clientes Shopify (recalculado / sobrescrito)
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
    # 3. NENHUM PEDIDO NOVO
    # ==================================================
    if total_novos == 0:
        return {
            "status": "success",
            "mensagem": (
                "Nenhum pedido novo encontrado.\n"
                f"📦 Pedidos processados: {total_processados}"
            )
        }

    # ==================================================
    # 4. REGERAR CLIENTES (BASE DERIVADA)
    # ==================================================
    df_pedidos = ler_aba(nome_planilha, "Pedidos Shopify")
    df_clientes = gerar_clientes(df_pedidos)

    escrever_aba(
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
            "✅ Sincronização concluída com sucesso\n"
            f"📦 Pedidos processados: {total_processados}\n"
            f"🆕 Pedidos novos: {total_novos}\n"
            f"👥 Clientes atualizados: {len(df_clientes)}"
        )
    }
