# utils/sync.py

import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo

from utils.shopify import buscar_pedidos_pagos_direto
from utils.sheets import ler_aba, escrever_aba, ler_ids_existentes, append_aba
from utils.classificacao import agregar_por_cliente, calcular_estado

APP_TZ = ZoneInfo("America/Sao_Paulo")


# ======================================================
# SINCRONIZAÇÃO INCREMENTAL RÁPIDA
# ======================================================
def sincronizar_incremental(nome_planilha: str = "Clientes Shopify") -> dict:
    """
    Sincronização INCREMENTAL e RÁPIDA:
    
    1. Busca pedidos da Shopify (cache 5 min)
    2. Compara com IDs da planilha
    3. Adiciona APENAS pedidos novos
    4. Reagrega clientes
    
    Vantagem: Não refaz tudo, só processa o que é novo!
    """
    
    # ==================================================
    # 1. BUSCAR PEDIDOS DA SHOPIFY (COM CACHE)
    # ==================================================
    df_shopify = buscar_pedidos_pagos_direto()
    
    if df_shopify.empty:
        return {
            "status": "warning",
            "mensagem": "⚠️ Nenhum pedido encontrado na Shopify",
            "novos_pedidos": 0,
            "total_clientes": 0
        }
    
    # ==================================================
    # 2. FILTRAR PEDIDOS VÁLIDOS
    # ==================================================
    df_shopify = df_shopify[df_shopify["Cancelled At"].isna()]
    df_shopify = df_shopify[df_shopify["Total Refunded"] < df_shopify["Valor Total"]]
    
    if df_shopify.empty:
        return {
            "status": "warning",
            "mensagem": "⚠️ Nenhum pedido válido na Shopify",
            "novos_pedidos": 0,
            "total_clientes": 0
        }
    
    # Normalizar IDs
    df_shopify["Pedido ID"] = df_shopify["Pedido ID"].astype(str).str.strip()
    
    # ==================================================
    # 3. BUSCAR IDS JÁ SALVOS NA PLANILHA
    # ==================================================
    try:
        ids_existentes = ler_ids_existentes(
            planilha=nome_planilha,
            aba="Pedidos Shopify",
            coluna_id="Pedido ID"
        )
    except Exception:
        # Primeira vez, não existe aba ainda
        ids_existentes = set()
    
    # ==================================================
    # 4. FILTRAR APENAS PEDIDOS NOVOS
    # ==================================================
    df_novos = df_shopify[~df_shopify["Pedido ID"].isin(ids_existentes)]
    
    total_novos = len(df_novos)
    
    # ==================================================
    # 5. ADICIONAR PEDIDOS NOVOS NA PLANILHA
    # ==================================================
    if total_novos > 0:
        # Remover colunas internas
        df_novos_salvar = df_novos.drop(
            columns=["Cancelled At", "Total Refunded", "Financial Status"],
            errors="ignore"
        )
        
        try:
            append_aba(
                planilha=nome_planilha,
                aba="Pedidos Shopify",
                df=df_novos_salvar
            )
        except Exception as e:
            return {
                "status": "error",
                "mensagem": f"❌ Erro ao salvar pedidos: {str(e)}",
                "novos_pedidos": 0,
                "total_clientes": 0
            }
    
    # ==================================================
    # 6. LER TODOS OS PEDIDOS DA PLANILHA
    # ==================================================
    try:
        df_pedidos = ler_aba(nome_planilha, "Pedidos Shopify")
    except Exception as e:
        return {
            "status": "error",
            "mensagem": f"❌ Erro ao ler pedidos da planilha: {str(e)}",
            "novos_pedidos": total_novos,
            "total_clientes": 0
        }
    
    if df_pedidos.empty:
        return {
            "status": "warning",
            "mensagem": "⚠️ Planilha vazia após sincronização",
            "novos_pedidos": total_novos,
            "total_clientes": 0
        }
    
    # ==================================================
    # 7. NORMALIZAR DATAS
    # ==================================================
    df_pedidos["Data de criação"] = (
        pd.to_datetime(df_pedidos["Data de criação"], errors="coerce", utc=True)
        .dt.tz_convert("America/Sao_Paulo")
        .dt.tz_localize(None)
    )
    
    # ==================================================
    # 8. AGREGAR CLIENTES
    # ==================================================
    df_clientes = agregar_por_cliente(df_pedidos)
    
    if df_clientes.empty:
        return {
            "status": "warning",
            "mensagem": "⚠️ Nenhum cliente gerado",
            "novos_pedidos": total_novos,
            "total_clientes": 0
        }
    
    # ==================================================
    # 9. CALCULAR ESTADOS
    # ==================================================
    df_clientes = calcular_estado(
        df_clientes,
        threshold_risco=45,
        threshold_dormente=90
    )
    
    # ==================================================
    # 10. REORDENAR COLUNAS
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
    # 11. SOBRESCREVER ABA CLIENTES
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
            "mensagem": f"❌ Erro ao salvar clientes: {str(e)}",
            "novos_pedidos": total_novos,
            "total_clientes": len(df_clientes)
        }
    
    # ==================================================
    # 12. ESTATÍSTICAS
    # ==================================================
    total_campeoes = len(df_clientes[df_clientes["Nível"] == "Campeão"])
    total_leais = len(df_clientes[df_clientes["Nível"] == "Leal"])
    total_promissores = len(df_clientes[df_clientes["Nível"] == "Promissor"])
    total_novos_nivel = len(df_clientes[df_clientes["Nível"] == "Novo"])
    
    total_ativos = len(df_clientes[df_clientes["Estado"] == "🟢 Ativo"])
    total_risco = len(df_clientes[df_clientes["Estado"] == "🚨 Em risco"])
    total_dormentes = len(df_clientes[df_clientes["Estado"] == "💤 Dormente"])
    
    if total_novos > 0:
        mensagem = (
            f"✅ Sincronização concluída\n\n"
            f"🆕 **{total_novos} novos pedidos** adicionados!\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👥 **Total de clientes:** {len(df_clientes)}\n\n"
            f"**📊 Por Nível:**\n"
            f"  🏆 Campeões: {total_campeoes}\n"
            f"  💙 Leais: {total_leais}\n"
            f"  ⭐ Promissores: {total_promissores}\n"
            f"  🆕 Novos: {total_novos_nivel}\n\n"
            f"**🚦 Por Estado:**\n"
            f"  🟢 Ativos: {total_ativos}\n"
            f"  🚨 Em Risco: {total_risco}\n"
            f"  💤 Dormentes: {total_dormentes}"
        )
    else:
        mensagem = (
            f"✅ Base já está atualizada!\n\n"
            f"📦 Nenhum pedido novo encontrado\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👥 **Total de clientes:** {len(df_clientes)}\n\n"
            f"**📊 Por Nível:**\n"
            f"  🏆 Campeões: {total_campeoes}\n"
            f"  💙 Leais: {total_leais}\n"
            f"  ⭐ Promissores: {total_promissores}\n"
            f"  🆕 Novos: {total_novos_nivel}\n\n"
            f"**🚦 Por Estado:**\n"
            f"  🟢 Ativos: {total_ativos}\n"
            f"  🚨 Em Risco: {total_risco}\n"
            f"  💤 Dormentes: {total_dormentes}"
        )
    
    return {
        "status": "success",
        "mensagem": mensagem,
        "novos_pedidos": total_novos,
        "total_clientes": len(df_clientes)
    }


