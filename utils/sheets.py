# utils/sheets.py

import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials


# ======================================================
# CONEXÃO
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
# LEITURA
# ======================================================
def ler_aba(planilha: str, aba: str) -> pd.DataFrame:
    client = conectar_google_sheets()
    ws = client.open(planilha).worksheet(aba)
    return pd.DataFrame(ws.get_all_records())


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


def _normalizar_valores_ptbr(df: pd.DataFrame) -> pd.DataFrame:
    """
    Converte valores monetários para padrão pt-BR
    (96.9 -> 96,9) antes de enviar ao Google Sheets
    """
    df = df.copy()

    if "Valor Total" in df.columns:
        df["Valor Total"] = (
            df["Valor Total"]
            .astype(str)
            .str.replace(".", ",", regex=False)
        )

    return df


def ler_ids_existentes(planilha: str, aba: str, coluna_id: str) -> set:
    """
    Lê apenas a coluna de IDs para deduplicação
    (normaliza IDs vindos do Google Sheets)
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
    (usado para Pedidos Shopify)
    """
    if df.empty:
        return

    client = conectar_google_sheets()
    sh = client.open(planilha)

    try:
        ws = sh.worksheet(aba)
        existente = ws.get_all_values()
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=aba, rows=1000, cols=20)
        ws.append_row(df.columns.tolist())
        existente = []

    if not existente:
        ws.append_row(df.columns.tolist())

    # ✅ NORMALIZA VALORES PT-BR AQUI
    df = _normalizar_valores_ptbr(df)

    linhas = df.astype(str).values.tolist()
    ws.append_rows(linhas, value_input_option="USER_ENTERED")


# ======================================================
# ESCRITA TOTAL (SOBRESCREVER)
# ======================================================
def escrever_aba(planilha: str, aba: str, df: pd.DataFrame):
    """
    SOBRESCREVE a aba inteira
    (usado para Clientes Shopify — base derivada)
    """
    client = conectar_google_sheets()
    sh = client.open(planilha)

    try:
        ws = sh.worksheet(aba)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=aba, rows=1000, cols=20)

    ws.clear()
    ws.update(
        [df.columns.tolist()] +
        df.astype(str).values.tolist(),
        value_input_option="USER_ENTERED"
    )
