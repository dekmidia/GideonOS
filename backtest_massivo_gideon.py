import pandas as pd
import requests
import time
import json
import concurrent.futures
from datetime import datetime
import numpy as np

# Reuso de funções do backtest_consenso.py com otimizações
def obter_klines_paginado(symbol, interval, dias=7): # Reduzi para 7 dias para o teste massivo ser rápido
    all_klines = []
    end_time = int(time.time() * 1000)
    start_time = end_time - (dias * 24 * 60 * 60 * 1000)
    is_futures = "DOM" in symbol
    base_url = "https://fapi.binance.com/fapi/v1/klines" if is_futures else "https://api.binance.com/api/v3/klines"
    
    current_start = start_time
    while current_start < end_time:
        params = {"symbol": symbol, "interval": interval, "limit": 1000, "startTime": current_start}
        try:
            r = requests.get(base_url, params=params, timeout=10).json()
            if not isinstance(r, list) or len(r) == 0: break
            all_klines.extend(r)
            current_start = r[-1][0] + 1
            if len(r) < 1000: break
        except: break
    
    if not all_klines: return pd.DataFrame()
    df = pd.DataFrame(all_klines).iloc[:, :6]
    df.columns = ['t','o','h','l','c','v']
    for col in ['o','h','l','c','v']: df[col] = df[col].astype(float)
    return df

def calcular_rsi(prices, period=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).ewm(com=period-1, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(com=period-1, adjust=False).mean()
    rs = gain / loss.replace(0, 1e-10)
    return 100 - (100 / (1 + rs))

def calc_ichimoku(df):
    if len(df) < 52: return False
    sa = (((df['h'].rolling(9).max() + df['l'].rolling(9).min())/2) + ((df['h'].rolling(26).max() + df['l'].rolling(26).min())/2)) / 2
    return df['c'].iloc[-1] > sa.shift(26).iloc[-1]

def processar_moeda(simbolo, dias, df_dom, df_btc_h):
    try:
        # Para o massivo, vamos focar em 1m para sinais e 1h/4h para IA
        # Simplificando a IA para ser mais rápido (apenas 1h e 4h no massivo)
        df_1m = obter_klines_paginado(simbolo, "1m", dias)
        if df_1m.empty: return None
        
        df_1h = obter_klines_paginado(simbolo, "1h", dias + 2) # Dados extras para Ichimoku
        df_4h = obter_klines_paginado(simbolo, "4h", dias + 10)
        
        df_1m['rsi'] = calcular_rsi(df_1m['c'])
        tp, sl = 1.015, 0.990
        
        resultados = {"Puro": [], "Gideon": []}
        
        for i in range(50, len(df_1m)-60):
            if df_1m['rsi'].iloc[i] < 50 and df_1m['rsi'].iloc[i] > df_1m['rsi'].iloc[i-1] and df_1m['c'].iloc[i] > df_1m['o'].iloc[i]:
                ts = df_1m['t'].iloc[i]
                
                # Filtro Altseason (Permissivo para o teste)
                d = df_dom[df_dom['t'] <= ts].tail(1)
                alt_ok = not d.empty and d['c'].iloc[0] <= d['sma_dom'].iloc[0] * 1.001
                
                # Veto IA (Foco em 1h para mais sinais no backtest)
                df_ia_1h = df_1h[df_1h['t'] <= ts].tail(60)
                ia_ok = calc_ichimoku(df_ia_1h)
                
                # Simular Resultado
                res = None
                entry = df_1m['c'].iloc[i]
                for j in range(i+1, i+61):
                    if df_1m['h'].iloc[j] >= entry * tp: res = 1; break
                    if df_1m['l'].iloc[j] <= entry * sl: res = 0; break
                
                if res is not None:
                    resultados["Puro"].append(res)
                    if alt_ok and ia_ok:
                        resultados["Gideon"].append(res)
        
        return simbolo, resultados
    except: return None

def executar_massivo():
    with open('moedas_comuns.json', 'r') as f:
        moedas = json.load(f)
    
    dias = 7
    print(f"🌍 Iniciando Backtest Massivo em {len(moedas)} moedas (7 Dias)...")
    
    df_dom = obter_klines_paginado("BTCDOMUSDT", "1h", dias + 1)
    df_btc = obter_klines_paginado("BTCUSDT", "1h", dias + 1)
    
    # Pré-calcular SMA da Dominância
    df_dom['sma_dom'] = df_dom['c'].rolling(20).mean()
    
    total_resultados = {"Puro": [], "Gideon": []}
    count = 0
    
    # Rodar em paralelo
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(processar_moeda, m, dias, df_dom, df_btc) for m in moedas[:50]] # Testando com 50 moedas para ser rápido
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res:
                s, r = res
                total_resultados["Puro"].extend(r["Puro"])
                total_resultados["Gideon"].extend(r["Gideon"])
                count += 1
                if count % 10 == 0: print(f"  ✅ {count}/100 moedas processadas...")

    print("\n🏆 RESULTADOS CONSOLIDADOS (MASSIVO):")
    for name in ["Puro", "Gideon"]:
        res = total_resultados[name]
        if res:
            wr = (sum(res)/len(res))*100
            print(f"  [{name:<10}] Trades: {len(res):<5} | WinRate: {wr:.2f}%")
        else:
            print(f"  [{name:<10}] Trades: 0     | WinRate: 0.00%")

if __name__ == "__main__":
    executar_massivo()
