# utils/sync.py

import pandas as pd
from utils.shopify import puxar_pedidos_pagos
from utils.sheets import escrever_aba


def gerar_clientes(df_pedidos: pd.DataFrame) -> pd.DataFrame:
    """
    Gera a base de clientes a partir da aba Pedidos Shopify
    """
    if df_pedidos.empty:
        return pd.DataFrame()

    df_pedidos["Data de criação"] = pd.to_datetime(df_pedidos["Data de criação"])

    clientes = (
        df_pedidos
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


def sincronizar_shopify_com_planilha(
    nome_planilha: str = "Clientes Shopify"
) -> dict:
    """
    Orquestrador principal:
    Shopify -> Pedidos Shopify -> Clientes Shopify
    """

    # =========================
    # 1. PUXAR PEDIDOS DA SHOPIFY
    # =========================
    pedidos = puxar_pedidos_pagos()

    if not pedidos:
        return {
            "status": "warning",
            "mensagem": "Nenhum pedido pago encontrado na Shopify."
        }

    df_pedidos = pd.DataFrame(pedidos)

    # =========================
    # 2. SALVAR PEDIDOS NA PLANILHA
    # =========================
    escrever_aba(
        planilha=nome_planilha,
        aba="Pedidos Shopify",
        df=df_pedidos
    )

    # =========================
    # 3. GERAR CLIENTES
    # =========================
    df_clientes = gerar_clientes(df_pedidos)

    if df_clientes.empty:
        return {
            "status": "warning",
            "mensagem": "Pedidos salvos, mas nenhum cliente foi gerado."
        }

    # =========================
    # 4. SALVAR CLIENTES NA PLANILHA
    # =========================
    escrever_aba(
        planilha=nome_planilha,
        aba="Clientes Shopify",
        df=df_clientes
    )

    # =========================
    # 5. RETORNO PARA O STREAMLIT
    # =========================
    return {
        "status": "success",
        "mensagem": f"Sincronização concluída: {len(df_pedidos)} pedidos e {len(df_clientes)} clientes."
    }
