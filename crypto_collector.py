import requests
from datetime import datetime

def obter_historico_coingecko(coin_id="bitcoin", vs_currency="usd", days="30"):
    """
    Busca o histórico de preços da CoinGecko para treinamento do seu modelo.
    Retorna arrays com [timestamp_milissegundos, preco].
    """
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    params = {
        "vs_currency": vs_currency,
        "days": days
    }
    print(f"Buscando histórico de {days} dias para {coin_id} na CoinGecko...")
    response = requests.get(url, params=params)
    
    if response.status_code == 200:
        dados = response.json()
        precos = dados.get("prices", [])
        print(f"Sucesso! {len(precos)} registros diários/horários encontrados.\n")
        return precos
    else:
        print(f"Erro na CoinGecko: {response.status_code} - {response.text}\n")
        return None

def obter_klines_binance(symbol="BTCUSDT", interval="5m", limit=5):
    """
    Busca os candlesticks (Klines) recentes da Binance.
    Intervalos solicitados: '5m', '15m', '1h'
    """
    url = "https://api.binance.com/api/v3/klines"
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    }
    print(f"Buscando Klines da Binance ({symbol}) no intervalo de {interval}...")
    response = requests.get(url, params=params)
    
    if response.status_code == 200:
        klines = response.json()
        
        resultado = []
        for kline in klines:
            timestamp_abertura = kline[0]
            abertura = kline[1]
            maxima = kline[2]
            minima = kline[3]
            fechamento = kline[4]
            volume = kline[5]
            
            data_legivel = datetime.fromtimestamp(timestamp_abertura / 1000).strftime('%Y-%m-%d %H:%M:%S')
            resultado.append({
                "data": data_legivel,
                "abertura": abertura,
                "maxima": maxima,
                "minima": minima,
                "fechamento": fechamento,
                "volume": volume
            })
        print(f"Sucesso! {len(resultado)} Candles obtidos.")
        return resultado
    else:
        print(f"Erro na Binance: {response.status_code} - {response.text}\n")
        return None

if __name__ == "__main__":
    # 1. Testando CoinGecko (Histórico)
    historico = obter_historico_coingecko(coin_id="bitcoin", vs_currency="usd", days="30")
    
    print("-" * 50)
    
    # 2. Testando Binance (Momento Atual nos ranges solicitados)
    intervalos = ["5m", "15m", "1h"]
    
    for intervalo in intervalos:
        # Pegando apenas as 2 últimas velas de cada tempo gráfico para o teste não ficar longo
        klines = obter_klines_binance(symbol="BTCUSDT", interval=intervalo, limit=2)
        
        if klines:
            for k in klines:
                print(f"[{intervalo}] Data: {k['data']} | Abert: {k['abertura']} | Fecham: {k['fechamento']}")
        print("-" * 50)
