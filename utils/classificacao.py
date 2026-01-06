# utils/classificacao.py

import pandas as pd
import pytz
from typing import Dict, List


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
    - Nível (Novo/Promissor/Leal/Campeão)
    
    ORDENAÇÃO: Mais recente no topo (Ultimo Pedido DESC)
    
    Raises:
        ValueError: Se colunas obrigatórias estiverem ausentes
    """
    
    if df_pedidos.empty:
        return pd.DataFrame()
    
    # Validar colunas obrigatórias
    colunas_obrigatorias = [
        "Pedido ID", "Customer ID", "Cliente", 
        "Email", "Valor Total", "Data de criação"
    ]
    colunas_faltantes = set(colunas_obrigatorias) - set(df_pedidos.columns)
    
    if colunas_faltantes:
        raise ValueError(
            f"❌ Colunas obrigatórias ausentes: {', '.join(colunas_faltantes)}"
        )
    
    # ======================================================
    # 1. CRIAR CHAVE ÚNICA (Customer ID)
    # ======================================================
    df_pedidos = df_pedidos.copy()  # Evitar SettingWithCopyWarning
    
    df_pedidos["cliente_key"] = (
        df_pedidos["Customer ID"]
        .astype(str)
        .str.strip()
    )
    
    # Fallback para clientes sem Customer ID (casos raros)
    mask_sem_id = df_pedidos["cliente_key"].isin(["", "nan", "None"])
    df_pedidos.loc[mask_sem_id, "cliente_key"] = (
        "EMAIL_" + 
        df_pedidos.loc[mask_sem_id, "Email"]
        .astype(str)
        .str.lower()
        .str.strip()
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
    
    # Renomear colunas para padrão final
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
    df_clientes = df_clientes.copy()

    df_clientes["Ultimo Pedido"] = pd.to_datetime(
        df_clientes["Ultimo Pedido"],
        errors="coerce"
    )

    # Marcar registros com problema de data (debug explícito)
    df_clientes["Erro Data Ultimo Pedido"] = df_clientes["Ultimo Pedido"].isna()

    hoje = pd.Timestamp.now(
        tz=pytz.timezone("America/Sao_Paulo")
    ).tz_localize(None)

    df_clientes["Dias sem comprar"] = (
        hoje - df_clientes["Ultimo Pedido"]
    ).dt.days

    # 👇 ESTA LINHA ENTRA AQUI (mesma identação)
    df_clientes.loc[
        df_clientes["Erro Data Ultimo Pedido"],
        "Dias sem comprar"
    ] = None

    # Garantir que não há valores negativos (edge case)
    df_clientes["Dias sem comprar"] = (
        df_clientes["Dias sem comprar"].clip(lower=0)
    )
    
    # ======================================================
    # 4. CLASSIFICAR CLIENTES (COLUNA "Nível")
    # ======================================================
    df_clientes["Nível"] = df_clientes.apply(
        _calcular_classificacao, 
        axis=1
    )
    
    # ======================================================
    # 5. ORDENAR POR DATA (MAIS RECENTE PRIMEIRO)
    # ======================================================
    df_clientes = df_clientes.sort_values(
        ["Ultimo Pedido"],
        ascending=[False]  # Mais recente no topo
    )
    
    # ======================================================
    # 6. REORDENAR COLUNAS (SEM "Estado" ainda)
    # ======================================================
    colunas_ordenadas = [
        "Customer ID",
        "Cliente",
        "Email",
        "Qtd Pedidos",
        "Valor Total",
        "Primeiro Pedido",
        "Ultimo Pedido",
        "Dias sem comprar",
        "Nível"
    ]
    
    df_clientes = df_clientes[colunas_ordenadas]
    
    # ======================================================
    # 7. RESETAR INDEX
    # ======================================================
    df_clientes = df_clientes.reset_index(drop=True)
    
    return df_clientes


# ======================================================
# CLASSIFICAÇÃO RFM (Recency, Frequency, Monetary)
# ======================================================
def _calcular_classificacao(row) -> str:
    """
    Classifica cliente baseado em RFM (Recency, Frequency, Monetary).
    
    Critérios:
    - Campeão: (5+ pedidos OU R$ 5.000+) E ativo há < 60 dias
    - Leal: (3+ pedidos OU R$ 2.000+) E ativo há < 90 dias
    - Promissor: (2+ pedidos OU R$ 500+) E ativo há < 120 dias
    - Novo: 1 pedido e ativo há < 90 dias
    
    Args:
        row: Linha do DataFrame com as colunas:
             "Qtd Pedidos", "Valor Total", "Dias sem comprar"
    
    Returns:
        str: "Campeão", "Leal", "Promissor" ou "Novo"
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
        return "Iniciante"
    
    # Fallback: classificar como Novo
    return "Iniciante"


