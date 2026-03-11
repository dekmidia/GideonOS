"""
╔══════════════════════════════════════════════════════════════════╗
║     SWING TRADE ENGINE (Vega Breakout + User Risk Framework)   ║
║     TP 10% | SL 5% | Condição de Ouro: Alta 24h entre 10% e 20%║
╚══════════════════════════════════════════════════════════════════╝
"""
import requests, time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone

PARES_BACKTEST = [
    "SOLUSDT", "LINKUSDT", "DOGEUSDT", "NEARUSDT",
    "APTUSDT",  "AVAXUSDT", "DOTUSDT",  "XRPUSDT",
    "ATOMUSDT", "INJUSDT",  "SEIUSDT",  "TIAUSDT",
]

# PERFIL SWING (FRAMEWORK DO USUÁRIO)
SWING = {
    "tp": 1.10,      # Win 10%
    "sl": 0.95,      # Loss 5%
    "expiry": 672,   # 4 semanas (28 dias) 
}

JANELA = 200

def obter_historico(symbol, interval, dias):
    url    = "https://api.binance.com/api/v3/klines"
    fim    = int(datetime.now(timezone.utc).timestamp() * 1000)
    inicio = int((datetime.now(timezone.utc) - timedelta(days=dias)).timestamp() * 1000)
    todos, cursor = [], inicio
    while cursor < fim:
        resp = requests.get(url, params={"symbol": symbol, "interval": interval, "startTime": cursor, "endTime": fim, "limit": 1000}, timeout=15)
        if resp.status_code != 200: return None
        batch = resp.json()
        if not batch: break
        todos.extend(batch)
        cursor = batch[-1][0] + 1
        time.sleep(0.12)
    if not todos: return None
    df = pd.DataFrame(todos, columns=["timestamp","open","high","low","close","volume","close_time","qav","trades","taker_base","taker_quote","ignore"])[["timestamp","open","high","low","close","volume"]].copy()
    for col in ["open","high","low","close","volume"]: df[col] = pd.to_numeric(df[col])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.drop_duplicates(subset="timestamp", inplace=True)
    df.set_index("timestamp", inplace=True)
    return df

def rsi(series, p=14):
    d  = series.diff()
    ag = d.clip(lower=0).ewm(alpha=1/p, min_periods=p, adjust=False).mean()
    al = (-d.clip(upper=0)).ewm(alpha=1/p, min_periods=p, adjust=False).mean()
    return 100 - (100 / (1 + ag / al.replace(0, np.nan)))

def detectar_swing(janela_df, interval):
    if len(janela_df) < JANELA: return None
    
    close = janela_df["close"]
    vol = janela_df["volume"]
    i = -1
    
    # REGRA DE OURO DO USUÁRIO: Alta nas últimas 24H entre 10% e 20%
    candles_24h = 24 if interval == "1h" else 6
    if len(janela_df) < candles_24h + 1: return None
    
    preco_24h_atras = close.iloc[i - candles_24h]
    variacao_24h = (close.iloc[i] / preco_24h_atras) - 1.0
    
    # Validando o range de +10% a +20%
    if not (0.10 <= variacao_24h <= 0.20):
        return None
    
    # 1. TENDÊNCIA MACRO
    ema50 = close.ewm(span=50, adjust=False).mean()
    ema200 = close.ewm(span=200, adjust=False).mean()
    
    if not (ema50.iloc[i] > ema200.iloc[i] and close.iloc[i] > ema50.iloc[i]):
        return None

    # 2. BREAKOUT DE TOPO (Canal de Donchian de ~10 candles no swing)
    highest_high = janela_df["high"].iloc[-11:-1].max()
    if close.iloc[i] <= highest_high:
        return None
        
    # 3. ANOMALIA DE VOLUME INSTITUCIONAL
    vol_sma_10 = vol.iloc[-11:-1].mean()
    if vol.iloc[i] < (2.0 * vol_sma_10):
        return None
        
    # 4. MOMENTUM POSITIVO (RSI)
    rsi_s = rsi(close)
    if rsi_s.iloc[i] < 60:
        return None

    return {"preco": close.iloc[i], "var_24h": variacao_24h*100}

