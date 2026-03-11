"""
╔══════════════════════════════════════════════════════════════════╗
║     ESTRATÉGIA VEGA — MOMENTUM BREAKOUT ENGINE                 ║
║     Descartando reversões e focando em explosões institucionais║
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

# ALVO REALISTA PARA BREAKOUTS EM 15M
PERFIL = {"tp": 1.035, "sl": 0.980, "expiry": 48}  # TP +3.5%, SL -2.0%, Timeout 12h

JANELA = 200

def obter_historico(symbol, interval="15m", dias=30):
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

def detectar_vega(janela_df):
    """
    A GRANDE VERDADE SOBRE PUMPS NO 15M:
    Pumps reais não acontecem porque os indicadores estão sobrevendidos (isso é reversão à média, lento).
    Pumps reais acontecem por MOMENTUM: fuga institucional de caixotes com volume extremo a favor da tendência.
    """
    if len(janela_df) < JANELA: return None
    
    close = janela_df["close"]
    vol = janela_df["volume"]
    
    # 1. TENDÊNCIA MACRO OBRIGATÓRIA (Filtrando as facadas caindo)
    ema50 = close.ewm(span=50, adjust=False).mean()
    ema200 = close.ewm(span=200, adjust=False).mean()
    
    i = -1
    
    # Must be in an uptrend
    if not (ema50.iloc[i] > ema200.iloc[i] and close.iloc[i] > ema50.iloc[i]):
        return None

    # 2. BREAKOUT DA MÁXIMA DE 10 HORAS (Donchian Channel Breakout)
    # Busca o rompimento do teto das últimas 40 velas (40 * 15m = 10 horas)
    highest_high_40 = janela_df["high"].iloc[-41:-1].max()
    
    if close.iloc[i] <= highest_high_40:
        return None # Não rompeu resistência
        
    # 3. ANOMALIA DE VOLUME INSTITUCIONAL
    # Volume da vela atual deve ser pelo menos 2.5x a média de volume das últimas 40 velas
    vol_sma_40 = vol.iloc[-41:-1].mean()
    if vol.iloc[i] < (2.5 * vol_sma_40):
        return None # Rompeu sem força financeira
        
    # 4. MOMENTUM POSITIVO (RSI Acima de 60)
    # Em estratégias de breakout, RSI alto significa força, não fraqueza. Veta moedas fracas.
    rsi_s = rsi(close)
    if rsi_s.iloc[i] < 60:
        return None

    return {"preco": close.iloc[i], "rsi": rsi_s.iloc[i], "vol_ratio": vol.iloc[i] / vol_sma_40}

def simular_trade(df_futuro, p_in, perfil):
    tp, sl = p_in * perfil["tp"], p_in * perfil["sl"]
    for i in range(min(perfil["expiry"], len(df_futuro))):
        if df_futuro.iloc[i]["high"] >= tp: return "WIN", (tp/p_in-1)*100
        if df_futuro.iloc[i]["low"]  <= sl: return "LOSS", (sl/p_in-1)*100
    pf = df_futuro.iloc[min(perfil["expiry"]-1, len(df_futuro)-1)]["close"]
    return "TIMEOUT", (pf/p_in-1)*100

def backtest_vega():
    print("\n╔═════════════════════════════════════════════════════╗")
    print("║   ESTRATÉGIA VEGA: MOMENTUM & BREAKOUT              ║")
    print(f"║   Início: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                       ║")
    print("╚═════════════════════════════════════════════════════╝\n")
    
    res = {"WIN":0, "LOSS":0, "TIMEOUT":0, "ret_pct": []}
    sinais_totais = 0
    trades_log = []

    for symbol in PARES_BACKTEST:
        print(f"  ⬇️  Baixando {symbol} (30 dias)...", end=" ", flush=True)
        df = obter_historico(symbol, "15m", 30)
        if df is None or len(df) < JANELA + PERFIL["expiry"] + 10:
            print("PULADO")
            continue
            
        trades = 0
        cooldown = 0
        for i in range(JANELA, len(df) - PERFIL["expiry"] - 1):
            if cooldown > 0:
                cooldown -= 1
                continue
            sinal = detectar_vega(df.iloc[i - JANELA: i + 1])
            if not sinal: continue
            
            df_swing = df.iloc[i+1: i + 1 + PERFIL["expiry"]]
            rs, ret = simular_trade(df_swing, sinal["preco"], PERFIL)
            res[rs] += 1
            res["ret_pct"].append(ret)
            
            trades_log.append({
                "symbol": symbol, "data": df.index[i].strftime("%Y-%m-%d %H:%M"),
                "rs": rs, "ret": ret, "rsi": sinal["rsi"], "volx": sinal["vol_ratio"]
            })
            trades += 1
            cooldown = 15 # Congela por quase 4h após um sinal para evitar metralhadora no mesmo breakout
            
        sinais_totais += trades
        print(f"✅ {trades} sinais")

    print(f"\n{'═'*70}")
    print(f"  📊 RESULTADO VEGA (Momentum Breakout)")
    print(f"     TP +3.5% | SL -2.0% | Expira em 12h")
    print(f"{'═'*70}")
    
    if sinais_totais == 0:
        print("Nenhum sinal encontrado.")
        return
        
    s_W, s_L, s_T = res["WIN"], res["LOSS"], res["TIMEOUT"]
    s_ret = np.mean(res["ret_pct"])

    print(f"  {'✅ WINS':<20} | {s_W:>4} ({s_W/sinais_totais*100:4.1f}%)")
    print(f"  {'❌ LOSSES':<20} | {s_L:>4} ({s_L/sinais_totais*100:4.1f}%)")
    print(f"  {'⏳ TIMEOUTS':<20} | {s_T:>4} ({s_T/sinais_totais*100:4.1f}%)")
    print(f"  {'─'*45}")
    print(f"  {'🎯 TAXA DE ACERTO':<20} | {s_W/sinais_totais*100:>20.1f}%")
    print(f"  {'💰 RETORNO MÉDIO':<20} | {s_ret:>20.2f}%")
    print(f"{'═'*70}\n")
    
    trades_df = pd.DataFrame(trades_log)
    if not trades_df.empty:
        print("  Detalhe omitido para mostrar apenas o sumário.")
            
if __name__ == "__main__":
    backtest_vega()