# ======================================================
# CALCULAR CICLO MÉDIO DE COMPRA
# ======================================================
def calcular_ciclo_medio(df_clientes: pd.DataFrame) -> Dict:
    """
    Analisa clientes recorrentes e retorna estatísticas
    sobre o ciclo médio de compra.
    
    Args:
        df_clientes: DataFrame com clientes agregados
                     (deve ter colunas "Qtd Pedidos", "Primeiro Pedido", "Ultimo Pedido")
    
    Returns:
        dict: {
            "ciclo_mediana": float | None,
            "ciclo_media": float | None,
            "threshold_ativo": int,
            "threshold_risco": int,
            "threshold_dormente": int,
            "total_recorrentes": int
        }
    
    Exemplo:
        >>> ciclo = calcular_ciclo_medio(df_clientes)
        >>> print(f"Ciclo médio: {ciclo['ciclo_mediana']} dias")
    """
    
    if df_clientes.empty:
        return {
            "ciclo_mediana": None,
            "ciclo_media": None,
            "threshold_ativo": 45,
            "threshold_risco": 90,
            "threshold_dormente": 90,
            "total_recorrentes": 0
        }

    # 🔒 GARANTIR QUE AS DATAS SÃO DATETIME
    df_clientes = df_clientes.copy()

    df_clientes["Primeiro Pedido"] = pd.to_datetime(
        df_clientes["Primeiro Pedido"],
        errors="coerce"
    )

    df_clientes["Ultimo Pedido"] = pd.to_datetime(
        df_clientes["Ultimo Pedido"],
        errors="coerce"
    )

    
    # Filtrar apenas clientes com 2+ pedidos
    clientes_recorrentes = df_clientes[df_clientes["Qtd Pedidos"] >= 2].copy()
    
    if len(clientes_recorrentes) < 5:
        # Poucos dados para análise confiável
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
    
    # Remover valores inválidos (zero ou negativos)
    clientes_recorrentes = clientes_recorrentes[
        clientes_recorrentes["Ciclo_Medio"] > 0
    ]
    
    if clientes_recorrentes.empty:
        return {
            "ciclo_mediana": None,
            "ciclo_media": None,
            "threshold_ativo": 45,
            "threshold_risco": 90,
            "threshold_dormente": 90,
            "total_recorrentes": 0
        }
    
    # Estatísticas
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
    
    Args:
        df_clientes: DataFrame com clientes
        threshold_risco: Dias para classificar como "Em risco" (padrão: 45)
        threshold_dormente: Dias para classificar como "Dormente" (padrão: 90)
    
    Returns:
        pd.DataFrame: DataFrame original com coluna "Estado" adicionada
    
    Estados possíveis:
        - "🟢 Ativo": < threshold_risco dias
        - "🚨 Em risco": entre threshold_risco e threshold_dormente dias
        - "💤 Dormente": >= threshold_dormente dias
    
    Exemplo:
        >>> df = calcular_estado(df, threshold_risco=60, threshold_dormente=120)
    """
    
    if df_clientes.empty:
        return df_clientes
    
    def _classificar_estado(dias):
        if pd.isna(dias):
            return "🟢 Ativo"  # Fallback seguro
        if dias >= threshold_dormente:
            return "💤 Dormente"
        if dias >= threshold_risco:
            return "🚨 Em risco"
        return "🟢 Ativo"
    
    df_clientes = df_clientes.copy()
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
    
    Args:
        df_clientes: DataFrame com clientes
        estado: "🟢 Ativo", "🚨 Em risco" ou "💤 Dormente"
    
    Returns:
        pd.DataFrame: DataFrame filtrado
    
    Exemplo:
        >>> clientes_risco = filtrar_por_estado(df, "🚨 Em risco")
    """
    if "Estado" not in df_clientes.columns:
        raise ValueError("❌ Coluna 'Estado' não encontrada! Execute calcular_estado() primeiro.")
    
    return df_clientes[df_clientes["Estado"] == estado].copy()