def simular_trade(df_futuro, p_in, perfil):
    tp, sl = p_in * perfil["tp"], p_in * perfil["sl"]
    for j in range(len(df_futuro)):
        if df_futuro.iloc[j]["high"] >= tp: return "WIN", (tp/p_in-1)*100
        if df_futuro.iloc[j]["low"]  <= sl: return "LOSS", (sl/p_in-1)*100
    pf = df_futuro.iloc[-1]["close"]
    return "TIMEOUT", (pf/p_in-1)*100

def rodar_backtest_por_intervalo(interval, dias_historico):
    print(f"\n╔═════════════════════════════════════════════════════╗")
    print(f"║   SWING TRADE ENGINE — GRÁFICO {interval.upper():<20} ║")
    print(f"║   RISCO: WIN 10% | LOSS 5%                          ║")
    print(f"║   FILTRO: +10% a +20% variação nas últimas 24H      ║")
    print(f"╚═════════════════════════════════════════════════════╝\n")
    
    res = {"WIN":0, "LOSS":0, "TIMEOUT":0, "ret_pct": []}
    sinais_totais = 0
    trades_log = []
    
    if interval == "1h":
        expiry_candles = 28 * 24 # 4 semanas em horas
    else:
        expiry_candles = 28 * 6  # 4 semanas em 4h

    for symbol in PARES_BACKTEST:
        print(f"  ⬇️  Baixando {symbol} ({dias_historico} dias, {interval})...", end=" ", flush=True)
        df = obter_historico(symbol, interval, dias_historico)
        if df is None or len(df) < JANELA + expiry_candles + 10:
            print("PULADO (Pouco histórico)")
            continue
            
        trades = 0
        cooldown = 0
        
        for i in range(JANELA, len(df) - expiry_candles - 1):
            if cooldown > 0:
                cooldown -= 1
                continue

            sinal = detectar_swing(df.iloc[i - JANELA: i + 1], interval)
            if not sinal: continue
            
            df_swing = df.iloc[i+1: i + 1 + expiry_candles]
            rs, ret = simular_trade(df_swing, sinal["preco"], SWING)
            res[rs] += 1
            res["ret_pct"].append(ret)
            
            trades_log.append({
                "symbol": symbol, "data": df.index[i].strftime("%Y-%m-%d %H:%M"),
                "rs": rs, "ret": ret, "var_24h": sinal["var_24h"]
            })
            trades += 1
            cooldown = 24 if interval == "1h" else 6 # Esperar 1 dia pós-sinal
            
        sinais_totais += trades
        print(f"✅ {trades} sinais")

    print(f"\n{'═'*70}")
    print(f"  📊 RESULTADO SWING ({interval.upper()})")
    print(f"{'═'*70}")
    
    if sinais_totais == 0:
        print("Nenhum sinal encontrado. O filtro de +10% a +20% em 24H é muito seletivo!")
    else:
        s_W, s_L, s_T = res["WIN"], res["LOSS"], res["TIMEOUT"]
        s_ret = np.mean(res["ret_pct"])

        print(f"  {'✅ WINS':<20} | {s_W:>4} ({s_W/sinais_totais*100:4.1f}%)")
        print(f"  {'❌ LOSSES':<20} | {s_L:>4} ({s_L/sinais_totais*100:4.1f}%)")
        print(f"  {'⏳ TIMEOUTS':<20} | {s_T:>4} ({s_T/sinais_totais*100:4.1f}%)")
        print(f"  {'─'*45}")
        print(f"  {'🎯 TAXA DE ACERTO':<20} | {s_W/(s_W+s_L)*100 if s_W+s_L > 0 else 0:>20.1f}% (descontando timeouts)")
        print(f"  {'💰 RETORNO MÉDIO':<20} | {s_ret:>20.2f}%")
        
        trades_df = pd.DataFrame(trades_log)
        if not trades_df.empty:
            print("\n  Detalhe dos Sinais Swing:")
            for r in trades_df.itertuples():
                ic = "✅" if r.rs=="WIN" else ("❌" if r.rs=="LOSS" else "⏳")
                print(f"  {r.symbol:<10} {r.data} {ic}{r.rs:<8} {r.ret:>+6.2f}% | Var24H {r.var_24h:>+5.1f}%")
    print(f"{'═'*70}\n")

if __name__ == "__main__":
    # Backtest 1H (90 dias de histórico)
    rodar_backtest_por_intervalo("1h", 90)
    
    # Backtest 4H (180 dias de histórico)
    rodar_backtest_por_intervalo("4h", 180)
