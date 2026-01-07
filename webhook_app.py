# webhook_app.py

from fastapi import FastAPI, Request
import json
import pandas as pd

from utils.shopify import buscar_pedido_por_id
from utils.sheets import append_aba, ler_ids_existentes
from utils.sync import COLUNAS_PEDIDOS

app = FastAPI()

PLANILHA = "Clientes Shopify"


@app.post("/webhooks/orders/paid")
async def webhook_orders_paid(request: Request):
    raw_body = await request.body()
    payload = json.loads(raw_body)

    pedido_id = str(payload.get("id"))

    if not pedido_id:
        return {"status": "ignored"}

    # 🔁 Evitar duplicação
    ids_existentes = ler_ids_existentes(
        PLANILHA,
        "Pedidos Shopify",
        "Pedido ID"
    )

    if pedido_id in ids_existentes:
        return {"status": "duplicate"}

    # 🔎 Buscar pedido completo na Shopify
    pedido = buscar_pedido_por_id(pedido_id)

    if not pedido:
        return {"status": "not_found"}

    # 🧾 Normalizar no contrato da aba
    linha = {k: pedido.get(k, "") for k in COLUNAS_PEDIDOS}

    append_aba(
        planilha=PLANILHA,
        aba="Pedidos Shopify",
        df=pd.DataFrame([linha])
    )

    return {"status": "ok"}
