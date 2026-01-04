from utils.shopify import puxar_pedidos_pagos_shopify
from utils.sheets import garantir_aba_com_cabecalho, ler_coluna, append_rows
from dateutil import parser as dateparser

PEDIDOS_HEADERS = [
    "Pedido ID",
    "Data de criação",
    "Customer ID",
    "Cliente",
    "Email",
    "Valor Total",
    "Pedido",
]

def sync_pedidos_shopify_para_planilha(nome_planilha: str):
    """
    1) Puxa pedidos pagos da Shopify
    2) Grava APENAS os novos na aba 'Pedidos Shopify' (dedup por Pedido ID)
    """
    garantir_aba_com_cabecalho(nome_planilha, "Pedidos Shopify", PEDIDOS_HEADERS)

    # ids existentes (coluna 1 = Pedido ID)
    existentes = set(str(x).strip() for x in ler_coluna(nome_planilha, "Pedidos Shopify", 1) if x)

    pedidos = puxar_pedidos_pagos_shopify()

    novos_rows = []
    for p in pedidos:
        pid = str(p.get("pedido_id", "")).strip()
        if not pid or pid in existentes:
            continue

        created_at = p.get("data_criacao") or ""
        # deixa em formato legível (opcional)
        try:
            created_at = dateparser.parse(created_at).strftime("%d/%m/%Y %H:%M:%S")
        except Exception:
            pass

        novos_rows.append([
            pid,
            created_at,
            str(p.get("customer_id") or "").strip(),
            p.get("cliente") or "SEM NOME",
            p.get("email") or "",
            float(p.get("valor_total") or 0),
            str(p.get("pedido") or "").strip(),
        ])
        existentes.add(pid)

    append_rows(nome_planilha, "Pedidos Shopify", novos_rows)

    return {
        "total_shopify": len(pedidos),
        "novos_inseridos": len(novos_rows),
    }
