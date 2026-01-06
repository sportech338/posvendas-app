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
from utils.classificacao import agregar_por_cliente, calcular_estado


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
    """
    Sincronização COMPLETA:
    - Busca TODOS os pedidos pagos
    - Atualiza Pedidos Shopify / Pedidos Ignorados
    - Reagrega clientes
    """

    resultado_pedidos = sincronizar_shopify_com_planilha(
        nome_planilha=nome_planilha,
        lote_tamanho=lote_tamanho,
        data_inicio="2023-01-01T00:00:00-03:00"  # histórico completo
    )

    if resultado_pedidos["status"] != "success":
        return resultado_pedidos

    return _reagregar_clientes(nome_planilha, resultado_pedidos)


# ======================================================
# SINCRONIZAÇÃO INCREMENTAL (CACHE / 10 MIN)
# ======================================================
def sincronizar_shopify_incremental(
    nome_planilha: str = "Clientes Shopify"
) -> dict:
    """
    Sincronização incremental:
    - Busca pedidos de hoje + ontem
    - Deduplica
    - Reagrega clientes
    Ideal para cache (10 min)
    """

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
# REAGREGAR CLIENTES (USO INTERNO)
# ======================================================
def _reagregar_clientes(nome_planilha: str, resultado_pedidos: dict) -> dict:
    try:
        df_pedidos = ler_aba(nome_planilha, "Pedidos Shopify")
    except Exception as e:
        return {
            "status": "error",
            "mensagem": f"❌ Erro ao ler pedidos: {str(e)}"
        }

    if df_pedidos.empty:
        return {
            "status": "warning",
            "mensagem": "⚠️ Nenhum pedido encontrado para agregação"
        }

    # Normalizar datas
    df_pedidos["Data de criação"] = (
        pd.to_datetime(df_pedidos["Data de criação"], errors="coerce", utc=True)
        .dt.tz_convert("America/Sao_Paulo")
        .dt.tz_localize(None)
    )

    # Agregar clientes
    df_clientes = agregar_por_cliente(df_pedidos)
    df_clientes = calcular_estado(df_clientes, 45, 90)

    colunas_finais = [
        "Customer ID",
        "Cliente",
        "Email",
        "Qtd Pedidos",
        "Valor Total",
        "Primeiro Pedido",
        "Ultimo Pedido",
        "Dias sem comprar",
        "Estado",
        "Nível"
    ]

    df_clientes = df_clientes[colunas_finais]

    try:
        escrever_aba(
            planilha=nome_planilha,
            aba="Clientes Shopify",
            df=df_clientes
        )
    except Exception as e:
        return {
            "status": "error",
            "mensagem": f"❌ Erro ao escrever clientes: {str(e)}"
        }

    return {
        "status": "success",
        "mensagem": (
            f"{resultado_pedidos['mensagem']}\n\n"
            f"👥 Clientes atualizados: {len(df_clientes)}"
        )
    }


# ======================================================
# SINCRONIZAÇÃO APENAS DE PEDIDOS (BASE)
# ======================================================
def sincronizar_shopify_com_planilha(
    nome_planilha: str = "Clientes Shopify",
    lote_tamanho: int = 500,
    data_inicio: str = "2023-01-01T00:00:00-03:00"
) -> dict:
    """
    Shopify → Planilha
    - Pedidos válidos
    - Pedidos ignorados (cancelados / reembolsados)
    - Deduplicação por Pedido ID
    """

    ids_pedidos = ler_ids_existentes(
        planilha=nome_planilha,
        aba="Pedidos Shopify",
        coluna_id="Pedido ID"
    )

    ids_ignorados = ler_ids_existentes(
        planilha=nome_planilha,
        aba="Pedidos Ignorados",
        coluna_id="Pedido ID"
    )

    total_processados = 0
    total_novos = 0
    total_ignorados = 0

    for lote in puxar_pedidos_pagos_em_lotes(
        lote_tamanho=lote_tamanho,
        data_inicio=data_inicio
    ):
        df = pd.DataFrame(lote)
        total_processados += len(df)

        if df.empty or "Pedido ID" not in df.columns:
            continue

        df["Pedido ID"] = (
            df["Pedido ID"]
            .astype(str)
            .str.replace(".0", "", regex=False)
            .str.strip()
        )

        # --------------------------------------------------
        # CANCELADOS / REEMBOLSADOS
        # --------------------------------------------------
        df_cancelados = df[
            (df.get("Cancelled At").notna()) |
            (df.get("Total Refunded", 0) >= df.get("Valor Total", 0))
        ].copy()

        if not df_cancelados.empty:
            df_cancelados["Motivo"] = df_cancelados.apply(
                lambda r: "CANCELADO"
                if pd.notna(r.get("Cancelled At"))
                else "REEMBOLSADO",
                axis=1
            )

            df_cancelados_final = df_cancelados[
                [
                    "Pedido ID",
                    "Data de criação",
                    "Financial Status",
                    "Cancelled At",
                    "Motivo"
                ]
            ].rename(columns={
                "Financial Status": "Status",
                "Cancelled At": "Data de cancelamento"
            })

            df_cancelados_final = df_cancelados_final[
                ~df_cancelados_final["Pedido ID"].isin(ids_ignorados)
            ]

            if not df_cancelados_final.empty:
                append_aba(
                    planilha=nome_planilha,
                    aba="Pedidos Ignorados",
                    df=df_cancelados_final
                )

                ids_ignorados.update(df_cancelados_final["Pedido ID"].tolist())
                total_ignorados += len(df_cancelados_final)

        # --------------------------------------------------
        # PEDIDOS VÁLIDOS
        # --------------------------------------------------
        df_validos = df[
            (df.get("Cancelled At").isna()) &
            (df.get("Total Refunded", 0) < df.get("Valor Total", 0))
        ].copy()

        df_validos = df_validos[
            ~df_validos["Pedido ID"].isin(ids_pedidos)
        ]

        if df_validos.empty:
            continue

        df_validos_final = df_validos.drop(
            columns=["Cancelled At", "Total Refunded", "Financial Status"],
            errors="ignore"
        )

        append_aba(
            planilha=nome_planilha,
            aba="Pedidos Shopify",
            df=df_validos_final
        )

        ids_pedidos.update(df_validos_final["Pedido ID"].tolist())
        total_novos += len(df_validos_final)

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
