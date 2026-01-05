# utils/shopify.py

import requests
import streamlit as st
import time


def puxar_pedidos_pagos_em_lotes(
    lote_tamanho: int = 500,
    data_inicio: str = "2023-01-01T00:00:00-03:00"
):
    """
    Busca TODOS os pedidos pagos da Shopify a partir de uma data
    e retorna os dados em lotes (ex: 500 em 500).

    🔒 IMPORTANTE:
    - Datas retornadas são ISO 8601 (Shopify padrão)
    - Timezone é preservado
    - NÃO converte datas
    - NÃO formata para pt-BR

    Exemplo:
    2025-09-13T09:22:08-03:00

    A conversão é responsabilidade da camada de visualização.
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
        "order": "created_at desc"  # mais novos primeiro
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

        # =========================
        # RATE LIMIT SHOPIFY
        # =========================
        if response.status_code == 429:
            time.sleep(2)
            continue

        response.raise_for_status()

        orders = response.json().get("orders", [])

        if not orders:
            break

        for o in orders:
            customer = o.get("customer") or {}

            buffer.append({
                "Pedido ID": str(o.get("id")),
                "Data de criação": o.get("created_at"),  # ISO 8601
                "Customer ID": str(customer.get("id", "")),
                "Cliente": (
                    f"{customer.get('first_name', '')} "
                    f"{customer.get('last_name', '')}"
                ).strip() or "SEM NOME",
                "Email": o.get("email"),
                "Valor Total": float(o.get("total_price", 0)),
                "Pedido": o.get("order_number"),
                "Financial Status": o.get("financial_status"),
                "Cancelled At": o.get("cancelled_at"),
                "Total Refunded": float(o.get("total_refunded", 0))
            })

            # 🔹 Entrega lote
            if len(buffer) >= lote_tamanho:
                yield buffer
                buffer = []

        # =========================
        # PAGINAÇÃO SHOPIFY
        # =========================
        link = response.headers.get("Link")
        next_url = None

        if link:
            for parte in link.split(","):
                if 'rel="next"' in parte:
                    next_url = (
                        parte
                        .split(";")[0]
                        .replace("<", "")
                        .replace(">", "")
                        .strip()
                    )

        url = next_url
        params = {}  # params só na primeira request

    # =========================
    # ÚLTIMO LOTE
    # =========================
    if buffer:
        yield buffer
