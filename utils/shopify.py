# utils/shopify.py

import requests
from utils.config import get_shopify_config
import time
import hmac
import hashlib
from typing import Generator, Dict, List, Optional


# ======================================================
# BUSCAR PEDIDOS PAGOS EM LOTES
# ======================================================
def puxar_pedidos_pagos_em_lotes(
    lote_tamanho: int = 500,
    data_inicio: str = "2023-01-01T00:00:00-03:00",
    ordem: str = "desc"  # 👈 NOVO (desc = padrão atual)
) -> Generator[List[Dict], None, None]:

    # =========================
    # CONFIG SHOPIFY (secrets)
    # =========================
    cfg = get_shopify_config()
    
    shop = cfg["shop_name"]
    token = cfg["access_token"]
    version = cfg["api_version"]
    
    if not all([shop, token, version]):
        raise ValueError("❌ Variáveis SHOPIFY_* não configuradas")


    base_url = f"https://{shop}/admin/api/{version}/orders.json"

    headers = {
        "X-Shopify-Access-Token": token,
        "Content-Type": "application/json"
    }

    # ⚠️ PARAMS APENAS NA PRIMEIRA REQUEST
    params = {
        "financial_status": "paid",
        "status": "any",
        "limit": 250,
        "created_at_min": data_inicio,
        "order": f"created_at {ordem}"  # 👈 AQUI
    }


    buffer = []
    url = base_url
    total_pedidos = 0

    # =========================
    # LOOP DE PAGINAÇÃO
    # =========================
    while url:
        try:
            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=30
            )

            # =========================
            # RATE LIMIT SHOPIFY (429)
            # =========================
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 2))
                time.sleep(retry_after)
                continue

            # =========================
            # TRATAMENTO DE ERROS HTTP
            # =========================
            if response.status_code != 200:
                raise requests.HTTPError(
                    f"Shopify API retornou status {response.status_code}: "
                    f"{response.text}"
                )

            response.raise_for_status()

        except requests.exceptions.RequestException as e:
            raise ConnectionError(
                f"❌ Erro ao conectar com Shopify API: {str(e)}"
            )

        # =========================
        # PROCESSAR PEDIDOS
        # =========================
        orders = response.json().get("orders", [])

        if not orders:
            break

        for o in orders:
            customer = o.get("customer") or {}
            shipping = o.get("shipping_address") or {}

            # Extrair dados do pedido
            pedido = {
                "Pedido ID": str(o.get("id", "")),
                "Data de criação": o.get("created_at"),  # ISO 8601
                "Customer ID": str(customer.get("id") or o.get("email") or ""),
                "Cliente": _extrair_nome_cliente(customer, shipping),
                "Email": o.get("email") or "",
                "Valor Total": float(o.get("total_price", 0)),
                "Pedido": o.get("order_number"),
    
                # Campos internos
                "Financial Status": o.get("financial_status"),
                "Cancelled At": o.get("cancelled_at"),
                "Total Refunded": float(o.get("total_refunded", 0))
            }

            buffer.append(pedido)
            total_pedidos += 1

            # 🔹 Entrega lote quando atinge o tamanho definido
            if len(buffer) >= lote_tamanho:
                yield buffer
                buffer = []

        # =========================
        # PAGINAÇÃO SHOPIFY (Link header)
        # =========================
        url = _extrair_proxima_pagina(response.headers.get("Link"))
        params = {}  # Params só na primeira request

    # =========================
    # ENTREGAR ÚLTIMO LOTE (se houver)
    # =========================
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
    
    Exemplo:
        >>> pedido = buscar_pedido_por_id("123456789")
        >>> print(pedido["Customer ID"])
    """
    cfg = get_shopify_config()
    
    shop = cfg["shop_name"]
    token = cfg["access_token"]
    version = cfg["api_version"]
    
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
        
        # Formatar pedido no mesmo padrão de puxar_pedidos_pagos_em_lotes
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
    """
    Valida se um webhook veio realmente da Shopify usando HMAC SHA256.
    
    Args:
        data: Corpo da requisição (bytes)
        hmac_header: Header "X-Shopify-Hmac-Sha256" enviado pela Shopify
        secret: Seu Shopify Webhook Secret (configurado no .env)
    
    Returns:
        True se webhook é válido, False caso contrário
    
    Exemplo:
        >>> from flask import request
        >>> if validar_webhook_shopify(request.data, request.headers.get("X-Shopify-Hmac-Sha256"), SECRET):
        >>>     processar_webhook()
    """
    if not secret:
        print("⚠️ SHOPIFY_WEBHOOK_SECRET não configurado!")
        return False
    
    # Calcular hash
    hash_calculado = hmac.new(
        secret.encode('utf-8'),
        data,
        hashlib.sha256
    ).hexdigest()
    
    # Comparar com o hash enviado pela Shopify
    return hmac.compare_digest(hash_calculado, hmac_header)


# ======================================================
# CRIAR WEBHOOK NA SHOPIFY (PROGRAMÁTICO)
# ======================================================
def criar_webhook(topico: str, url_callback: str) -> Optional[Dict]:
    """
    Cria um webhook na Shopify programaticamente.
    
    Args:
        topico: Evento a monitorar (ex: "orders/paid", "orders/create")
        url_callback: URL pública do seu servidor que receberá o webhook
    
    Returns:
        Dados do webhook criado ou None se falhar
    
    Tópicos disponíveis:
    - orders/paid (pedido pago)
    - orders/create (pedido criado)
    - orders/updated (pedido atualizado)
    - orders/cancelled (pedido cancelado)
    
    Exemplo:
        >>> webhook = criar_webhook(
        >>>     topico="orders/paid",
        >>>     url_callback="https://seu-dominio.com/webhooks/orders/paid"
        >>> )
        >>> print(f"Webhook ID: {webhook['id']}")
    """
    cfg = get_shopify_config()
    
    shop = cfg["shop_name"]
    token = cfg["access_token"]
    version = cfg["api_version"]
    
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
    """
    Lista todos os webhooks configurados na Shopify.
    
    Returns:
        Lista de webhooks ativos
    
    Exemplo:
        >>> webhooks = listar_webhooks()
        >>> for w in webhooks:
        >>>     print(f"{w['topic']} → {w['address']}")
    """
    cfg = get_shopify_config()
    
    shop = cfg["shop_name"]
    token = cfg["access_token"]
    version = cfg["api_version"]
    
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
    """
    Deleta um webhook específico da Shopify.
    
    Args:
        webhook_id: ID do webhook a deletar
    
    Returns:
        True se deletado com sucesso, False caso contrário
    
    Exemplo:
        >>> deletar_webhook(123456789)
    """
    cfg = get_shopify_config()
    
    shop = cfg["shop_name"]
    token = cfg["access_token"]
    version = cfg["api_version"]
    
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
# FUNÇÕES AUXILIARES
# ======================================================
def _extrair_nome_cliente(customer: dict, shipping: dict = None) -> str:
    """
    Extrai nome do cliente.
    Prioridade:
    1. customer (perfil)
    2. shipping_address (checkout)
    3. fallback seguro
    """
    first = (customer.get("first_name") or "").strip()
    last = (customer.get("last_name") or "").strip()

    if not first and shipping:
        first = (shipping.get("first_name") or "").strip()
        last = (shipping.get("last_name") or "").strip()

    nome_completo = f"{first} {last}".strip()
    return nome_completo if nome_completo else "SEM NOME"


def _extrair_proxima_pagina(link_header: str) -> str:
    """
    Extrai URL da próxima página do header "Link" da Shopify.
    
    Formato do header:
    <https://shop.myshopify.com/...>; rel="next", <https://...>; rel="previous"
    
    Retorna:
    - URL da próxima página se existir
    - None se não houver mais páginas
    """
    if not link_header:
        return None
    
    # Separar as partes do header
    for parte in link_header.split(","):
        if 'rel="next"' in parte:
            # Extrair URL entre < e >
            url = (
                parte
                .split(";")[0]
                .replace("<", "")
                .replace(">", "")
                .strip()
            )
            return url
    
    return None


# ======================================================
# BUSCAR PEDIDOS DIRETO (SEM LOTES) - OPCIONAL
# ======================================================
def puxar_todos_pedidos_pagos(
    data_inicio: str = "2023-01-01T00:00:00-03:00"
) -> List[Dict]:
    """
    Busca TODOS os pedidos pagos de uma vez (sem lotes).
    
    ⚠️ ATENÇÃO: Use apenas se tiver POUCOS pedidos (< 1000)
    Para lojas com muitos pedidos, use `puxar_pedidos_pagos_em_lotes()`
    
    Retorna:
    Lista completa de pedidos (pode consumir muita memória)
    """
    todos_pedidos = []
    
    for lote in puxar_pedidos_pagos_em_lotes(
        lote_tamanho=500,
        data_inicio=data_inicio
    ):
        todos_pedidos.extend(lote)
    
    return todos_pedidos


# ======================================================
# CONTAR PEDIDOS (SEM BAIXAR TODOS) - ÚTIL PARA DEBUG
# ======================================================
def contar_pedidos_pagos(
    data_inicio: str = "2023-01-01T00:00:00-03:00"
) -> int:
    """
    Conta quantos pedidos pagos existem na Shopify
    SEM baixar todos os dados (mais rápido).
    
    Útil para verificar se há novos pedidos antes de sincronizar.
    """
    cfg = get_shopify_config()
    
    shop = cfg["shop_name"]
    token = cfg["access_token"]
    version = cfg["api_version"]
    
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
