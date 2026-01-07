import logging
import pandas as pd
from datetime import timedelta

from utils.sheets import ler_aba
from utils.sync import sincronizar_shopify_com_planilha, _reagregar_clientes

# ======================================================
# LOGGING
# ======================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger("cron-shopify")

# ======================================================
# CONSTANTES
# ======================================================
PLANILHA = "Clientes Shopify"
ABA_PEDIDOS = "Pedidos Shopify"

# ======================================================
# UTIL — DESCOBRIR DATA INICIAL
# ======================================================
def descobrir_data_inicio() -> str:
    """
    Lê a última 'Data de criação' da aba Pedidos Shopify
    e retorna essa data menos 1 minuto (ISO 8601).
    """
    try:
        df = ler_aba(PLANILHA, ABA_PEDIDOS)

        if df.empty or "Data de criação" not in df.columns:
            logger.warning("⚠️ Nenhuma data encontrada, usando fallback inicial")
            return "2023-01-01T00:00:00-03:00"

        df["Data de criação"] = pd.to_datetime(
            df["Data de criação"],
            errors="coerce",
            utc=True
        )

        ultima_data = df["Data de criação"].max()

        if pd.isna(ultima_data):
            logger.warning("⚠️ Data inválida, usando fallback inicial")
            return "2023-01-01T00:00:00-03:00"

        # ⏪ Voltar 1 minuto para evitar perda de pedidos simultâneos
        data_inicio = ultima_data - timedelta(minutes=1)

        data_iso = (
            data_inicio
            .tz_convert("America/Sao_Paulo")
            .strftime("%Y-%m-%dT%H:%M:%S-03:00")
        )

        logger.info(f"🕒 Última data encontrada: {ultima_data}")
        logger.info(f"🔁 Data usada na busca: {data_iso}")

        return data_iso

    except Exception as e:
        logger.error(f"🔥 Erro ao descobrir data inicial: {e}")
        return "2023-01-01T00:00:00-03:00"


# ======================================================
# MAIN
# ======================================================
def main():
    logger.info("🚀 CRON Shopify iniciado")

    data_inicio = descobrir_data_inicio()

    # ==================================================
    # 1️⃣ SINCRONIZAR PEDIDOS (INCREMENTAL POR DATA)
    # ==================================================
    resultado = sincronizar_shopify_com_planilha(
        nome_planilha=PLANILHA,
        lote_tamanho=250,
        data_inicio=data_inicio
    )

    logger.info("📦 Resultado sincronização:")
    for k, v in resultado.items():
        logger.info(f"   {k}: {v}")

    if resultado.get("total_novos", 0) == 0:
        logger.info("⏱️ Nenhum pedido novo encontrado")
        logger.info("✅ Execução finalizada")
        return

    # ==================================================
    # 2️⃣ REAGREGAR CLIENTES
    # ==================================================
    logger.info("🔄 Reagregando clientes")

    resultado_clientes = _reagregar_clientes(
        nome_planilha=PLANILHA,
        resultado_pedidos=resultado
    )

    logger.info("👥 Resultado clientes:")
    for k, v in resultado_clientes.items():
        logger.info(f"   {k}: {v}")

    logger.info("✅ Execução finalizada com sucesso")


# ======================================================
# ENTRYPOINT
# ======================================================
if __name__ == "__main__":
    main()
