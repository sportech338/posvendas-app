import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials


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


def ler_aba(planilha, aba):
    client = conectar_google_sheets()
    ws = client.open(planilha).worksheet(aba)
    return pd.DataFrame(ws.get_all_records())


def escrever_aba(planilha, aba, df: pd.DataFrame):
    client = conectar_google_sheets()
    sh = client.open(planilha)

    try:
        ws = sh.worksheet(aba)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=aba, rows=1000, cols=20)

    ws.clear()
    ws.update([df.columns.tolist()] + df.values.tolist())
