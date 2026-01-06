# utils/sync.py

import pandas as pd
from utils.shopify import buscar_pedidos_pagos_direto
from utils.classificacao import agregar_por_cliente, calcular_estado


# ======================================================
# CARREGAR DADOS DIRETO DA SHOPIFY (COM CACHE)
# ======================================================
def carregar_dados_shopify() -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Carrega pedidos DIRETO da Shopify e agrega clientes.
    
    Fluxo:
    1. Busca pedidos pagos da Shopify (cache 5 min)
    2. Filtra cancelados/reembolsados
    3. Agrega por cliente
    4. Calcula estados e níveis
    
    Returns:
        tuple: (df_pedidos, df_clientes)
    
    Exemplo:
        >>> df_pedidos, df_clientes = carregar_dados_shopify()
        >>> print(len(df_clientes))
    """
    
    # ==================================================
    # 1. BUSCAR PEDIDOS DA SHOPIFY (COM CACHE)
    # ==================================================
    df_pedidos = buscar_pedidos_pagos_direto()
    
    if df_pedidos.empty:
        return pd.DataFrame(), pd.DataFrame()
    
    # ==================================================
    # 2. FILTRAR PEDIDOS VÁLIDOS
    # ==================================================
    # Remover cancelados
    df_pedidos = df_pedidos[df_pedidos["Cancelled At"].isna()]
    
    # Remover totalmente reembolsados
    df_pedidos = df_pedidos[
        df_pedidos["Total Refunded"] < df_pedidos["Valor Total"]
    ]
    
    if df_pedidos.empty:
        return pd.DataFrame(), pd.DataFrame()
    
    # ==================================================
    # 3. NORMALIZAR DATAS
    # ==================================================
    df_pedidos["Data de criação"] = (
        pd.to_datetime(df_pedidos["Data de criação"], errors="coerce", utc=True)
        .dt.tz_convert("America/Sao_Paulo")
        .dt.tz_localize(None)
    )
    
    # ==================================================
    # 4. AGREGAR CLIENTES
    # ==================================================
    df_clientes = agregar_por_cliente(df_pedidos)
    
    if df_clientes.empty:
        return df_pedidos, pd.DataFrame()
    
    # ==================================================
    # 5. CALCULAR ESTADOS
    # ==================================================
    df_clientes = calcular_estado(
        df_clientes,
        threshold_risco=45,
        threshold_dormente=90
    )
    
    # ==================================================
    # 6. REORDENAR COLUNAS
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
    
    return df_pedidos, df_clientes


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


# ======================================================
# SALVAR BACKUP NO GOOGLE SHEETS (OPCIONAL)
# ======================================================
def salvar_backup_sheets(
    df_pedidos: pd.DataFrame,
    df_clientes: pd.DataFrame,
    nome_planilha: str = "Clientes Shopify"
):
    """
    Salva backup dos dados no Google Sheets (opcional).
    
    Use apenas se quiser manter histórico no Sheets.
    
    Args:
        df_pedidos: DataFrame de pedidos
        df_clientes: DataFrame de clientes
        nome_planilha: Nome da planilha no Google Drive
    
    Exemplo:
        >>> salvar_backup_sheets(df_pedidos, df_clientes)
    """
    from utils.sheets import escrever_aba
    
    try:
        # Salvar pedidos
        if not df_pedidos.empty:
            escrever_aba(nome_planilha, "Pedidos Shopify", df_pedidos)
        
        # Salvar clientes
        if not df_clientes.empty:
            escrever_aba(nome_planilha, "Clientes Shopify", df_clientes)
        
        return {
            "status": "success",
            "mensagem": "✅ Backup salvo no Google Sheets"
        }
    
    except Exception as e:
        return {
            "status": "error",
            "mensagem": f"❌ Erro ao salvar backup: {str(e)}"
        }
