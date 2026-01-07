# utils/sheets.py

import gspread
import pandas as pd
import json
import os
from google.oauth2.service_account import Credentials
from typing import Set


# ======================================================
# CONEXÃO GOOGLE SHEETS
# ======================================================
def conectar_google_sheets():
    """
    Conecta no Google Sheets usando GCP_SERVICE_ACCOUNT_JSON (env).
    Compatível com GitHub Actions / CRON.
    """
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    raw = os.getenv("GCP_SERVICE_ACCOUNT_JSON")
    if not raw:
        raise ValueError("❌ GCP_SERVICE_ACCOUNT_JSON não definido")

    try:
        service_account_info = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"❌ JSON inválido em GCP_SERVICE_ACCOUNT_JSON: {e}")

    creds = Credentials.from_service_account_info(
        service_account_info,
        scopes=scopes
    )

    return gspread.authorize(creds)


# ======================================================
# ABRIR PLANILHA (CACHEADO)
# ======================================================
def abrir_planilha(nome_planilha: str):
    """
    Abre uma planilha do Google Sheets pelo nome.
    """
    client = conectar_google_sheets()

    try:
        return client.open(nome_planilha)
    except gspread.SpreadsheetNotFound:
        raise FileNotFoundError(
            f"❌ Planilha '{nome_planilha}' não encontrada!\n"
            f"Verifique se a service account tem acesso."
        )


# ======================================================
# CONVERSÃO DE VALORES BR → FLOAT
# ======================================================
def _converter_valor_br_para_float(serie: pd.Series) -> pd.Series:
    """
    Converte valores em formato brasileiro (R$ 1.234,56) para float.
    
    Transformações aplicadas:
    - Remove "R$"
    - Remove espaços
    - Remove ponto (separador de milhar)
    - Troca vírgula por ponto (decimal)
    - Converte para numérico
    - Preenche NaN com 0
    
    Args:
        serie: Pandas Series com valores formatados
    
    Returns:
        pd.Series: Série com valores float
    
    Exemplos:
        "R$ 1.234,56" → 1234.56
        "96,90" → 96.90
        "R$ 5.000,00" → 5000.00
    """
    return (
        serie
        .astype(str)
        .str.replace("R$", "", regex=False)
        .str.replace(" ", "", regex=False)
        .str.replace(".", "", regex=False)   # Remove separador de milhar
        .str.replace(",", ".", regex=False)  # Vírgula → ponto decimal
        .str.strip()
        .pipe(pd.to_numeric, errors="coerce")
        .fillna(0)
    )


# ======================================================
# LEITURA (SANITIZADA E COM CONVERSÃO AUTOMÁTICA)
# ======================================================
def ler_aba(planilha: str, aba: str) -> pd.DataFrame:
    """
    Lê uma aba do Google Sheets e retorna DataFrame limpo.
    
    Processamento automático:
    ✅ Remove caracteres invisíveis (NBSP, etc)
    ✅ Converte coluna "Valor Total" para float (se existir)
    ✅ Faz trim em todas as strings
    
    Args:
        planilha: Nome da planilha
        aba: Nome da aba/worksheet
    
    Returns:
        pd.DataFrame: Dados da aba como DataFrame
    
    Raises:
        gspread.WorksheetNotFound: Se aba não existir
    """
    sh = abrir_planilha(planilha)
    
    try:
        ws = sh.worksheet(aba)
    except gspread.WorksheetNotFound:
        raise ValueError(
            f"❌ Aba '{aba}' não encontrada na planilha '{planilha}'!"
        )

    # Ler todos os registros
    df = pd.DataFrame(ws.get_all_records())

    if df.empty:
        return df

    # 🔒 Limpar strings invisíveis que quebram parsing
    for col in df.select_dtypes(include="object").columns:
        df[col] = (
            df[col]
            .astype(str)
            .str.replace("\xa0", " ", regex=False)  # Non-breaking space
            .str.replace("\u200b", "", regex=False)  # Zero-width space
            .str.strip()
        )
    
    # ✅ Conversão automática de valores monetários
    if "Valor Total" in df.columns:
        df["Valor Total"] = _converter_valor_br_para_float(df["Valor Total"])

    return df


# ======================================================
# NORMALIZAÇÃO DE IDs
# ======================================================
def _normalizar_id(valor) -> str:
    """
    Normaliza IDs para comparação consistente.
    
    Remove:
    - Decimais desnecessários (.0)
    - Vírgulas
    - Espaços em branco
    
    Args:
        valor: ID para normalizar (qualquer tipo)
    
    Returns:
        str: ID normalizado
    
    Exemplos:
        123.0 → "123"
        "456.0" → "456"
        "789," → "789"
    """
    if valor is None or valor == "":
        return ""
    
    return (
        str(valor)
        .replace(".0", "")
        .replace(",", "")
        .strip()
    )


