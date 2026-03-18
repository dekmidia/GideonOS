"""
╔══════════════════════════════════════════════════════════════════╗
║     BACKTEST ESTRATÉGIA v2: EMA CROSS + RSI < 45               ║
║     Lógica: EMA 9 > EMA 20 AND RSI < 45                        ║
║     Saída: R:R 1:2 ou 24 candles timeout                        ║
╚══════════════════════════════════════════════════════════════════╝
"""

import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
import time

# ─────────────────────────────────────────────────
# CONFIGURAÇÃO
# ─────────────────────────────────────────────────
PARES_BACKTEST = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", 
    "LINKUSDT", "NEARUSDT", "AVAXUSDT", "ADAUSDT", 
    "DOGEUSDT"
]

TP_RR           = 2.0
EXPIRY_CANDLES  = 24
JANELA          = 200

# ─────────────────────────────────────────────────
# COLETA HISTÓRICA
# ─────────────────────────────────────────────────
def obter_historico(symbol, interval="15m", dias=30):
    url = "https://api.binance.com/api/v3/klines"
    fim    = int(datetime.now(timezone.utc).timestamp() * 1000)
    inicio = int((datetime.now(timezone.utc) - timedelta(days=dias)).timestamp() * 1000)
    todos, cursor = [], inicio
    while cursor < fim:
        try:
            resp = requests.get(url, params={
                "symbol": symbol, "interval": interval,
                "startTime": cursor, "endTime": fim, "limit": 1000
            }, timeout=15)
            if resp.status_code != 200: return None
            batch = resp.json()
            if not batch: break
            todos.extend(batch)
            cursor = batch[-1][0] + 1
            time.sleep(0.1)
        except: return None

    if not todos: return None
    df = pd.DataFrame(todos, columns=[
        "timestamp","open","high","low","close","volume",
        "close_time","qav","trades","taker_base","taker_quote","ignore"
    ])[["timestamp","open","high","low","close","volume"]].copy()
    for col in ["open","high","low","close","volume"]:
        df[col] = pd.to_numeric(df[col])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)
    return df

def rsi(series, p=14):
    d  = series.diff()
    ag = d.clip(lower=0).ewm(alpha=1/p, min_periods=p, adjust=False).mean()
    al = (-d.clip(upper=0)).ewm(alpha=1/p, min_periods=p, adjust=False).mean()
    return 100 - (100 / (1 + ag / al.replace(0, np.nan)))

# ─────────────────────────────────────────────────
# DETECTOR DE ESTRATÉGIA v2
# ─────────────────────────────────────────────────
def detectar_v2(df: pd.DataFrame) -> dict | None:
    if len(df) < JANELA: return None

    close = df["close"]
    ema9  = close.ewm(span=9, adjust=False).mean()
    ema20 = close.ewm(span=20, adjust=False).mean()
    rsi_v = rsi(close)

    i = -1 # vela atual

    # Regra: ema9 > ema20 AND rsi < 45
    if ema9.iloc[i] > ema20.iloc[i] and rsi_v.iloc[i] < 45:
        # Preço de Entrada
        preco = close.iloc[i]
        # Stop Loss fixo de 1.5% para este backtest rápido
        sl = preco * 0.985
        tp = preco * (1 + (0.015 * TP_RR)) # R:R 1:2
        
        return {
            "preco_entrada": preco,
            "sl": sl,
            "tp": tp,
            "rsi": rsi_v.iloc[i]
        }
    return None

# ─────────────────────────────────────────────────
# ENGINE
# ─────────────────────────────────────────────────
def simular_trade(df_futuro, entrada, tp, sl):
    for i in range(min(EXPIRY_CANDLES, len(df_futuro))):
        h = df_futuro.iloc[i]["high"]
        l = df_futuro.iloc[i]["low"]
        if h >= tp:
            return {"resultado": "WIN", "retorno": (tp/entrada-1)*100, "velas": i+1}
        if l <= sl:
            return {"resultado": "LOSS", "retorno": (sl/entrada-1)*100, "velas": i+1}
    cf = df_futuro.iloc[-1]["close"]
    return {"resultado": "TIMEOUT", "retorno": (cf/entrada-1)*100, "velas": EXPIRY_CANDLES}

def rodar_backtest():
    todos_trades = []
    for symbol in PARES_BACKTEST:
        print(f"  🔍 Analisando {symbol}...")
        df = obter_historico(symbol)
        if df is None: continue
        
        cooldown = 0
        for i in range(JANELA, len(df) - EXPIRY_CANDLES):
            if cooldown > 0:
                cooldown -= 1
                continue
                
            janela = df.iloc[i-JANELA:i+1]
            sinal = detectar_v2(janela)
            
            if sinal:
                futuro = df.iloc[i+1 : i+1+EXPIRY_CANDLES]
                res = simular_trade(futuro, sinal["preco_entrada"], sinal["tp"], sinal["sl"])
                res.update({
                    "symbol": symbol,
                    "data": df.index[i].strftime("%Y-%m-%d %H:%M"),
                    "entrada": round(sinal["preco_entrada"], 6),
                    "tp": round(sinal["tp"], 6),
                    "sl": round(sinal["sl"], 6),
                    "rsi": round(sinal["rsi"], 1)
                })
                todos_trades.append(res)
                cooldown = 24 # Cooldown maior para evitar sinais sequenciais no mesmo movimento
                
    if not todos_trades:
        print("\n  ❌ Nenhum sinal encontrado.")
        return

    res_df = pd.DataFrame(todos_trades)
    print(f"\n{'═'*60}")
    print(f"  📊 RESULTADO BACKTEST v2: EMA 9/20 + RSI < 45")
    print(f"{'═'*60}")
    total = len(res_df)
    wins = len(res_df[res_df["resultado"]=="WIN"])
    wr = (wins/total)*100
    print(f"  Sinais Totais : {total}")
    print(f"  Taxa de Acerto: {wr:.1f}%")
    print(f"  Retorno Médio : {res_df['retorno'].mean():+.2f}%")
    
    res_df.to_csv("backtest_custom_v2_resultado.csv", index=False)
    print(f"\n  💾 Salvo em: backtest_custom_v2_resultado.csv")

if __name__ == "__main__":
    rodar_backtest()