# ======================================================
# FILTRAR POR NÍVEL (ANTES ERA "CLASSIFICAÇÃO")
# ======================================================
def filtrar_por_classificacao(
    df_clientes: pd.DataFrame,
    classificacoes: List[str]
) -> pd.DataFrame:
    """
    Filtra clientes por uma ou mais níveis.
    
    Args:
        df_clientes: DataFrame com clientes
        classificacoes: Lista de níveis, ex: ["Campeão", "Leal"]
    
    Returns:
        pd.DataFrame: DataFrame filtrado
    
    Exemplo:
        >>> vips = filtrar_por_classificacao(df, ["Campeão", "Leal"])
    """
    if "Nível" not in df_clientes.columns:
        raise ValueError("❌ Coluna 'Nível' não encontrada!")
    
    return df_clientes[df_clientes["Nível"].isin(classificacoes)].copy()


# ======================================================
# MÉTRICAS AGREGADAS
# ======================================================
def calcular_metricas_gerais(df_clientes: pd.DataFrame) -> Dict:
    """
    Calcula métricas gerais da base de clientes.
    
    Args:
        df_clientes: DataFrame com clientes agregados
    
    Returns:
        dict: {
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
    
    Exemplo:
        >>> metricas = calcular_metricas_gerais(df)
        >>> print(f"Faturamento: R$ {metricas['faturamento_total']:,.2f}")
    """
    
    if df_clientes.empty:
        return {
            "total_clientes": 0,
            "faturamento_total": 0.0,
            "ticket_medio": 0.0,
            "total_campeoes": 0,
            "total_leais": 0,
            "total_promissores": 0,
            "total_novos": 0,
            "total_ativos": 0,
            "total_em_risco": 0,
            "total_dormentes": 0
        }
    
    total_clientes = len(df_clientes)
    faturamento_total = float(df_clientes["Valor Total"].sum())
    ticket_medio = faturamento_total / total_clientes if total_clientes > 0 else 0.0
    
    # Contar por nível (agora é "Nível" ao invés de "Classificação")
    contagem_nivel = df_clientes["Nível"].value_counts().to_dict()
    
    # Contar por estado (se coluna existir)
    if "Estado" in df_clientes.columns:
        contagem_estado = df_clientes["Estado"].value_counts().to_dict()
    else:
        contagem_estado = {}
    
    return {
        "total_clientes": total_clientes,
        "faturamento_total": faturamento_total,
        "ticket_medio": ticket_medio,
        "total_campeoes": contagem_nivel.get("Campeão", 0),
        "total_leais": contagem_nivel.get("Leal", 0),
        "total_promissores": contagem_nivel.get("Promissor", 0),
        "total_novos": contagem_nivel.get("Novo", 0),
        "total_ativos": contagem_estado.get("🟢 Ativo", 0),
        "total_em_risco": contagem_estado.get("🚨 Em risco", 0),
        "total_dormentes": contagem_estado.get("💤 Dormente", 0)
    }