# ======================================================
# CARREGAR DADOS DA PLANILHA (RÁPIDO)
# ======================================================
def carregar_dados_planilha(nome_planilha: str = "Clientes Shopify") -> pd.DataFrame:
    """
    Carrega clientes JÁ PROCESSADOS da planilha.
    
    Muito mais rápido que processar tudo novamente!
    
    Returns:
        DataFrame com clientes agregados
    """
    try:
        df_clientes = ler_aba(nome_planilha, "Clientes Shopify")
        
        # Normalizar datas
        if "Primeiro Pedido" in df_clientes.columns:
            df_clientes["Primeiro Pedido"] = pd.to_datetime(
                df_clientes["Primeiro Pedido"], 
                errors="coerce"
            )
        
        if "Ultimo Pedido" in df_clientes.columns:
            df_clientes["Ultimo Pedido"] = pd.to_datetime(
                df_clientes["Ultimo Pedido"], 
                errors="coerce"
            )
        
        return df_clientes
        
    except Exception as e:
        raise Exception(f"Erro ao carregar planilha: {str(e)}")


# ======================================================
# CALCULAR ESTATÍSTICAS
# ======================================================
def calcular_estatisticas(df_clientes: pd.DataFrame) -> dict:
    """
    Calcula estatísticas da base de clientes.
    
    Args:
        df_clientes: DataFrame com clientes agregados
    
    Returns:
        dict: Estatísticas completas
    
    Exemplo:
        >>> stats = calcular_estatisticas(df_clientes)
        >>> print(f"Total: {stats['total_clientes']}")
    """
    
    if df_clientes.empty:
        return {
            "total_clientes": 0,
            "faturamento_total": 0.0,
            "ticket_medio": 0.0,
            "campeoes": 0,
            "leais": 0,
            "promissores": 0,
            "novos": 0,
            "ativos": 0,
            "em_risco": 0,
            "dormentes": 0
        }
    
    # Métricas gerais
    total_clientes = len(df_clientes)
    faturamento_total = float(df_clientes["Valor Total"].sum())
    ticket_medio = faturamento_total / total_clientes if total_clientes > 0 else 0.0
    
    # Por nível
    total_campeoes = len(df_clientes[df_clientes["Nível"] == "Campeão"])
    total_leais = len(df_clientes[df_clientes["Nível"] == "Leal"])
    total_promissores = len(df_clientes[df_clientes["Nível"] == "Promissor"])
    total_novos = len(df_clientes[df_clientes["Nível"] == "Novo"])
    
    # Por estado
    total_ativos = len(df_clientes[df_clientes["Estado"] == "🟢 Ativo"])
    total_risco = len(df_clientes[df_clientes["Estado"] == "🚨 Em risco"])
    total_dormentes = len(df_clientes[df_clientes["Estado"] == "💤 Dormente"])
    
    return {
        "total_clientes": total_clientes,
        "faturamento_total": faturamento_total,
        "ticket_medio": ticket_medio,
        "campeoes": total_campeoes,
        "leais": total_leais,
        "promissores": total_promissores,
        "novos": total_novos,
        "ativos": total_ativos,
        "em_risco": total_risco,
        "dormentes": total_dormentes
    }
