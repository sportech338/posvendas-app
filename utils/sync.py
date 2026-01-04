import pandas as pd


def gerar_clientes(df_pedidos: pd.DataFrame) -> pd.DataFrame:
    if df_pedidos.empty:
        return pd.DataFrame()

    df_pedidos["Data de criação"] = pd.to_datetime(df_pedidos["Data de criação"])

    agrupado = df_pedidos.groupby("Customer ID").agg(
        Cliente=("Cliente", "first"),
        Email=("Email", "first"),
        Qtd_Pedidos=("Pedido ID", "count"),
        Valor_Total_Gasto=("Valor Total", "sum"),
        Primeira_Compra=("Data de criação", "min"),
        Ultima_Compra=("Data de criação", "max"),
    ).reset_index()

    return agrupado
