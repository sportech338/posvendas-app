# webhook_server.py

import os
from flask import Flask, request, jsonify
from datetime import datetime
import pandas as pd
import pytz

from utils.sheets import ler_aba, escrever_aba, append_aba
from utils.classificacao import agregar_por_cliente, calcular_estado

app = Flask(__name__)

PLANILHA = "Clientes Shopify"


@app.route("/webhooks/orders/paid", methods=["POST"])
def webhook_order_paid():
    """Recebe webhook quando um pedido é marcado como pago."""
    try:
        pedido_data = request.json
        pedido_id = str(pedido_data.get("id", ""))
        
        print(f"\n{'='*60}")
        print(f"🔔 NOVO PEDIDO PAGO: {pedido_id}")
        print(f"{'='*60}\n")
        
        # Extrair dados
        customer = pedido_data.get("customer", {})
        customer_id = str(customer.get("id", ""))
        
        if not customer_id or customer_id == "None":
            print(f"⚠️ Pedido {pedido_id} sem customer_id, ignorando...")
            return jsonify({"status": "skipped"}), 200
        
        # Verificar se já existe
        df_pedidos = ler_aba(PLANILHA, "Pedidos Shopify")
        
        if not df_pedidos.empty:
            if pedido_id in df_pedidos["Pedido ID"].astype(str).values:
                print(f"⚠️ Pedido {pedido_id} já existe!")
                return jsonify({"status": "duplicate"}), 200
        
        # Adicionar pedido
        nova_linha = pd.DataFrame([{
            "Pedido ID": pedido_id,
            "Customer ID": customer_id,
            "Cliente": f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip(),
            "Email": customer.get("email", ""),
            "Valor Total": float(pedido_data.get("total_price", 0)),
            "Data de criação": pedido_data.get("created_at", ""),
        }])
        
        append_aba(PLANILHA, "Pedidos Shopify", nova_linha)
        print(f"✅ Pedido {pedido_id} adicionado!")
        
        # Reagregar clientes
        print("🔄 Reagregando clientes...")
        df_pedidos = ler_aba(PLANILHA, "Pedidos Shopify")
        
        df_pedidos["Data de criação"] = (
            pd.to_datetime(df_pedidos["Data de criação"], errors="coerce", utc=True)
            .dt.tz_convert("America/Sao_Paulo")
            .dt.tz_localize(None)
        )
        
        df_clientes = agregar_por_cliente(df_pedidos)
        df_clientes = calcular_estado(df_clientes, threshold_risco=45, threshold_dormente=90)
        
        colunas_finais = [
            "Customer ID", "Cliente", "Email", "Qtd Pedidos", "Valor Total",
            "Primeiro Pedido", "Ultimo Pedido", "Dias sem comprar", "Estado", "Nível"
        ]
        
        df_clientes = df_clientes[colunas_finais]
        escrever_aba(PLANILHA, "Clientes Shopify", df_clientes)
        
        print(f"✅ {len(df_clientes)} clientes atualizados!")
        
        return jsonify({"status": "success"}), 200
        
    except Exception as e:
        print(f"❌ Erro: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/health", methods=["GET"])
def health():
    """Health check"""
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now(pytz.timezone("America/Sao_Paulo")).isoformat()
    }), 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"\n🚀 Servidor rodando na porta {port}")
    print(f"📍 Endpoint: http://localhost:{port}/webhooks/orders/paid\n")
    app.run(host="0.0.0.0", port=port, debug=False)
