# utils/config.py

import os
import json

def get_shopify_config():
    return {
        "shop_name": os.getenv("SHOPIFY_SHOP_NAME"),
        "access_token": os.getenv("SHOPIFY_ACCESS_TOKEN"),
        "api_version": os.getenv("SHOPIFY_API_VERSION"),
    }

def get_gcp_credentials():
    raw = os.getenv("GCP_SERVICE_ACCOUNT_JSON")
    if not raw:
        raise ValueError("GCP_SERVICE_ACCOUNT_JSON não definido")
    return json.loads(raw)
