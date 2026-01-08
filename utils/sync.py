# utils/sync.py

import pandas as pd
from datetime import datetime, timedelta
import pytz

from utils.shopify import puxar_pedidos_pagos_em_lotes
from utils.sheets import (
    append_aba,
    ler_ids_existentes,
    ler_aba,
    escrever_aba
)
from utils.classificacao import agregar_por_cliente, calcular_estado, calcular_ciclo_medio


# ======================================================
# 🔒 CONTRATO FIXO DAS ABAS DE PEDIDOS
# ======================================================
COLUNAS_PEDIDOS = [
    "Pedido ID",
    "Data de criação",
    "Customer ID",
    "Cliente",
    "Email",
    "Valor Total",
    "Pedido"
]


# ======================================================
# UTIL — DATA DE INÍCIO (ONTEM 00:00)
# ======================================================
def _data_inicio_ontem() -> str:
    tz = pytz.timezone("America/Sao_Paulo")
    ontem = datetime.now(tz) - timedelta(days=1)
    return ontem.strftime("%Y-%m-%dT00:00:00-03:00")


# ======================================================
# SINCRONIZAÇÃO COMPLETA (BOTÃO MANUAL)
# ======================================================
def sincronizar_shopify_completo(
    nome_planilha: str = "Clientes Shopify",
    lote_tamanho: int = 500
) -> dict:
    todos_pedidos = []

    # 🔑 PUXAR DO MAIS ANTIGO → MAIS RECENTE
    for lote in puxar_pedidos_pagos_em_lotes(
        lote_tamanho=lote_tamanho,
        data_inicio="2023-01-01T00:00:00-03:00",
        ordem="asc"
    ):
        todos_pedidos.extend(lote)

    if not todos_pedidos:
        return {
            "status": "warning",
            "mensagem": "⚠️ Nenhum pedido encontrado"
        }

    df_pedidos = pd.DataFrame(todos_pedidos)

    # 🔒 CONTRATO FIXO
    df_pedidos = df_pedidos[COLUNAS_PEDIDOS]

    # 1️⃣ Converter para datetime (timezone correto)
    df_pedidos["Data de criação"] = (
        pd.to_datetime(
            df_pedidos["Data de criação"],
            errors="coerce",
            utc=True
        )
        .dt.tz_convert("America/Sao_Paulo")
        .dt.tz_localize(None)
    )

    # 2️⃣ Ordenar corretamente
    df_pedidos = df_pedidos.sort_values("Data de criação")

    # 3️⃣ Só AGORA formatar para string BR
    df_pedidos["Data de criação"] = (
        df_pedidos["Data de criação"]
        .dt.strftime("%d/%m/%Y %H:%M")
    )

    # ✍️ SOBRESCREVER A ABA INTEIRA
    escrever_aba(
        planilha=nome_planilha,
        aba="Pedidos Shopify",
        df=df_pedidos
    )

    # 🔄 REAGREGAR CLIENTES
    return _reagregar_clientes(
        nome_planilha,
        {
            "mensagem": f"📦 Pedidos sincronizados (rebuild): {len(df_pedidos)}"
        }
    )



# ======================================================
# SINCRONIZAÇÃO INCREMENTAL
# ======================================================
def sincronizar_shopify_incremental(
    nome_planilha: str = "Clientes Shopify"
) -> dict:
    data_inicio = _data_inicio_ontem()

    resultado_pedidos = sincronizar_shopify_com_planilha(
        nome_planilha=nome_planilha,
        lote_tamanho=250,
        data_inicio=data_inicio
    )

    if resultado_pedidos["total_novos"] == 0:
        return {
            "status": "noop",
            "mensagem": "⏱️ Nenhum pedido novo nos últimos 2 dias"
        }

    return _reagregar_clientes(nome_planilha, resultado_pedidos)


