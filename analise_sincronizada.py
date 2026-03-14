import pandas as pd
import requests
import time
from datetime import datetime, timezone

def obter_klines(symbol, interval, start_str):
    # start_str deve ser em UTC para a API da Binance
    start_ts = int(datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).timestamp() * 1000)
    end_ts = start_ts + (15 * 60 * 60 * 1000) # 15 horas
    
    is_futures = "DOM" in symbol
    base_url = "https://fapi.binance.com/fapi/v1/klines" if is_futures else "https://api.binance.com/api/v3/klines"
    
    params = {"symbol": symbol, "interval": interval, "startTime": start_ts, "endTime": end_ts}
    try:
        r = requests.get(base_url, params=params, timeout=10).json()
        if not isinstance(r, list): return pd.DataFrame()
        df = pd.DataFrame(r).iloc[:, :6]
        df.columns = ['t','o','h','l','c','v']
        for col in ['o','h','l','c','v']: df[col] = df[col].astype(float)
        df['timestamp_utc'] = pd.to_datetime(df['t'], unit='ms')
        # Ajusta para Brasilia (UTC-3)
        df['timestamp_br'] = df['timestamp_utc'] - pd.Timedelta(hours=3)
        return df
    except: return pd.DataFrame()

def calcular_rsi(prices, period=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).ewm(com=period-1, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(com=period-1, adjust=False).mean()
    rs = gain / loss.replace(0, 1e-10)
    return 100 - (100 / (1 + rs))

def analisar_sincronizado():
    # 00:00 Brasilia do dia 14/03 = 03:00 UTC
    data_inicio_utc = "2026-03-14 03:00:00"
    log = ["Relatorio Sincronizado com TradingView (Brasilia UTC-3) - 14/03"]
    
    moedas = ["BTCUSDT", "SOLUSDT"]
    for m in moedas:
        log.append(f"\nVerificando {m}:")
        df = obter_klines(m, "15m", data_inicio_utc)
        if df.empty: continue
        
        df['rsi'] = calcular_rsi(df['c'])
        
        for i in range(1, len(df)):
            ts_br = df['timestamp_br'].iloc[i].strftime('%H:%M')
            rsi = df['rsi'].iloc[i]
            rsi_ant = df['rsi'].iloc[i-1]
            close = df['c'].iloc[i]
            open_p = df['o'].iloc[i]
            
            # Regra: RSI < 50, RSI subindo e Candle VERDE
            if rsi < 50 and rsi > rsi_ant and close > open_p:
                log.append(f"  [SINAL LONG] {ts_br}: RSI {rsi:.1f} + Candle Verde. [OK]")

    with open("resultado_sincronizado.txt", "w") as f:
        f.write("\n".join(log))
    print("Relatorio gerado em Brasilia: resultado_sincronizado.txt")

analisar_sincronizado()
