# utils/classificacao.py

import pandas as pd
from datetime import datetime
import pytz


# ======================================================
# AGREGAÇÃO DE PEDIDOS POR CLIENTE
# ======================================================
def agregar_por_cliente(df_pedidos: pd.DataFrame) -> pd.DataFrame:
    """
    Recebe DataFrame de pedidos individuais e retorna
    DataFrame agregado por cliente com métricas calculadas.
    
    Entrada esperada (df_pedidos):
    - Pedido ID
    - Customer ID
    - Cliente (nome)
    - Email
    - Valor Total (float)
    - Data de criação (datetime)
    
    Saída (df_clientes):
    - Customer ID
    - Cliente
    - Email
    - Qtd Pedidos
    - Valor Total (soma)
    - Primeiro Pedido
    - Ultimo Pedido
    - Dias sem comprar
    - Classificação (Novo/Promissor/Leal/Campeão)
    """
    
    if df_pedidos.empty:
        return pd.DataFrame()
    
    # ======================================================
    # 1. CRIAR CHAVE ÚNICA (Customer ID)
    # ======================================================
    df_pedidos["cliente_key"] = (
        df_pedidos["Customer ID"]
        .astype(str)
        .str.strip()
    )
    
    # Fallback para clientes sem Customer ID (casos raros)
    df_pedidos.loc[df_pedidos["cliente_key"] == "", "cliente_key"] = (
        "EMAIL_" + df_pedidos["Email"].astype(str).str.lower().str.strip()
    )
    
    # ======================================================
    # 2. AGREGAÇÃO
    # ======================================================
    df_clientes = (
        df_pedidos
        .groupby("cliente_key", as_index=False)
        .agg(
            Customer_ID=("Customer ID", "first"),
            Cliente=("Cliente", "last"),
            Email=("Email", "last"),
            Qtd_Pedidos=("Pedido ID", "count"),
            Valor_Total=("Valor Total", "sum"),
            Primeiro_Pedido=("Data de criação", "min"),
            Ultimo_Pedido=("Data de criação", "max"),
        )
    )
    
    # Renomear colunas
    df_clientes = df_clientes.rename(columns={
        "Customer_ID": "Customer ID",
        "Valor_Total": "Valor Total",
        "Qtd_Pedidos": "Qtd Pedidos",
        "Primeiro_Pedido": "Primeiro Pedido",
        "Ultimo_Pedido": "Ultimo Pedido",
    })
    
    # ======================================================
    # 3. CALCULAR DIAS SEM COMPRAR
    # ======================================================
    hoje = pd.Timestamp.now(tz=pytz.timezone("America/Sao_Paulo")).tz_localize(None)
    df_clientes["Dias sem comprar"] = (hoje - df_clientes["Ultimo Pedido"]).dt.days
    
    # ======================================================
    # 4. CLASSIFICAR CLIENTES
    # ======================================================
    df_clientes["Classificação"] = df_clientes.apply(
        _calcular_classificacao, 
        axis=1
    )
    
    # ======================================================
    # 5. ORDENAR POR VALOR (MAIOR PRIMEIRO)
    # ======================================================
    df_clientes = df_clientes.sort_values(
        ["Valor Total", "Ultimo Pedido"],
        ascending=[False, False]
    )
    
    # ======================================================
    # 6. REMOVER COLUNA AUXILIAR
    # ======================================================
    df_clientes = df_clientes.drop(columns=["cliente_key"], errors="ignore")
    
    return df_clientes


# ======================================================
# CLASSIFICAÇÃO RFM (Recency, Frequency, Monetary)
# ======================================================
def _calcular_classificacao(row) -> str:
    """
    Classifica cliente baseado em:
    - Recency (Dias sem comprar)
    - Frequency (Quantidade de pedidos)
    - Monetary (Valor total gasto)
    
    Retorna: "Novo", "Promissor", "Leal" ou "Campeão"
    """
    qtd = row["Qtd Pedidos"]
    valor = row["Valor Total"]
    dias = row["Dias sem comprar"]
    
    # 🏆 CAMPEÃO: Alto valor + frequência + comprou recentemente
    if (qtd >= 5 or valor >= 5000) and dias < 60:
        return "Campeão"
    
    # 💙 LEAL: Compra regularmente com bom valor
    if (qtd >= 3 or valor >= 2000) and dias < 90:
        return "Leal"
    
    # ⭐ PROMISSOR: Mostra potencial (2+ compras ou ticket alto)
    if (qtd >= 2 or valor >= 500) and dias < 120:
        return "Promissor"
    
    # 🆕 NOVO: Primeira compra recente
    if qtd == 1 and dias < 90:
        return "Novo"
    
    # Fallback: classificar como Novo
    return "Novo"


