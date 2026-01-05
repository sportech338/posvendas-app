# utils/sheets.py

import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials


# ======================================================
# CONEXÃO GOOGLE
# ======================================================
@st.cache_resource
def conectar_google_sheets():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scopes
    )

    return gspread.authorize(creds)


# ======================================================
# ABRIR PLANILHA (CACHEADO)
# ======================================================
@st.cache_resource
def abrir_planilha(nome_planilha: str):
    client = conectar_google_sheets()
    return client.open(nome_planilha)


# ======================================================
# LEITURA (SANITIZADA)
# ======================================================
def ler_aba(planilha: str, aba: str) -> pd.DataFrame:
    """
    Lê uma aba do Google Sheets e retorna DataFrame
    com saneamento básico de strings (sem conversão de tipos).
    """
    sh = abrir_planilha(planilha)
    ws = sh.worksheet(aba)

    df = pd.DataFrame(ws.get_all_records())

    if df.empty:
        return df

    # 🔒 Limpa strings invisíveis que quebram parse depois
    for col in df.select_dtypes(include="object").columns:
        df[col] = (
            df[col]
            .astype(str)
            .str.replace("\xa0", " ", regex=False)  # NBSP
            .str.strip()
        )

    return df


# ======================================================
# NORMALIZAÇÕES
# ======================================================
def _normalizar_id(valor) -> str:
    if valor is None:
        return ""
    return (
        str(valor)
        .replace(".0", "")
        .replace(",", "")
        .strip()
    )


def ler_ids_existentes(planilha: str, aba: str, coluna_id: str) -> set:
    """
    Lê apenas a coluna de IDs para deduplicação
    """
    try:
        df = ler_aba(planilha, aba)

        if coluna_id not in df.columns:
            return set()

        return set(
            df[coluna_id]
            .apply(_normalizar_id)
            .tolist()
        )
    except Exception:
        return set()


# ======================================================
# ESCRITA INCREMENTAL (APPEND)
# ======================================================
def append_aba(planilha: str, aba: str, df: pd.DataFrame):
    """
    Adiciona linhas no final da aba SEM apagar o conteúdo existente
    ✅ MANTÉM VALORES NUMÉRICOS COMO NÚMEROS
    """
    if df.empty:
        return

    sh = abrir_planilha(planilha)

    try:
        ws = sh.worksheet(aba)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=aba, rows=1000, cols=20)
        ws.append_row(df.columns.tolist())

    # ✅ CONVERTE PARA LISTA PRESERVANDO TIPOS
    # Números ficam como números, strings como strings
    valores = []
    for _, row in df.iterrows():
        linha = []
        for val in row:
            # Se for número, manda como número
            if pd.notna(val) and isinstance(val, (int, float)):
                linha.append(val)
            # Se for NaN/None, manda string vazia
            elif pd.isna(val):
                linha.append("")
            # Resto como string
            else:
                linha.append(str(val))
        valores.append(linha)

    ws.append_rows(
        valores,
        value_input_option="USER_ENTERED"  # Deixa Sheets interpretar tipos
    )


# ======================================================
# ESCRITA TOTAL (SOBRESCREVER)
# ======================================================
def escrever_aba(planilha: str, aba: str, df: pd.DataFrame):
    """
    SOBRESCREVE a aba inteira
    ✅ MANTÉM VALORES NUMÉRICOS COMO NÚMEROS
    """
    sh = abrir_planilha(planilha)

    try:
        ws = sh.worksheet(aba)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=aba, rows=1000, cols=20)

    ws.clear()
    
    # ✅ CONVERTE PARA LISTA PRESERVANDO TIPOS
    valores = [df.columns.tolist()]
    for _, row in df.iterrows():
        linha = []
        for val in row:
            if pd.notna(val) and isinstance(val, (int, float)):
                linha.append(val)
            elif pd.isna(val):
                linha.append("")
            else:
                linha.append(str(val))
        valores.append(linha)
    
    ws.update(
        valores,
        value_input_option="USER_ENTERED"
    )
