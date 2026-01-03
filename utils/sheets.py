import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials

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

@st.cache_data(ttl=300)
def carregar_aba(nome_planilha, nome_aba):
    client = conectar_google_sheets()
    sheet = client.open(nome_planilha)
    ws = sheet.worksheet(nome_aba)

    dados = ws.get_all_records()
    return pd.DataFrame(dados)
