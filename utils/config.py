# utils/config.py

import os
import json

def get_shopify_config():
    shop_name = access_token = api_version = None

    # 1️⃣ Streamlit Secrets (formato [shopify])
    try:
        import streamlit as st
        if "shopify" in st.secrets:
            shop_name = st.secrets["shopify"].get("shop_name")
            access_token = st.secrets["shopify"].get("access_token")
            api_version = (
                st.secrets["shopify"].get("api_version")
                or st.secrets["shopify"].get("API_VERSION")
            )
    except Exception:
        pass

    # 2️⃣ Fallback ENV (GitHub Actions / CRON)
    shop_name = shop_name or os.getenv("SHOPIFY_SHOP_NAME")
    access_token = access_token or os.getenv("SHOPIFY_ACCESS_TOKEN")
    api_version = api_version or os.getenv("SHOPIFY_API_VERSION")

    return {
        "shop_name": shop_name,
        "access_token": access_token,
        "api_version": api_version,
    }


def get_gcp_credentials():
    # 1️⃣ Streamlit secrets
    try:
        import streamlit as st
        if "gcp_service_account" in st.secrets:
            return dict(st.secrets["gcp_service_account"])
    except Exception:
        pass

    # 2️⃣ Fallback ENV (CRON / GitHub Actions)
    raw = os.getenv("GCP_SERVICE_ACCOUNT_JSON")
    if not raw:
        raise ValueError("GCP_SERVICE_ACCOUNT_JSON não definido")
    return json.loads(raw)
