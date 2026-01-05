# utils/shopify.py

import requests
import streamlit as st
import time
from typing import Generator, Dict, List


# ======================================================
# BUSCAR PEDIDOS PAGOS EM LOTES
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
    
    Exemplo de data retornada:
    "2026-01-03T21:50:37-03:00"

    A conversão de datas/valores é responsabilidade da camada de visualização.
    
    Yields:
    Lista de dicionários com pedidos (lotes de até `lote_tamanho` pedidos)
    
    Exemplo de uso:
    >>> for lote in puxar_pedidos_pagos_em_lotes(lote_tamanho=100):
    >>>     df = pd.DataFrame(lote)
    >>>     processar(df)
    """

    # =========================
    # CONFIG SHOPIFY (secrets)
    # =========================
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

    # ⚠️ PARAMS APENAS NA PRIMEIRA REQUEST
    params = {
        "financial_status": "paid",      # Apenas pedidos pagos
        "status": "any",                 # Qualquer status (aberto/fechado)
        "limit": 250,                    # Máximo permitido pela Shopify API
        "created_at_min": data_inicio,   # Data mínima de criação
        "order": "created_at desc"       # Mais novos primeiro
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

            # Extrair dados do pedido
            pedido = {
                "Pedido ID": str(o.get("id", "")),
                "Data de criação": o.get("created_at"),  # ISO 8601
                "Customer ID": str(customer.get("id", "")),
                "Cliente": _extrair_nome_cliente(customer),
                "Email": o.get("email", ""),
                "Valor Total": float(o.get("total_price", 0)),
                "Pedido": o.get("order_number"),
                
                # Campos internos (usados para filtrar cancelados/reembolsados)
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
# FUNÇÕES AUXILIARES
# ======================================================
def _extrair_nome_cliente(customer: dict) -> str:
    """
    Extrai nome completo do cliente a partir do objeto customer.
    Se não houver nome, retorna "SEM NOME".
    """
    first = customer.get("first_name", "").strip()
    last = customer.get("last_name", "").strip()
    
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