# ======================================================
# REAGREGAR CLIENTES
# ======================================================
def _reagregar_clientes(nome_planilha: str, resultado_pedidos: dict) -> dict:
    df_pedidos = ler_aba(nome_planilha, "Pedidos Shopify")

    if df_pedidos.empty:
        return {
            "status": "warning",
            "mensagem": "⚠️ Nenhum pedido encontrado para agregação"
        }

    df_pedidos["Data de criação"] = (
        pd.to_datetime(df_pedidos["Data de criação"], errors="coerce", utc=True)
        .dt.tz_convert("America/Sao_Paulo")
        .dt.tz_localize(None)
    )

    df_clientes = agregar_por_cliente(df_pedidos)

    # 📊 Calcular ciclo médio real com base na planilha
    ciclo = calcular_ciclo_medio(df_clientes)

    threshold_risco = ciclo["limite_risco"] or 60
    threshold_dormente = ciclo["limite_dormente"] or 120

    # ✅ CALCULAR ESTADO DINÂMICO (ESTA LINHA É A CHAVE)
    df_clientes = calcular_estado(
        df_clientes,
        threshold_risco=threshold_risco,
        threshold_dormente=threshold_dormente
    )
    
    # ✍️ AGORA SIM escrever clientes COM ESTADO
    escrever_aba(
        planilha=nome_planilha,
        aba="Clientes Shopify",
        df=df_clientes
    )


    return {
        "status": "success",
        "mensagem": (
            f"{resultado_pedidos['mensagem']}\n\n"
            f"👥 Clientes atualizados: {len(df_clientes)}"
        )
    }


# ======================================================
# BASE — SINCRONIZAÇÃO DE PEDIDOS
# ======================================================
def sincronizar_shopify_com_planilha(
    nome_planilha: str,
    lote_tamanho: int,
    data_inicio: str,
    ordem: str = "desc"
) -> dict:


    ids_pedidos = ler_ids_existentes(nome_planilha, "Pedidos Shopify", "Pedido ID")
    ids_ignorados = ler_ids_existentes(nome_planilha, "Pedidos Ignorados", "Pedido ID")

    total_processados = total_novos = total_ignorados = 0

    for lote in puxar_pedidos_pagos_em_lotes(
        lote_tamanho,
        data_inicio,
        ordem=ordem
    ):

        df = pd.DataFrame(lote)
        total_processados += len(df)

        if df.empty:
            continue

        # Normalizar ID
        df["Pedido ID"] = (
            df["Pedido ID"]
            .astype(str)
            .str.replace(".0", "", regex=False)
            .str.strip()
        )

        # ==================================================
        # 🚫 CANCELADOS / REEMBOLSADOS
        # ==================================================
        df_cancelados = df[
            (df.get("Cancelled At").notna()) |
            (df.get("Total Refunded", 0) >= df.get("Valor Total", 0))
        ]

        df_cancelados = df_cancelados[
            ~df_cancelados["Pedido ID"].isin(ids_ignorados)
        ]

        if not df_cancelados.empty:
            df_cancelados = df_cancelados[COLUNAS_PEDIDOS]
            append_aba(nome_planilha, "Pedidos Ignorados", df_cancelados)
            ids_ignorados.update(df_cancelados["Pedido ID"])
            total_ignorados += len(df_cancelados)

        # ==================================================
        # ✅ PEDIDOS VÁLIDOS
        # ==================================================
        df_validos = df[
            (df.get("Cancelled At").isna()) &
            (df.get("Total Refunded", 0) < df.get("Valor Total", 0))
        ]

        df_validos = df_validos[
            ~df_validos["Pedido ID"].isin(ids_pedidos)
        ]

        if df_validos.empty:
            continue

        # 🔒 GARANTIR CONTRATO DA ABA
        df_validos = df_validos[COLUNAS_PEDIDOS]

        df_validos["Data de criação"] = (
            pd.to_datetime(
                df_validos["Data de criação"],
                errors="coerce",
                utc=True
            )
            .dt.tz_convert("America/Sao_Paulo")
            .dt.tz_localize(None)
            .dt.strftime("%d/%m/%Y %H:%M")
        )
        
        append_aba(nome_planilha, "Pedidos Shopify", df_validos)
        ids_pedidos.update(df_validos["Pedido ID"])
        total_novos += len(df_validos)

    return {
        "status": "success",
        "mensagem": (
            "✅ Sincronização de pedidos concluída\n\n"
            f"📦 Processados: {total_processados}\n"
            f"🆕 Novos: {total_novos}\n"
            f"🚫 Ignorados: {total_ignorados}"
        ),
        "total_processados": total_processados,
        "total_novos": total_novos,
        "total_ignorados": total_ignorados
    }
