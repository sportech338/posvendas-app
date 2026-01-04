# utils/shopify.py

import requests
import streamlit as st


def puxar_pedidos_pagos_em_lotes(lote_tamanho: int = 500):
    """
    Generator que busca pedidos pagos da Shopify
    e retorna os dados em lotes (ex: 500 em 500)
    """

    shop = st.secrets["shopify"]["shop_name"]
    token = st.secrets["shopify"]["access_token"]
    version = st.secrets["shopify"]["API_VERSION"]

    base_url = f"https://{shop}/admin/api/{version}/orders.json"

    headers = {
        "X-Shopify-Access-Token": token,
        "Content-Type": "application/json"
    }

    params = {
        "financial_status": "paid",
        "status": "any",
        "limit": 250  # limite máximo da Shopify por request
    }

    buffer = []
    url = base_url

    while url:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()

        orders = response.json().get("orders", [])

        for o in orders:
            buffer.append({
                "Pedido ID": o["id"],
                "Data de criação": o["created_at"],
                "Customer ID": o["customer"]["id"] if o.get("customer") else "",
                "Cliente": (
                    f"{o.get('customer', {}).get('first_name', '')} "
                    f"{o.get('customer', {}).get('last_name', '')}"
                ).strip() or "SEM NOME",
                "Email": o.get("email"),
                "Valor Total": float(o.get("total_price", 0)),
                "Pedido": o.get("order_number")
            })

            # 🔹 Quando atingir o tamanho do lote, entrega
            if len(buffer) >= lote_tamanho:
                yield buffer
                buffer = []

        # 🔁 Paginação Shopify
        link = response.headers.get("Link")
        if link and 'rel="next"' in link:
            url = link.split(";")[0].strip("<>")
            params = {}  # params só na primeira chamada
        else:
            url = None

    # 🔚 Último lote (se sobrar algo)
    if buffer:
        yield buffer