# ======================================================
# CALCULAR CICLO MÉDIO DE COMPRA
# ======================================================
def calcular_ciclo_medio(df_clientes: pd.DataFrame) -> dict:
    """
    Analisa clientes recorrentes e retorna estatísticas
    sobre o ciclo médio de compra.
    
    Retorna:
    {
        "ciclo_mediana": float,  # Mediana do ciclo em dias
        "ciclo_media": float,    # Média do ciclo em dias
        "threshold_ativo": int,  # Sugestão para "Ativo"
        "threshold_risco": int,  # Sugestão para "Em Risco"
        "threshold_dormente": int,  # Sugestão para "Dormente"
        "total_recorrentes": int  # Qtd de clientes analisados
    }
    """
    
    # Filtrar apenas clientes com 2+ pedidos
    clientes_recorrentes = df_clientes[df_clientes["Qtd Pedidos"] >= 2].copy()
    
    if len(clientes_recorrentes) < 5:
        # Poucos dados para análise, retorna valores padrão
        return {
            "ciclo_mediana": None,
            "ciclo_media": None,
            "threshold_ativo": 45,
            "threshold_risco": 90,
            "threshold_dormente": 90,
            "total_recorrentes": len(clientes_recorrentes)
        }
    
    # Calcular dias totais entre primeira e última compra
    clientes_recorrentes["Dias_Total"] = (
        clientes_recorrentes["Ultimo Pedido"] - 
        clientes_recorrentes["Primeiro Pedido"]
    ).dt.days
    
    # Calcular ciclo médio (dias totais / quantidade de intervalos)
    clientes_recorrentes["Ciclo_Medio"] = (
        clientes_recorrentes["Dias_Total"] / 
        (clientes_recorrentes["Qtd Pedidos"] - 1)
    )
    
    # Remover valores extremos (outliers)
    ciclo_mediana = clientes_recorrentes["Ciclo_Medio"].median()
    ciclo_media = clientes_recorrentes["Ciclo_Medio"].mean()
    
    # Calcular thresholds sugeridos
    threshold_ativo = int(ciclo_mediana * 1.5)
    threshold_risco = int(ciclo_mediana * 3)
    
    return {
        "ciclo_mediana": round(ciclo_mediana, 1),
        "ciclo_media": round(ciclo_media, 1),
        "threshold_ativo": threshold_ativo,
        "threshold_risco": threshold_risco,
        "threshold_dormente": threshold_risco,
        "total_recorrentes": len(clientes_recorrentes)
    }


# ======================================================
# CALCULAR ESTADO (ATIVO / EM RISCO / DORMENTE)
# ======================================================
def calcular_estado(
    df_clientes: pd.DataFrame,
    threshold_risco: int = 45,
    threshold_dormente: int = 90
) -> pd.DataFrame:
    """
    Adiciona coluna "Estado" ao DataFrame de clientes
    baseado em dias sem comprar.
    
    Parâmetros:
    - threshold_risco: dias para classificar como "Em risco"
    - threshold_dormente: dias para classificar como "Dormente"
    
    Retorna DataFrame com coluna "Estado" adicionada.
    """
    
    def _classificar_estado(dias):
        if dias >= threshold_dormente:
            return "💤 Dormente"
        if dias >= threshold_risco:
            return "🚨 Em risco"
        return "🟢 Ativo"
    
    df_clientes["Estado"] = df_clientes["Dias sem comprar"].apply(_classificar_estado)
    
    return df_clientes


# ======================================================
# FILTRAR POR ESTADO
# ======================================================
def filtrar_por_estado(
    df_clientes: pd.DataFrame, 
    estado: str
) -> pd.DataFrame:
    """
    Filtra clientes por estado específico.
    
    Parâmetros:
    - estado: "🟢 Ativo", "🚨 Em risco" ou "💤 Dormente"
    
    Retorna DataFrame filtrado.
    """
    return df_clientes[df_clientes["Estado"] == estado].copy()


# ======================================================
# FILTRAR POR CLASSIFICAÇÃO
# ======================================================
def filtrar_por_classificacao(
    df_clientes: pd.DataFrame,
    classificacoes: list
) -> pd.DataFrame:
    """
    Filtra clientes por classificação(ões).
    
    Parâmetros:
    - classificacoes: lista como ["Campeão", "Leal"]
    
    Retorna DataFrame filtrado.
    """
    return df_clientes[df_clientes["Classificação"].isin(classificacoes)].copy()


# ======================================================
# MÉTRICAS AGREGADAS
# ======================================================
def calcular_metricas_gerais(df_clientes: pd.DataFrame) -> dict:
    """
    Calcula métricas gerais da base de clientes.
    
    Retorna:
    {
        "total_clientes": int,
        "faturamento_total": float,
        "ticket_medio": float,
        "total_campeoes": int,
        "total_leais": int,
        "total_promissores": int,
        "total_novos": int,
        "total_ativos": int,
        "total_em_risco": int,
        "total_dormentes": int
    }
    """
    
    if df_clientes.empty:
        return {
            "total_clientes": 0,
            "faturamento_total": 0,
            "ticket_medio": 0,
            "total_campeoes": 0,
            "total_leais": 0,
            "total_promissores": 0,
            "total_novos": 0,
            "total_ativos": 0,
            "total_em_risco": 0,
            "total_dormentes": 0
        }
    
    total_clientes = len(df_clientes)
    faturamento_total = df_clientes["Valor Total"].sum()
    ticket_medio = faturamento_total / total_clientes if total_clientes > 0 else 0
    
    return {
        "total_clientes": total_clientes,
        "faturamento_total": faturamento_total,
        "ticket_medio": ticket_medio,
        "total_campeoes": len(df_clientes[df_clientes["Classificação"] == "Campeão"]),
        "total_leais": len(df_clientes[df_clientes["Classificação"] == "Leal"]),
        "total_promissores": len(df_clientes[df_clientes["Classificação"] == "Promissor"]),
        "total_novos": len(df_clientes[df_clientes["Classificação"] == "Novo"]),
        "total_ativos": len(df_clientes[df_clientes["Estado"] == "🟢 Ativo"]),
        "total_em_risco": len(df_clientes[df_clientes["Estado"] == "🚨 Em risco"]),
        "total_dormentes": len(df_clientes[df_clientes["Estado"] == "💤 Dormente"])
    }
