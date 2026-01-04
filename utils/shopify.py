# utils/shopify.py

import requests
import streamlit as st


def puxar_pedidos_pagos_em_lotes(
    lote_tamanho: int = 500,
    data_inicio: str = "2023-01-01T00:00:00-03:00"
):
    """
    Busca TODOS os pedidos pagos da Shopify a partir de uma data
    e retorna os dados em lotes (ex: 500 em 500).

    - Usa paginação oficial da Shopify (Link header)
    - Para automaticamente quando não houver mais pedidos
    """

    # =========================
    # CONFIG SHOPIFY
    # =========================
    shop = st.secrets["shopify"]["shop_name"]
    token = st.secrets["shopify"]["access_token"]
    version = st.secrets["shopify"]["API_VERSION"]

    base_url = f"https://{shop}/admin/api/{version}/orders.json"

    headers = {
        "X-Shopify-Access-Token": token,
        "Content-Type": "application/json"
    }

    # ⚠️ PARAMS APENAS NA PRIMEIRA REQUEST
    params = {
        "financial_status": "paid",
        "status": "any",
        "limit": 250,  # máximo permitido pela Shopify
        "created_at_min": data_inicio,
        "order": "created_at asc"  # do mais antigo para o mais novo
    }

    buffer = []
    url = base_url

    # =========================
    # LOOP DE PAGINAÇÃO
    # =========================
    while url:
        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=30
        )
        response.raise_for_status()

        orders = response.json().get("orders", [])

        # Se não vier pedido nenhum, encerra
        if not orders:
            break

        for o in orders:
            buffer.append({
                "Pedido ID": str(o["id"]),
                "Data de criação": o["created_at"],
                "Customer ID": str(o["customer"]["id"]) if o.get("customer") else "",
                "Cliente": (
                    f"{o.get('customer', {}).get('first_name', '')} "
                    f"{o.get('customer', {}).get('last_name', '')}"
                ).strip() or "SEM NOME",
                "Email": o.get("email"),
                "Valor Total": float(o.get("total_price", 0)),
                "Pedido": o.get("order_number")
            })

            # 🔹 Entrega lote completo
            if len(buffer) >= lote_tamanho:
                yield buffer
                buffer = []

        # =========================
        # PAGINAÇÃO SHOPIFY (CORRETA)
        # =========================
        link = response.headers.get("Link")

        next_url = None
        if link:
            partes = link.split(",")
            for parte in partes:
                if 'rel="next"' in parte:
                    next_url = parte.split(";")[0].replace("<", "").replace(">", "").strip()

        url = next_url
        params = {}  # params só na primeira request

    # =========================
    # ÚLTIMO LOTE (RESTO)
    # =========================
    if buffer:
        yield buffer
