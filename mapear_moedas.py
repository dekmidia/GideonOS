import requests
import json

def mapear():
    print("🔍 Obtendo moedas da Binance...")
    binance = requests.get('https://api.binance.com/api/v3/exchangeInfo').json()
    binance_symbols = {s['symbol'] for s in binance['symbols'] if s['status'] == 'TRADING' and s['quoteAsset'] == 'USDT'}
    
    print("🔍 Obtendo moedas da BingX...")
    bingx = requests.get('https://open-api.bingx.com/openApi/spot/v1/common/symbols').json()
    bingx_symbols = {s['symbol'].replace('-', '') for s in bingx['data']['symbols']}
    
    comuns = list(binance_symbols.intersection(bingx_symbols))
    comuns.sort()
    
    print(f"✅ Encontradas {len(comuns)} moedas comuns.")
    
    with open('moedas_comuns.json', 'w') as f:
        json.dump(comuns, f)
    
    print("📄 Lista salva em moedas_comuns.json")

if __name__ == "__main__":
    mapear()
