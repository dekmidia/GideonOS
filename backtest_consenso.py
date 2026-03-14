import pandas as pd
import requests
import time
from datetime import datetime, timedelta
import numpy as np

def obter_klines_paginado(symbol, interval, dias=15):
    """Busca dados históricos paginados da Binance (Spot ou Futuros)."""
    all_klines = []
    end_time = int(time.time() * 1000)
    start_time = end_time - (dias * 24 * 60 * 60 * 1000)
    
    # Determinar API (BTCDOMUSDT só existe em Futuros)
    is_futures = "DOM" in symbol
    base_url = "https://fapi.binance.com/fapi/v1/klines" if is_futures else "https://api.binance.com/api/v3/klines"
    
    print(f"  📥 Baixando {dias} dias de dados para {symbol} ({interval})...")
    
    current_start = start_time
    while current_start < end_time:
        params = {"symbol": symbol, "interval": interval, "limit": 1000, "startTime": current_start}
        try:
            r = requests.get(base_url, params=params, timeout=15).json()
            if not isinstance(r, list) or len(r) == 0: break
            all_klines.extend(r)
            current_start = r[-1][0] + 1
            if len(r) < 1000: break
            time.sleep(0.1)
        except: break
    
    if not all_klines:
        return pd.DataFrame()
            
    df = pd.DataFrame(all_klines)
    # Pegar apenas as colunas necessárias e converter
    df = df.iloc[:, :6]
    df.columns = ['t','o','h','l','c','v']
    df['close'] = df['c'].astype(float)
    df['open'] = df['o'].astype(float)
    df['high'] = df['h'].astype(float)
    df['low'] = df['l'].astype(float)
    df['timestamp'] = pd.to_datetime(df['t'], unit='ms')
    return df

def calcular_rsi(prices, period=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).ewm(com=period-1, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(com=period-1, adjust=False).mean()
    rs = gain / loss.replace(0, 1e-10)
    return 100 - (100 / (1 + rs))

def calc_ichimoku(df):
    if len(df) < 52: return False
    tenkan = (df['high'].rolling(9).max() + df['low'].rolling(9).min()) / 2
    kijun = (df['high'].rolling(26).max() + df['low'].rolling(26).min()) / 2
    sa = ((tenkan + kijun) / 2).shift(26)
    sb = ((df['high'].rolling(52).max() + df['low'].rolling(52).min()) / 2).shift(26)
    return df['close'].iloc[-1] > sa.iloc[-1]

def simular_raiox(ts, dfs_full):
    conf_score = 0
    weights = {'4h': 2.0, '1h': 1.8, '30m': 1.5, '15m': 1.5, '5m': 1.2, '1m': 0.8}
    total_w = sum(weights.values())
    
    for tf, w in weights.items():
        df_moment = dfs_full[tf][dfs_full[tf]['t'] <= ts].tail(60)
        if len(df_moment) < 52: continue
        if calc_ichimoku(df_moment):
            conf_score += w
            
    return (conf_score / total_w) * 100

def rodar_backtest(simbolo, dias=15):
    print(f"\n🚀 Backtest Gideon Sentinel: {simbolo} | {dias} Dias")
    
    # Baixar dados de Dominância e BTC para filtro de Altseason
    df_dom = obter_klines_paginado("BTCDOMUSDT", "1h", dias)
    df_btc_h = obter_klines_paginado("BTCUSDT", "1h", dias)
    
    # Calcular SMA 20 da Dominância
    df_dom['sma20'] = df_dom['close'].rolling(20).mean()
    df_btc_h['sma20'] = df_btc_h['close'].rolling(20).mean()

    def is_altseason(ts):
        # Verifica se na hora 'ts', a dominância estava abaixo da SMA 20
        d = df_dom[df_dom['t'] <= ts].tail(1)
        b = df_btc_h[df_btc_h['t'] <= ts].tail(1)
        if d.empty or b.empty: return True
        return d['close'].iloc[0] < d['sma20'].iloc[0] and b['close'].iloc[0] > (b['sma20'].iloc[0] * 0.995)

    # Baixar dados de todos os tempos
    dfs = {}
    for tf in ['1m', '5m', '15m', '30m', '1h', '4h']:
        dfs[tf] = obter_klines_paginado(simbolo, tf, dias)
    
    df_main = dfs['1m']
    df_main['rsi'] = calcular_rsi(df_main['close'])
    
    tp_pct, sl_pct = 1.015, 0.990 # 1.5% TP / 1.0% SL
    
    resultados = {"Puro": [], "Altseason": [], "VetoIA": []}
    
    print("  📊 Analisando sinais...")
    for i in range(100, len(df_main)-120):
        if df_main['rsi'].iloc[i] < 50 and df_main['rsi'].iloc[i] > df_main['rsi'].iloc[i-1] and df_main['close'].iloc[i] > df_main['open'].iloc[i]:
            
            entry_price = df_main['close'].iloc[i]
            ts = df_main['t'].iloc[i]
            
            alt_ok = is_altseason(ts)
            conf = simular_raiox(ts, dfs)
            veto_ia_ok = conf >= 35 
            
            res = None
            for j in range(i+1, i+121):
                if df_main['high'].iloc[j] >= entry_price * tp_pct: 
                    res = 1
                    break
                if df_main['low'].iloc[j] <= entry_price * sl_pct: 
                    res = 0
                    break
            
            if res is not None:
                resultados["Puro"].append(res)
                if alt_ok:
                    resultados["Altseason"].append(res)
                    if veto_ia_ok:
                        resultados["VetoIA"].append(res)

    def stats(name, res):
        if not res: return
        wr = (sum(res)/len(res))*100
        print(f"  ✅ [{name:<15}] Trades: {len(res):<4} | WinRate: {wr:.2f}%")

    stats("RSI PURO", resultados["Puro"])
    stats("RSI + ALTSEASON", resultados["Altseason"])
    stats("SISTEMA GIDEON", resultados["VetoIA"])

moedas = ["SOLUSDT", "ETHUSDT", "BTCUSDT"]
for m in moedas:
    rodar_backtest(m, 15)
