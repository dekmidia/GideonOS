"""
╔══════════════════════════════════════════════════════════════════╗
║     BACKTEST ESTRATÉGIA CUSTOM: SUPORTE + RSI + MACD           ║
║     Lógica: Preço em suporte (EMA 9/20) + RSI (30-45) + MACD    ║
║     Saída: R:R 1:2 ou 24 candles timeout                        ║
╚══════════════════════════════════════════════════════════════════╝
"""

import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
import time
import os

# ─────────────────────────────────────────────────
# CONFIGURAÇÃO
# ─────────────────────────────────────────────────
PARES_BACKTEST = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", 
    "LINKUSDT", "NEARUSDT", "AVAXUSDT", "ADAUSDT", 
    "DOGEUSDT"
]

TP_RR           = 2.0    # Risk/Reward Ratio
EXPIRY_CANDLES  = 24     # 6 horas no timeframe de 15m
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

# ─────────────────────────────────────────────────
# INDICADORES & ANALYZER
# ─────────────────────────────────────────────────
class CandleAnalyzer:
    @staticmethod
    def is_hammer(o, h, l, c):
        corpo = abs(c - o)
        pavio_inf = min(o, c) - l
        pavio_sup = h - max(o, c)
        return (pavio_inf >= 2 * corpo) and (pavio_sup <= corpo * 0.5) and corpo > 0

    @staticmethod
    def is_engulfing_bullish(o1, c1, o2, c2):
        return (c1 < o1) and (c2 > o2) and (o2 <= c1) and (c2 >= o1)

def rsi(series, p=14):
    d  = series.diff()
    ag = d.clip(lower=0).ewm(alpha=1/p, min_periods=p, adjust=False).mean()
    al = (-d.clip(upper=0)).ewm(alpha=1/p, min_periods=p, adjust=False).mean()
    return 100 - (100 / (1 + ag / al.replace(0, np.nan)))

def macd(series, fast=12, slow=26, signal=9):
    ema_f = series.ewm(span=fast, adjust=False).mean()
    ema_s = series.ewm(span=slow, adjust=False).mean()
    m_line = ema_f - ema_s
    s_line = m_line.ewm(span=signal, adjust=False).mean()
    return m_line, s_line

# ─────────────────────────────────────────────────
# DETECTOR DE ESTRATÉGIA
# ─────────────────────────────────────────────────
def detectar_estratégia(df: pd.DataFrame) -> dict | None:
    if len(df) < JANELA: return None

    close = df["close"]
    ema9  = close.ewm(span=9, adjust=False).mean()
    ema20 = close.ewm(span=20, adjust=False).mean()
    rsi_v = rsi(close)
    macd_l, macd_s = macd(close)

    i = -1 # vela atual
    prev = -2 # vela anterior

    # 1. EMA 9/20 Apoio e Tendência
    tendencia_alta = ema9.iloc[i] > ema20.iloc[i]
    testando_suporte = (df["low"].iloc[i] <= ema9.iloc[i] * 1.002)

    # 2. RSI subindo de região baixa (30-46)
    rsi_regiao_baixa = (30 <= rsi_v.iloc[prev] <= 46)
    rsi_subindo = rsi_v.iloc[i] > rsi_v.iloc[prev]

    # 3. MACD cruzando para cima
    macd_cross = (macd_l.iloc[i] > macd_s.iloc[i]) and (macd_l.iloc[prev] <= macd_s.iloc[prev])

    # 4. Candle de reversão
    o, h, l, c = df["open"].iloc[i], df["high"].iloc[i], df["low"].iloc[i], df["close"].iloc[i]
    o1, c1 = df["open"].iloc[prev], df["close"].iloc[prev]
    
    is_rev = CandleAnalyzer.is_hammer(o, h, l, c) or CandleAnalyzer.is_engulfing_bullish(o1, c1, o, c)

    if tendencia_alta and testando_suporte and rsi_regiao_baixa and rsi_subindo and macd_cross and is_rev:
        # Previsão de Stop Loss: Mínima dos últimos 2 candles ou 0.5% abaixo da EMA 20
        sl_fixo = close.iloc[i] * 0.985 # Fallback de 1.5%
        sl_variável = min(df["low"].iloc[i], df["low"].iloc[prev]) * 0.998
        sl_final = max(sl_variável, sl_fixo) # Não queremos um stop absurdo
        
        risco = close.iloc[i] - sl_final
        if risco <= 0: return None
        
        alvo = close.iloc[i] + (risco * TP_RR)
        
        return {
            "preco_entrada": close.iloc[i],
            "sl": sl_final,
            "tp": alvo,
            "rsi": rsi_v.iloc[i],
            "candle": "Hammer" if CandleAnalyzer.is_hammer(o, h, l, c) else "Engulfing"
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
            sinal = detectar_estratégia(janela)
            
            if sinal:
                futuro = df.iloc[i+1 : i+1+EXPIRY_CANDLES]
                res = simular_trade(futuro, sinal["preco_entrada"], sinal["tp"], sinal["sl"])
                res.update({
                    "symbol": symbol,
                    "data": df.index[i].strftime("%Y-%m-%d %H:%M"),
                    "entrada": round(sinal["preco_entrada"], 6),
                    "tp": round(sinal["tp"], 6),
                    "sl": round(sinal["sl"], 6),
                    "rsi": round(sinal["rsi"], 1),
                    "pattern": sinal["candle"]
                })
                todos_trades.append(res)
                cooldown = 12
                
    if not todos_trades:
        print("\n  ❌ Nenhum sinal encontrado com estas regras.")
        return

    res_df = pd.DataFrame(todos_trades)
    print(f"\n{'═'*60}")
    print(f"  📊 RESULTADO BACKTEST: SUPORTE + RSI + MACD")
    print(f"{'═'*60}")
    total = len(res_df)
    wins = len(res_df[res_df["resultado"]=="WIN"])
    wr = (wins/total)*100
    print(f"  Sinais Totais : {total}")
    print(f"  Taxa de Acerto: {wr:.1f}%")
    print(f"  Retorno Médio : {res_df['retorno'].mean():+.2f}%")
    print(f"  Padrão Hammer : {len(res_df[res_df['pattern']=='Hammer'])}")
    print(f"  Padrão Engolfo: {len(res_df[res_df['pattern']=='Engulfing'])}")
    
    res_df.to_csv("backtest_custom_resultado.csv", index=False)
    print(f"\n  💾 Salvo em: backtest_custom_resultado.csv")

if __name__ == "__main__":
    rodar_backtest()
