import requests
import streamlit as st


def puxar_pedidos_pagos():
    shop = st.secrets["shopify"]["shop_name"]
    token = st.secrets["shopify"]["access_token"]
    version = st.secrets["shopify"]["API_VERSION"]

    url = f"https://{shop}/admin/api/{version}/orders.json"
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

    while url:
        r = requests.get(url, headers=headers, params=params)
        r.raise_for_status()

        data = r.json().get("orders", [])
        for o in data:
            pedidos.append({
                "Pedido ID": o["id"],
                "Data de criação": o["created_at"],
                "Customer ID": o["customer"]["id"] if o.get("customer") else "",
                "Cliente": f"{o.get('customer', {}).get('first_name','')} {o.get('customer', {}).get('last_name','')}".strip(),
                "Email": o.get("email"),
                "Valor Total": float(o.get("total_price", 0)),
                "Pedido": o.get("order_number")
            })

        link = r.headers.get("Link")
        if link and 'rel="next"' in link:
            url = link.split(";")[0].strip("<>")
            params = {}
        else:
            url = None

    return pedidos
