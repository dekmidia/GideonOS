import pandas as pd
import requests
import time
from datetime import datetime, timezone

def obter_klines(symbol, interval, start_str):
    start_ts = int(datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).timestamp() * 1000)
    end_ts = start_ts + (12 * 60 * 60 * 1000) # 12 horas
    
    is_futures = "DOM" in symbol
    base_url = "https://fapi.binance.com/fapi/v1/klines" if is_futures else "https://api.binance.com/api/v3/klines"
    
    params = {"symbol": symbol, "interval": interval, "startTime": start_ts, "endTime": end_ts, "limit": 1000}
    r = requests.get(base_url, params=params).json()
    if not isinstance(r, list): return pd.DataFrame()
    
    df = pd.DataFrame(r).iloc[:, :6]
    df.columns = ['t','o','h','l','c','v']
    df['close'] = df['c'].astype(float)
    df['timestamp'] = pd.to_datetime(df['t'], unit='ms')
    return df

def analisar_manha_favoraveis():
    # Ajuste para Brasilia (UTC-3)
    # 00:00 Brasilia = 03:00 UTC
    data_alvo = "2026-03-14 03:00:00" 
    log = []
    log.append(f"Relatorio de Trades Favoraveis (Sincronizado Brasilia UTC-3) - 14/03")
    
    moedas = ["BTCUSDT", "SOLUSDT"]
    
    for m in moedas:
        log.append(f"\nVerificando {m} (Fuso do Print):")
        # 15m para bater com o print
        df = obter_klines(m, "15m", data_alvo)
        if df.empty: continue
        
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).ewm(com=13, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(com=13, adjust=False).mean()
        rs = gain / loss.replace(0, 1e-10)
        df['rsi'] = 100 - (100 / (1 + rs))

        for i in range(1, len(df)):
            # Aplicando a regra EXATA: RSI < 50, RSI subindo e Candle VERDE
            rsi_atual = df['rsi'].iloc[i]
            rsi_ant = df['rsi'].iloc[i-1]
            close = df['close'].iloc[i]
            abertura = df['open'].iloc[i]
            
            # Ajustando o TS para exibir em Brasilia no log
            ts_br = (df['timestamp'].iloc[i] - pd.Timedelta(hours=3)).strftime('%H:%M')
            
            if rsi_atual < 50 and rsi_atual > rsi_ant and close > abertura:
                log.append(f"  [LONG APROVADO] {ts_br}: RSI {rsi_atual:.1f} + Candle Verde. [OK]")

    with open("trades_favoraveis_v2.txt", "w") as f:
        f.write("\n".join(log))
    print("Relatorio gerado: trades_favoraveis_v2.txt")

analisar_manha_favoraveis()

    with open("trades_favoraveis_manha.txt", "w") as f:
        f.write("\n".join(log))
    print("Relatorio gerado: trades_favoraveis_manha.txt")

analisar_manha_favoraveis()
