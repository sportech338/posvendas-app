# utils/sync.py

import pandas as pd

from utils.shopify import puxar_pedidos_pagos_em_lotes
from utils.sheets import (
    append_aba,
    ler_ids_existentes,
    ler_aba,
    escrever_aba
)
from utils.classificacao import agregar_por_cliente, calcular_estado


# ======================================================
# SINCRONIZAÇÃO COMPLETA (PEDIDOS + CLIENTES)
# ======================================================
def sincronizar_shopify_completo(
    nome_planilha: str = "Clientes Shopify",
    lote_tamanho: int = 500
) -> dict:
    """
    Sincronização COMPLETA em 2 etapas:
    
    1️⃣ Sincroniza pedidos da Shopify → Planilha
       - Pedidos válidos → "Pedidos Shopify"
       - Cancelados/Reembolsados → "Pedidos Ignorados"
    
    2️⃣ Agrega clientes e salva na planilha
       - Lê "Pedidos Shopify"
       - Agrega por Customer ID
       - Classifica (Novo/Promissor/Leal/Campeão)
       - Calcula estados (Ativo/Em Risco/Dormente)
       - Salva em "Clientes Shopify"
    
    Retorna estatísticas completas da sincronização.
    """
    
    # ==================================================
    # ETAPA 1: SINCRONIZAR PEDIDOS
    # ==================================================
    resultado_pedidos = sincronizar_shopify_com_planilha(
        nome_planilha=nome_planilha,
        lote_tamanho=lote_tamanho
    )
    
    if resultado_pedidos["status"] != "success":
        return resultado_pedidos
    
    # ==================================================
    # ETAPA 2: LER PEDIDOS DA PLANILHA
    # ==================================================
    try:
        df_pedidos = ler_aba(nome_planilha, "Pedidos Shopify")
    except Exception as e:
        return {
            "status": "error",
            "mensagem": f"❌ Erro ao ler planilha: {str(e)}"
        }
    
    if df_pedidos.empty:
        return {
            "status": "warning",
            "mensagem": (
                f"{resultado_pedidos['mensagem']}\n\n"
                "⚠️ Nenhum pedido encontrado para agregar clientes"
            )
        }
    
    # ==================================================
    # ETAPA 3: NORMALIZAR DATAS
    # ==================================================
    df_pedidos["Data de criação"] = (
        pd.to_datetime(df_pedidos["Data de criação"], errors="coerce", utc=True)
        .dt.tz_convert("America/Sao_Paulo")
        .dt.tz_localize(None)
    )
    
    # ==================================================
    # ETAPA 4: AGREGAR POR CLIENTE
    # ==================================================
    df_clientes = agregar_por_cliente(df_pedidos)
    
    if df_clientes.empty:
        return {
            "status": "warning",
            "mensagem": (
                f"{resultado_pedidos['mensagem']}\n\n"
                "⚠️ Nenhum cliente gerado após agregação"
            )
        }
    
    # ==================================================
    # ETAPA 5: CALCULAR ESTADOS (ATIVO/RISCO/DORMENTE)
    # ==================================================
    df_clientes = calcular_estado(
        df_clientes,
        threshold_risco=45,
        threshold_dormente=90
    )
    
    # ==================================================
    # ETAPA 5.1: REORDENAR COLUNAS NA ORDEM FINAL
    # ==================================================
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
    
    # ==================================================
    # ETAPA 6: SOBRESCREVER ABA "Clientes Shopify"
    # ==================================================
    try:
        escrever_aba(
            planilha=nome_planilha,
            aba="Clientes Shopify",
            df=df_clientes
        )
    except Exception as e:
        return {
            "status": "error",
            "mensagem": f"❌ Erro ao escrever aba Clientes: {str(e)}"
        }
    
    # ==================================================
    # ESTATÍSTICAS FINAIS (AGORA USA "Nível")
    # ==================================================
    total_campeoes = len(df_clientes[df_clientes["Nível"] == "Campeão"])
    total_leais = len(df_clientes[df_clientes["Nível"] == "Leal"])
    total_promissores = len(df_clientes[df_clientes["Nível"] == "Promissor"])
    total_novos = len(df_clientes[df_clientes["Nível"] == "Novo"])
    
    total_ativos = len(df_clientes[df_clientes["Estado"] == "🟢 Ativo"])
    total_risco = len(df_clientes[df_clientes["Estado"] == "🚨 Em risco"])
    total_dormentes = len(df_clientes[df_clientes["Estado"] == "💤 Dormente"])
    
    return {
        "status": "success",
        "mensagem": (
            f"{resultado_pedidos['mensagem']}\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👥 **Total de clientes:** {len(df_clientes)}\n\n"
            "**📊 Por Nível:**\n"
            f"  🏆 Campeões: {total_campeoes}\n"
            f"  💙 Leais: {total_leais}\n"
            f"  ⭐ Promissores: {total_promissores}\n"
            f"  🆕 Novos: {total_novos}\n\n"
            "**🚦 Por Estado:**\n"
            f"  🟢 Ativos: {total_ativos}\n"
            f"  🚨 Em Risco: {total_risco}\n"
            f"  💤 Dormentes: {total_dormentes}"
        ),
        "stats": {
            "total_pedidos_processados": resultado_pedidos.get("total_processados", 0),
            "total_clientes": len(df_clientes),
            "campeoes": total_campeoes,
            "leais": total_leais,
            "promissores": total_promissores,
            "novos": total_novos,
            "ativos": total_ativos,
            "em_risco": total_risco,
            "dormentes": total_dormentes
        }
    }


