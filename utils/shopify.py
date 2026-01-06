# utils/shopify.py

import requests
import streamlit as st
import time
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo

APP_TZ = ZoneInfo("America/Sao_Paulo")


# ======================================================
# SESSION GLOBAL (otimização de requisições)
# ======================================================
_session = None

def _get_session():
    """Retorna sessão HTTP reutilizável para otimizar requisições."""
    global _session
    if _session is None:
        s = requests.Session()
        s.headers.update({"Accept-Encoding": "gzip, deflate"})
        _session = s
    return _session


# ======================================================
# BUSCAR PEDIDOS PAGOS DIRETO (COM CACHE) - PRINCIPAL
# ======================================================
@st.cache_data(ttl=300)  # Cache de 5 minutos
def buscar_pedidos_pagos_direto(start_date=None, end_date=None, limit=250):
    """
    Busca pedidos PAGOS diretamente da Shopify com CACHE.
    Atualiza automaticamente a cada 5 minutos.
    
    Args:
        start_date: Data inicial (datetime.date) - padrão: 01/01/2023
        end_date: Data final (datetime.date) - padrão: hoje
        limit: Máximo de pedidos por página (máx 250)
    
    Returns:
        pd.DataFrame com pedidos pagos
    
    Exemplo:
        >>> df = buscar_pedidos_pagos_direto()
        >>> print(len(df))  # Mostra quantidade de pedidos
    """
    try:
        shop = st.secrets["shopify"]["shop_name"]
        token = st.secrets["shopify"]["access_token"]
        version = st.secrets["shopify"]["API_VERSION"]
    except KeyError as e:
        raise ValueError(f"❌ Configuração Shopify ausente: {e}")
    
    BASE_URL = f"https://{shop}/admin/api/{version}"
    HEADERS = {
        "X-Shopify-Access-Token": token,
        "Content-Type": "application/json"
    }
    
    # Definir período
    hoje = datetime.now(APP_TZ).date()
    if start_date is None:
        start_date = datetime(2023, 1, 1).date()
    if end_date is None:
        end_date = hoje
    
    start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=APP_TZ)
    end_dt = datetime.combine(end_date, datetime.max.time(), tzinfo=APP_TZ)
    
    start_str = start_dt.strftime("%Y-%m-%dT%H:%M:%S%z")
    end_str = end_dt.strftime("%Y-%m-%dT%H:%M:%S%z")
    
    url = f"{BASE_URL}/orders.json?limit={limit}&status=any&financial_status=paid&created_at_min={start_str}&created_at_max={end_str}"
    
    all_rows = []
    s = _get_session()
    
    while url:
        try:
            r = s.get(url, headers=HEADERS, timeout=60)
            
            # Rate limit
            if r.status_code == 429:
                retry_after = int(r.headers.get("Retry-After", 2))
                time.sleep(retry_after)
                continue
            
            r.raise_for_status()
            
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"❌ Erro ao conectar com Shopify: {str(e)}")
        
        data = r.json()
        orders = data.get("orders", [])
        
        if not orders:
            break
        
        for o in orders:
            customer = o.get("customer") or {}
            shipping = o.get("shipping_address") or {}
            
            nome_cliente = (
                f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip()
                or "SEM NOME"
            )
            
            email_cliente = (
                customer.get("email")
                or o.get("email")
                or o.get("contact_email")
                or "sem-email@exemplo.com"
            )
            
            all_rows.append({
                "Pedido ID": str(o.get("id", "")),
                "Data de criação": o.get("created_at"),
                "Customer ID": str(customer.get("id", "")),
                "Cliente": nome_cliente,
                "Email": email_cliente,
                "Valor Total": float(o.get("total_price", 0)),
                "Pedido": o.get("order_number"),
                "Financial Status": o.get("financial_status"),
                "Cancelled At": o.get("cancelled_at"),
                "Total Refunded": float(o.get("total_refunded", 0))
            })
        
        # Paginação
        url = r.links.get("next", {}).get("url")
    
    return pd.DataFrame(all_rows)
