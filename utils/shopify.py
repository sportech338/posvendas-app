# utils/shopify.py

import requests
import streamlit as st
import time
import hmac
import hashlib
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Generator, Dict, List, Optional

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
# BUSCAR PEDIDOS PAGOS DIRETO (COM CACHE) - RECOMENDADO
# ======================================================
@st.cache_data(ttl=300)  # Cache de 5 minutos
def buscar_pedidos_pagos_direto(start_date=None, end_date=None, limit=250):
    """
    Busca pedidos PAGOS diretamente da Shopify com CACHE.
    Atualiza automaticamente a cada 5 minutos.
    
    IGUAL ao seu código de logística! 🎯
    
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


# ======================================================
# BUSCAR PEDIDOS PAGOS EM LOTES (para sincronização manual)
# ======================================================
def puxar_pedidos_pagos_em_lotes(
    lote_tamanho: int = 500,
    data_inicio: str = "2023-01-01T00:00:00-03:00"
) -> Generator[List[Dict], None, None]:
    """
    Busca TODOS os pedidos pagos da Shopify a partir de uma data
    e retorna os dados em lotes (ex: 500 em 500).

    Parâmetros:
    - lote_tamanho: Quantidade de pedidos por lote (padrão: 500)
    - data_inicio: Data mínima no formato ISO 8601 (padrão: 01/01/2023)

    🔒 IMPORTANTE:
    - Datas retornadas são ISO 8601 (Shopify padrão)
    - Timezone é preservado da Shopify
    - NÃO converte datas
    - NÃO formata valores para pt-BR
    
    Yields:
    Lista de dicionários com pedidos (lotes de até `lote_tamanho` pedidos)
    
    Exemplo de uso:
    >>> for lote in puxar_pedidos_pagos_em_lotes(lote_tamanho=100):
    >>>     df = pd.DataFrame(lote)
    >>>     processar(df)
    """
    try:
        shop = st.secrets["shopify"]["shop_name"]
        token = st.secrets["shopify"]["access_token"]
        version = st.secrets["shopify"]["API_VERSION"]
    except KeyError as e:
        raise ValueError(
            f"❌ Configuração Shopify ausente: {e}\n"
            "Verifique se st.secrets contém 'shopify.shop_name', "
            "'shopify.access_token' e 'shopify.API_VERSION'"
        )

    base_url = f"https://{shop}/admin/api/{version}/orders.json"

    headers = {
        "X-Shopify-Access-Token": token,
        "Content-Type": "application/json"
    }

    params = {
        "financial_status": "paid",
        "status": "any",
        "limit": 250,
        "created_at_min": data_inicio,
        "order": "created_at desc"
    }

    buffer = []
    url = base_url
    total_pedidos = 0

    while url:
        try:
            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=30
            )

            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 2))
                time.sleep(retry_after)
                continue

            if response.status_code != 200:
                raise requests.HTTPError(
                    f"Shopify API retornou status {response.status_code}: "
                    f"{response.text}"
                )

            response.raise_for_status()

        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"❌ Erro ao conectar com Shopify API: {str(e)}")

        orders = response.json().get("orders", [])

        if not orders:
            break

        for o in orders:
            customer = o.get("customer") or {}
            shipping = o.get("shipping_address") or {}

            pedido = {
                "Pedido ID": str(o.get("id", "")),
                "Data de criação": o.get("created_at"),
                "Customer ID": str(customer.get("id", "")),
                "Cliente": _extrair_nome_cliente(customer, shipping),
                "Email": o.get("email") or "",
                "Valor Total": float(o.get("total_price", 0)),
                "Pedido": o.get("order_number"),
                "Financial Status": o.get("financial_status"),
                "Cancelled At": o.get("cancelled_at"),
                "Total Refunded": float(o.get("total_refunded", 0))
            }

            buffer.append(pedido)
            total_pedidos += 1

            if len(buffer) >= lote_tamanho:
                yield buffer
                buffer = []

        url = _extrair_proxima_pagina(response.headers.get("Link"))
        params = {}

    if buffer:
        yield buffer


# ======================================================
# BUSCAR PEDIDO INDIVIDUAL (PARA WEBHOOK)
# ======================================================
def buscar_pedido_por_id(pedido_id: str) -> Optional[Dict]:
    """
    Busca um pedido específico pelo ID na Shopify.
    Útil para validar dados recebidos via webhook.
    
    Args:
        pedido_id: ID do pedido (string ou int)
    
    Returns:
        Dicionário com dados do pedido ou None se não encontrado
    """
    try:
        shop = st.secrets["shopify"]["shop_name"]
        token = st.secrets["shopify"]["access_token"]
        version = st.secrets["shopify"]["API_VERSION"]
    except KeyError as e:
        raise ValueError(f"❌ Configuração Shopify ausente: {e}")
    
    url = f"https://{shop}/admin/api/{version}/orders/{pedido_id}.json"
    
    headers = {
        "X-Shopify-Access-Token": token,
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 404:
            return None
        
        response.raise_for_status()
        
        order = response.json().get("order", {})
        
        if not order:
            return None
        
        customer = order.get("customer") or {}
        shipping = order.get("shipping_address") or {}
        
        return {
            "Pedido ID": str(order.get("id", "")),
            "Data de criação": order.get("created_at"),
            "Customer ID": str(customer.get("id", "")),
            "Cliente": _extrair_nome_cliente(customer, shipping),
            "Email": order.get("email") or "",
            "Valor Total": float(order.get("total_price", 0)),
            "Pedido": order.get("order_number"),
            "Financial Status": order.get("financial_status"),
            "Cancelled At": order.get("cancelled_at"),
            "Total Refunded": float(order.get("total_refunded", 0))
        }
        
    except requests.exceptions.RequestException as e:
        raise ConnectionError(f"❌ Erro ao buscar pedido: {str(e)}")


# ======================================================
# VALIDAR WEBHOOK DA SHOPIFY
# ======================================================
def validar_webhook_shopify(data: bytes, hmac_header: str, secret: str) -> bool:
    """Valida se um webhook veio realmente da Shopify usando HMAC SHA256."""
    if not secret:
        print("⚠️ SHOPIFY_WEBHOOK_SECRET não configurado!")
        return False
    
    hash_calculado = hmac.new(
        secret.encode('utf-8'),
        data,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(hash_calculado, hmac_header)


# ======================================================
# CRIAR WEBHOOK NA SHOPIFY (PROGRAMÁTICO)
# ======================================================
def criar_webhook(topico: str, url_callback: str) -> Optional[Dict]:
    """Cria um webhook na Shopify programaticamente."""
    try:
        shop = st.secrets["shopify"]["shop_name"]
        token = st.secrets["shopify"]["access_token"]
        version = st.secrets["shopify"]["API_VERSION"]
    except KeyError as e:
        raise ValueError(f"❌ Configuração Shopify ausente: {e}")
    
    url = f"https://{shop}/admin/api/{version}/webhooks.json"
    
    headers = {
        "X-Shopify-Access-Token": token,
        "Content-Type": "application/json"
    }
    
    payload = {
        "webhook": {
            "topic": topico,
            "address": url_callback,
            "format": "json"
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        
        webhook = response.json().get("webhook", {})
        
        print(f"✅ Webhook criado com sucesso!")
        print(f"   • ID: {webhook.get('id')}")
        print(f"   • Tópico: {webhook.get('topic')}")
        print(f"   • URL: {webhook.get('address')}")
        
        return webhook
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Erro ao criar webhook: {str(e)}")
        return None


# ======================================================
# LISTAR WEBHOOKS EXISTENTES
# ======================================================
def listar_webhooks() -> List[Dict]:
    """Lista todos os webhooks configurados na Shopify."""
    try:
        shop = st.secrets["shopify"]["shop_name"]
        token = st.secrets["shopify"]["access_token"]
        version = st.secrets["shopify"]["API_VERSION"]
    except KeyError as e:
        raise ValueError(f"❌ Configuração Shopify ausente: {e}")
    
    url = f"https://{shop}/admin/api/{version}/webhooks.json"
    
    headers = {
        "X-Shopify-Access-Token": token,
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json().get("webhooks", [])
    except requests.exceptions.RequestException as e:
        print(f"❌ Erro ao listar webhooks: {str(e)}")
        return []


# ======================================================
# DELETAR WEBHOOK
# ======================================================
def deletar_webhook(webhook_id: int) -> bool:
    """Deleta um webhook específico da Shopify."""
    try:
        shop = st.secrets["shopify"]["shop_name"]
        token = st.secrets["shopify"]["access_token"]
        version = st.secrets["shopify"]["API_VERSION"]
    except KeyError as e:
        raise ValueError(f"❌ Configuração Shopify ausente: {e}")
    
    url = f"https://{shop}/admin/api/{version}/webhooks/{webhook_id}.json"
    
    headers = {
        "X-Shopify-Access-Token": token,
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.delete(url, headers=headers, timeout=10)
        response.raise_for_status()
        print(f"✅ Webhook {webhook_id} deletado com sucesso!")
        return True
    except requests.exceptions.RequestException as e:
        print(f"❌ Erro ao deletar webhook: {str(e)}")
        return False


# ======================================================
# CONTAR PEDIDOS (SEM BAIXAR TODOS)
# ======================================================
def contar_pedidos_pagos(data_inicio: str = "2023-01-01T00:00:00-03:00") -> int:
    """Conta quantos pedidos pagos existem SEM baixar todos os dados."""
    try:
        shop = st.secrets["shopify"]["shop_name"]
        token = st.secrets["shopify"]["access_token"]
        version = st.secrets["shopify"]["API_VERSION"]
    except KeyError as e:
        raise ValueError(f"❌ Configuração Shopify ausente: {e}")
    
    url = f"https://{shop}/admin/api/{version}/orders/count.json"
    
    headers = {
        "X-Shopify-Access-Token": token,
        "Content-Type": "application/json"
    }
    
    params = {
        "financial_status": "paid",
        "status": "any",
        "created_at_min": data_inicio
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        return response.json().get("count", 0)
    except requests.exceptions.RequestException as e:
        raise ConnectionError(f"❌ Erro ao contar pedidos: {str(e)}")


# ======================================================
# FUNÇÕES AUXILIARES
# ======================================================
def _extrair_nome_cliente(customer: dict, shipping: dict = None) -> str:
    """Extrai nome do cliente com fallback."""
    first = (customer.get("first_name") or "").strip()
    last = (customer.get("last_name") or "").strip()

    if not first and shipping:
        first = (shipping.get("first_name") or "").strip()
        last = (shipping.get("last_name") or "").strip()

    nome_completo = f"{first} {last}".strip()
    return nome_completo if nome_completo else "SEM NOME"


def _extrair_proxima_pagina(link_header: str) -> str:
    """Extrai URL da próxima página do header Link da Shopify."""
    if not link_header:
        return None
    
    for parte in link_header.split(","):
        if 'rel="next"' in parte:
            url = (
                parte
                .split(";")[0]
                .replace("<", "")
                .replace(">", "")
                .strip()
            )
            return url
    
    return None