def ler_ids_existentes(planilha: str, aba: str, coluna_id: str) -> Set[str]:
    """
    Lê apenas a coluna de IDs de uma aba (para deduplicação).
    
    Útil para verificar se um ID já existe antes de inserir.
    Retorna set vazio se aba não existir ou não tiver a coluna.
    
    Args:
        planilha: Nome da planilha
        aba: Nome da aba
        coluna_id: Nome da coluna que contém IDs
    
    Returns:
        Set[str]: Conjunto de IDs já existentes (normalizados)
    
    Exemplo:
        >>> ids = ler_ids_existentes("Clientes", "Pedidos Shopify", "Pedido ID")
        >>> if "12345" not in ids:
        >>>     # Inserir novo pedido
    """
    try:
        df = ler_aba(planilha, aba)

        if df.empty or coluna_id not in df.columns:
            return set()

        return set(
            df[coluna_id]
            .apply(_normalizar_id)
            .tolist()
        )
    except (ValueError, FileNotFoundError, gspread.WorksheetNotFound):
        # Aba não existe ou está vazia
        return set()


# ======================================================
# ESCRITA INCREMENTAL (APPEND)
# ======================================================
def append_aba(planilha: str, aba: str, df: pd.DataFrame):
    """
    Adiciona linhas no FINAL da aba sem apagar conteúdo existente.
    
    Comportamento:
    ✅ Preserva tipos numéricos (números ficam como números)
    ✅ Cria aba automaticamente se não existir
    ✅ Adiciona cabeçalho se aba for nova
    ✅ NaN/None vira string vazia
    
    Args:
        planilha: Nome da planilha
        aba: Nome da aba
        df: DataFrame com dados para adicionar
    
    Exemplo:
        >>> novos_pedidos = pd.DataFrame([...])
        >>> append_aba("Clientes Shopify", "Pedidos Shopify", novos_pedidos)
    """
    if df.empty:
        return

    sh = abrir_planilha(planilha)

    # Criar aba se não existir
    try:
        ws = sh.worksheet(aba)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=aba, rows=1000, cols=20)
        # Adicionar cabeçalho
        ws.append_row(df.columns.tolist())

    # ✅ Converter DataFrame para lista preservando tipos
    valores = []
    for _, row in df.iterrows():
        linha = []
        for val in row:
            # Manter números como números
            if pd.notna(val) and isinstance(val, (int, float)):
                linha.append(val)
            # NaN/None vira string vazia
            elif pd.isna(val):
                linha.append("")
            # Resto vira string
            else:
                linha.append(str(val))
        valores.append(linha)

    # Inserir linhas (USER_ENTERED permite Google Sheets interpretar tipos)
    ws.append_rows(
        valores,
        value_input_option="USER_ENTERED"
    )


# ======================================================
# ESCRITA TOTAL (SOBRESCREVER)
# ======================================================
def escrever_aba(planilha: str, aba: str, df: pd.DataFrame):
    """
    SOBRESCREVE completamente o conteúdo da aba.
    
    ⚠️ ATENÇÃO: Apaga tudo que estava na aba antes!
    
    Comportamento:
    ✅ Preserva tipos numéricos
    ✅ Cria aba automaticamente se não existir
    ✅ Inclui cabeçalho
    
    Args:
        planilha: Nome da planilha
        aba: Nome da aba
        df: DataFrame com TODOS os dados (não incremental)
    
    Exemplo:
        >>> clientes_agregados = pd.DataFrame([...])
        >>> escrever_aba("Clientes Shopify", "Clientes Shopify", clientes_agregados)
    """
    sh = abrir_planilha(planilha)

    # Criar aba se não existir
    try:
        ws = sh.worksheet(aba)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=aba, rows=1000, cols=20)

    # Limpar conteúdo anterior
    ws.clear()
    
    # ✅ Preparar dados (cabeçalho + linhas)
    valores = [df.columns.tolist()]
    
    for _, row in df.iterrows():
        linha = []
        for val in row:
            # Manter números como números
            if pd.notna(val) and isinstance(val, (int, float)):
                linha.append(val)
            # NaN/None vira string vazia
            elif pd.isna(val):
                linha.append("")
            # Resto vira string
            else:
                linha.append(str(val))
        valores.append(linha)
    
    # Escrever tudo de uma vez
    ws.update(
        valores,
        value_input_option="USER_ENTERED"
    )


# ======================================================
# VERIFICAR SE ABA EXISTE
# ======================================================
def aba_existe(planilha: str, aba: str) -> bool:
    """
    Verifica se uma aba existe na planilha.
    
    Args:
        planilha: Nome da planilha
        aba: Nome da aba para verificar
    
    Returns:
        bool: True se aba existe, False caso contrário
    
    Exemplo:
        >>> if not aba_existe("Clientes Shopify", "Registro Ações"):
        >>>     criar_aba_registro()
    """
    try:
        sh = abrir_planilha(planilha)
        sh.worksheet(aba)
        return True
    except gspread.WorksheetNotFound:
        return False
