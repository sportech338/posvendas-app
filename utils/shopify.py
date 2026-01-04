# utils/shopify.py
import requests
import streamlit as st


def puxar_pedidos_pagos_shopify():
    """
    Retorna TODOS os pedidos pagos da Shopify
    """
    shop_name = st.secrets["shopify"]["shop_name"]
    token = st.secrets["shopify"]["access_token"]
    api_version = st.secrets["shopify"]["API_VERSION"]

    base_url = f"https://{shop_name}/admin/api/{api_version}/orders.json"

    headers = {
        "X-Shopify-Access-Token": token,
        "Content-Type": "application/json"
    }

    params = {
        "financial_status": "paid",
        "status": "any",
        "limit": 250
    }

    pedidos = []
    url = base_url

    while url:
        resp = requests.get(url, headers=headers, params=params)
        resp.raise_for_status()

        data = resp.json().get("orders", [])

        for order in data:
            pedidos.append({
                "pedido_id": order.get("id"),
                "data_criacao": order.get("created_at"),
                "customer_id": order.get("customer", {}).get("id"),
                "cliente": (
                    f"{order.get('customer', {}).get('first_name', '')} "
                    f"{order.get('customer', {}).get('last_name', '')}"
                ).strip() or "SEM NOME",
                "email": order.get("email"),
                "valor_total": float(order.get("total_price", 0)),
                "pedido": order.get("order_number")
            })

        # PAGINAÇÃO
        link = resp.headers.get("Link")
        if link and 'rel="next"' in link:
            url = link.split(";")[0].strip("<>")
            params = {}  # params só na primeira chamada
        else:
            url = None

    return pedidos
