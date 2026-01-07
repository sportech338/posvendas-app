from fastapi import FastAPI, Request
import json
import pandas as pd

from utils.shopify import buscar_pedido_por_id
from utils.sheets import append_aba, ler_ids_existentes
from utils.sync import COLUNAS_PEDIDOS, _reagregar_clientes

app = FastAPI()

PLANILHA = "Clientes Shopify"


@app.post("/webhooks/orders/paid")
async def webhook_orders_paid(request: Request):
    # ======================================================
    # 1️⃣ Ler payload do webhook
    # ======================================================
    raw_body = await request.body()
    payload = json.loads(raw_body)

    pedido_id = str(payload.get("id"))

    if not pedido_id:
        return {"status": "ignored"}

    # ======================================================
    # 2️⃣ Evitar duplicação de pedidos
    # ======================================================
    ids_existentes = ler_ids_existentes(
        PLANILHA,
        "Pedidos Shopify",
        "Pedido ID"
    )

    if pedido_id in ids_existentes:
        return {"status": "duplicate"}

    # ======================================================
    # 3️⃣ Buscar pedido completo na Shopify
    # ======================================================
    pedido = buscar_pedido_por_id(pedido_id)

    if not pedido:
        return {"status": "not_found"}

    # ======================================================
    # 4️⃣ Normalizar pedido no contrato da aba
    # ======================================================
    linha = {k: pedido.get(k, "") for k in COLUNAS_PEDIDOS}

    append_aba(
        planilha=PLANILHA,
        aba="Pedidos Shopify",
        df=pd.DataFrame([linha])
    )

    # ======================================================
    # 5️⃣ 🔄 REAGREGAR CLIENTES AUTOMATICAMENTE
    # ======================================================
    try:
        _reagregar_clientes(
            nome_planilha=PLANILHA,
            resultado_pedidos={
                "status": "success",
                "mensagem": "Webhook — novo pedido",
                "total_novos": 1
            }
        )
    except Exception as e:
        # ⚠️ Nunca quebrar o webhook por erro de agregação
        print(f"⚠️ Erro ao atualizar clientes via webhook: {e}")

    return {"status": "ok"}
