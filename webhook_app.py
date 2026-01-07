# webhook_app.py

from fastapi import FastAPI, Request, Header, HTTPException
import json
import os
import pandas as pd

from utils.shopify import (
    validar_webhook_shopify,
    buscar_pedido_por_id
)
from utils.sheets import append_aba, ler_ids_existentes
from utils.sync import COLUNAS_PEDIDOS

app = FastAPI()

# 🔐 SECRET DA SHOPIFY (VEM DO RENDER)
SHOPIFY_SECRET = os.getenv("SHOPIFY_WEBHOOK_SECRET")
if not SHOPIFY_SECRET:
    raise RuntimeError("❌ SHOPIFY_WEBHOOK_SECRET não definido no ambiente")

PLANILHA = "Clientes Shopify"


@app.post("/webhooks/orders/paid")
async def webhook_orders_paid(
    request: Request,
    x_shopify_hmac_sha256: str = Header(None)
):
    raw_body = await request.body()

    # 🔐 Validar assinatura do webhook
    if not validar_webhook_shopify(
        data=raw_body,
        hmac_header=x_shopify_hmac_sha256,
        secret=SHOPIFY_SECRET
    ):
        raise HTTPException(status_code=401, detail="Webhook inválido")

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