# ======================================================
# SINCRONIZAÇÃO APENAS DE PEDIDOS (FUNÇÃO ORIGINAL)
# ======================================================
def sincronizar_shopify_com_planilha(
    nome_planilha: str = "Clientes Shopify",
    lote_tamanho: int = 500
) -> dict:
    """
    Sincroniza APENAS pedidos da Shopify para a planilha.
    Não agrega clientes.
    
    Fluxo:
    Shopify →
      → Pedidos Shopify (válidos)
      → Pedidos Ignorados (cancelados / reembolsados)

    🔒 IMPORTANTE:
    - NÃO converte datas
    - NÃO altera timezone
    - Datas seguem como texto ISO (Shopify padrão)
    - Regra de negócio fica fora deste módulo
    """

    # ==================================================
    # IDS JÁ EXISTENTES (DEDUPLICAÇÃO)
    # ==================================================
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

    # ==================================================
    # BUSCA SHOPIFY (EM LOTES)
    # ==================================================
    for lote in puxar_pedidos_pagos_em_lotes(lote_tamanho):

        df = pd.DataFrame(lote)
        total_processados += len(df)

        if df.empty:
            continue

        # ==================================================
        # NORMALIZA ID (SEGURANÇA)
        # ==================================================
        if "Pedido ID" in df.columns:
            df["Pedido ID"] = (
                df["Pedido ID"]
                .astype(str)
                .str.replace(".0", "", regex=False)
                .str.strip()
            )
        else:
            continue  # sem ID não processa

        # ==================================================
        # CANCELADOS / REEMBOLSADOS
        # ==================================================
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

        # ==================================================
        # PEDIDOS VÁLIDOS
        # ==================================================
        df_validos = df[
            (df.get("Cancelled At").isna()) &
            (df.get("Total Refunded", 0) < df.get("Valor Total", 0))
        ].copy()

        df_validos = df_validos[
            ~df_validos["Pedido ID"].isin(ids_pedidos)
        ]

        if df_validos.empty:
            continue

        # Remove colunas internas
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

    # ==================================================
    # RETORNO
    # ==================================================
    return {
        "status": "success",
        "mensagem": (
            "✅ Sincronização de pedidos concluída\n\n"
            f"📦 Pedidos processados: {total_processados}\n"
            f"🆕 Pedidos válidos adicionados: {total_novos}\n"
            f"🚫 Pedidos ignorados: {total_ignorados}"
        ),
        "total_processados": total_processados,
        "total_novos": total_novos,
        "total_ignorados": total_ignorados
    }
