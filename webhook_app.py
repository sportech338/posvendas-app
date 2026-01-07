from fastapi import FastAPI, Request
import json
import pandas as pd
import logging
import traceback

from utils.shopify import buscar_pedido_por_id
from utils.sheets import append_aba, ler_ids_existentes
from utils.sync import COLUNAS_PEDIDOS, _reagregar_clientes

# ======================================================
# LOGGING (Render-friendly)
# ======================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger("shopify-webhook")

# ======================================================
# APP
# ======================================================
app = FastAPI()
PLANILHA = "Clientes Shopify"


@app.post("/webhooks/orders/paid")
async def webhook_orders_paid(request: Request):
    logger.info("🚀 Webhook /orders/paid recebido")

    try:
        # ==================================================
        # 1️⃣ Ler payload
        # ==================================================
        raw_body = await request.body()
        logger.info(f"📦 Raw payload: {raw_body[:500]}")

        payload = json.loads(raw_body)
        pedido_id = str(payload.get("id"))

        logger.info(f"🆔 Pedido ID: {pedido_id}")

        if not pedido_id:
            logger.warning("⚠️ Pedido sem ID — ignorado")
            return {"status": "ignored"}

        # ==================================================
        # 2️⃣ Deduplicação
        # ==================================================
        ids_existentes = ler_ids_existentes(
            PLANILHA,
            "Pedidos Shopify",
            "Pedido ID"
        )

        logger.info(f"📊 IDs existentes: {len(ids_existentes)}")

        if pedido_id in ids_existentes:
            logger.warning(f"🔁 Pedido {pedido_id} duplicado")
            return {"status": "duplicate"}

        # ==================================================
        # 3️⃣ Buscar pedido completo
        # ==================================================
        logger.info(f"🔎 Buscando pedido {pedido_id} na Shopify")

        pedido = buscar_pedido_por_id(pedido_id)

        if not pedido:
            logger.error(f"❌ Pedido {pedido_id} não encontrado na Shopify")
            return {"status": "not_found"}

        logger.info("✅ Pedido encontrado")

        # ==================================================
        # 4️⃣ Normalizar e salvar pedido
        # ==================================================
        linha = {k: pedido.get(k, "") for k in COLUNAS_PEDIDOS}
        logger.info(f"🧾 Linha normalizada: {linha}")

        append_aba(
            planilha=PLANILHA,
            aba="Pedidos Shopify",
            df=pd.DataFrame([linha])
        )

        logger.info(f"💾 Pedido {pedido_id} salvo na planilha")

        # ==================================================
        # 5️⃣ 🔄 Reagregar clientes automaticamente
        # ==================================================
        try:
            logger.info("🔄 Reagregando clientes via webhook")

            _reagregar_clientes(
                nome_planilha=PLANILHA,
                resultado_pedidos={
                    "status": "success",
                    "mensagem": "Webhook — novo pedido",
                    "total_novos": 1
                }
            )

            logger.info("👥 Clientes reagregados com sucesso")

        except Exception as e:
            # ⚠️ Nunca derrubar webhook por erro de agregação
            logger.error("⚠️ Erro ao reagregar clientes (não crítico)")
            logger.error(str(e))
            logger.error(traceback.format_exc())

        return {"status": "ok"}

    except Exception as e:
        logger.error("🔥 ERRO FATAL NO WEBHOOK")
        logger.error(str(e))
        logger.error(traceback.format_exc())
        return {"status": "error"}
