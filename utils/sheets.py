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
# LEITURA
# ======================================================
def ler_aba(planilha: str, aba: str) -> pd.DataFrame:
    sh = abrir_planilha(planilha)
    ws = sh.worksheet(aba)
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
# ESCRITA INCREMENTAL (APPEND) — SEM get_all_values ❗
# ======================================================
def append_aba(planilha: str, aba: str, df: pd.DataFrame):
    """
    Adiciona linhas no final da aba SEM apagar o conteúdo existente
    (Pedidos Shopify / Pedidos Ignorados)
    """
    if df.empty:
        return

    sh = abrir_planilha(planilha)

    try:
        ws = sh.worksheet(aba)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=aba, rows=1000, cols=20)
        ws.append_row(df.columns.tolist())

    # ✅ Normaliza valores monetários pt-BR
    df = _normalizar_valores_ptbr(df)

    ws.append_rows(
        df.astype(str).values.tolist(),
        value_input_option="USER_ENTERED"
    )


# ======================================================
# ESCRITA TOTAL (SOBRESCREVER)
# ======================================================
def escrever_aba(planilha: str, aba: str, df: pd.DataFrame):
    """
    SOBRESCREVE a aba inteira
    (Clientes Shopify, se voltar a usar no futuro)
    """
    sh = abrir_planilha(planilha)

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
