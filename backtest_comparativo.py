"""
╔══════════════════════════════════════════════════════════════════╗
║     CRYPTO PUMP — SCALPING vs SWING COMPARISON                 ║
║     Usa a detecção v2.1 e simula dois alvos simultaneamente    ║
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

# PERFIS DE TRADE
SCALPING = {"tp": 1.02, "sl": 0.985, "expiry": 20}  # TP +2%, SL -1.5%, Timeout 5h
SWING    = {"tp": 1.05, "sl": 0.970, "expiry": 96}  # TP +5%, SL -3.0%, Timeout 24h

JANELA       = 200
SCORE_MINIMO = 7
HORA_UTC_MIN = 5
HORA_UTC_MAX = 22

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

def mfi(df, p=14):
    tp  = (df["high"] + df["low"] + df["close"]) / 3
    rmf = tp * df["volume"]
    pos, neg = rmf.where(tp > tp.shift(1), 0), rmf.where(tp < tp.shift(1), 0)
    mfr = pos.rolling(p).sum() / neg.rolling(p).sum().replace(0, np.nan)
    return 100 - (100 / (1 + mfr))

def stochastic(df, k=14, d=3):
    lo, hi = df["low"].rolling(k).min(), df["high"].rolling(k).max()
    pk = (100 * (df["close"] - lo) / (hi - lo).replace(0, np.nan)).rolling(d).mean()
    return pk, pk.rolling(d).mean()

def squeeze(df, bb_p=20, bb_m=2.0, kc_p=20, kc_m=1.5):
    sma, std = df["close"].rolling(bb_p).mean(), df["close"].rolling(bb_p).std()
    bb_up, bb_lo = sma + bb_m * std, sma - bb_m * std
    tr = pd.concat([df["high"] - df["low"], (df["high"] - df["close"].shift()).abs(), (df["low"]  - df["close"].shift()).abs()], axis=1).max(axis=1)
    atr = tr.rolling(kc_p).mean()
    smakc = df["close"].rolling(kc_p).mean()
    kc_up, kc_lo = smakc + kc_m * atr, smakc - kc_m * atr
    sq_on = (bb_lo > kc_lo) & (bb_up < kc_up)
    mid = (df["high"].rolling(bb_p).max() + df["low"].rolling(bb_p).min()) / 2
    mom = (df["close"] - ((mid + sma) / 2)).rolling(bb_p).apply(lambda x: np.polyfit(range(len(x)), x, 1)[0], raw=True)
    return sq_on, mom

def macd_ind(series, fast=12, slow=26, signal=9):
    ef, es = series.ewm(span=fast, adjust=False).mean(), series.ewm(span=slow, adjust=False).mean()
    ml = ef - es
    return ml, ml.ewm(span=signal, adjust=False).mean(), ml - ml.ewm(span=signal, adjust=False).mean()

def detectar_v21(janela_df, hora_utc):
    if len(janela_df) < JANELA or not (HORA_UTC_MIN <= hora_utc <= HORA_UTC_MAX): return None
    close = janela_df["close"]
    rsi_s, mfi_s = rsi(close), mfi(janela_df)
    pctk, pctd = stochastic(janela_df)
    sq_on, mom = squeeze(janela_df)
    macd_l, macd_sig, macd_hist = macd_ind(close)
    ema9, sma20, ema200 = close.ewm(span=9, adjust=False).mean(), close.rolling(20).mean(), close.ewm(span=200, adjust=False).mean()
    vol_ma = janela_df["volume"].rolling(20).mean()
    i = -1

    sq_arr = sq_on.values
    sq_cons = 0
    for j in range(len(sq_arr) - 2, max(len(sq_arr) - 40, 0), -1):
        if sq_arr[j]: sq_cons += 1
        else: break
    
    if not ((not sq_on.iloc[i]) and sq_on.iloc[i-1]): return None

    c_base = {
        "Mom+": (mom.iloc[i] > 0) and (mom.iloc[i] > mom.iloc[i-1]),
        "E>S": ema9.iloc[i] > sma20.iloc[i],
        "R": 35 < rsi_s.iloc[i] < 68,
        "M": mfi_s.iloc[i] > 48,
        "S": (pctk.iloc[i] > pctd.iloc[i]) and (pctk.iloc[i] < 80),
        "V": janela_df["volume"].iloc[i] >= 1.2 * vol_ma.iloc[i],
        "E2": close.iloc[i] > ema200.iloc[i],
        "Sq": sq_cons >= 5,
    }
    
    rsi_lb, mfi_lb = rsi_s.iloc[-21:-1], mfi_s.iloc[-21:-1]
    oversold = (rsi_lb < 35).any() or (mfi_lb < 20).any()
    macd_c = (macd_l.iloc[i] > macd_sig.iloc[i] and macd_l.iloc[i-1] <= macd_sig.iloc[i-1])
    opens, closes = janela_df["open"].iloc[-4:-1], janela_df["close"].iloc[-4:-1]
    ignition = ((closes - opens) / opens >= 0.02).any()
    mom_f = (mom.iloc[i] > mom.iloc[i-1] > mom.iloc[i-2]) and (mom.iloc[i] > 0)
    
    c_bonus = {"O": oversold, "MC": macd_c, "I": ignition, "M3": mom_f}
    
    score = sum(1 for v in c_base.values() if v) + sum(2 for v in c_bonus.values() if v)
    if score < SCORE_MINIMO or score >= 16: return None
    return {"preco": close.iloc[i] * 1.003, "score": score}

def simular_trade(df_futuro, p_in, perfil):
    tp, sl = p_in * perfil["tp"], p_in * perfil["sl"]
    for i in range(min(perfil["expiry"], len(df_futuro))):
        h, l = df_futuro.iloc[i]["high"], df_futuro.iloc[i]["low"]
        if h >= tp: return "WIN", (tp/p_in-1)*100
        if l <= sl: return "LOSS", (sl/p_in-1)*100
    pf = df_futuro.iloc[min(perfil["expiry"]-1, len(df_futuro)-1)]["close"]
    return "TIMEOUT", (pf/p_in-1)*100

def backtest_comparativo():
    print("\n╔═════════════════════════════════════════════════════╗")
    print("║   BACKTEST COMPARATIVO — SCALPING vs SWING          ║")
    print(f"║   Início: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                       ║")
    print("╚═════════════════════════════════════════════════════╝\n")
    
    res_scalping = {"WIN":0, "LOSS":0, "TIMEOUT":0, "ret_pct": []}
    res_swing    = {"WIN":0, "LOSS":0, "TIMEOUT":0, "ret_pct": []}
    sinais_totais = 0

    for symbol in PARES_BACKTEST:
        print(f"  ⬇️  Baixando {symbol} (30 dias)...", end=" ", flush=True)
        df = obter_historico(symbol, "15m", 30)
        if df is None or len(df) < JANELA + SWING["expiry"] + 10:
            print("PULADO")
            continue
            
        trades = 0
        cooldown = 0
        for i in range(JANELA, len(df) - SWING["expiry"] - 1):
            if cooldown > 0:
                cooldown -= 1
                continue
            sinal = detectar_v21(df.iloc[i - JANELA: i], df.index[i].hour)
            if not sinal: continue
            
            # SCALPING Simulação
            df_scalp = df.iloc[i: i + SCALPING["expiry"] + 1]
            rs_s, ret_s = simular_trade(df_scalp, sinal["preco"], SCALPING)
            res_scalping[rs_s] += 1
            res_scalping["ret_pct"].append(ret_s)
            
            # SWING Simulação
            df_swing = df.iloc[i: i + SWING["expiry"] + 1]
            rs_w, ret_w = simular_trade(df_swing, sinal["preco"], SWING)
            res_swing[rs_w] += 1
            res_swing["ret_pct"].append(ret_w)
            
            trades += 1
            cooldown = 10
            
        sinais_totais += trades
        print(f"✅ {trades} sinais")

    # RELATÓRIO
    print(f"\n{'═'*70}")
    print(f"  📊 RESULTADO COMPARATIVO (Total Sinais idênticos: {sinais_totais})")
    print(f"{'═'*70}")
    
    if sinais_totais == 0:
        print("Nenhum sinal encontrado.")
        return
        
    s_W, s_L, s_T = res_scalping["WIN"], res_scalping["LOSS"], res_scalping["TIMEOUT"]
    w_W, w_L, w_T = res_swing["WIN"], res_swing["LOSS"], res_swing["TIMEOUT"]
    
    s_ret = np.mean(res_scalping["ret_pct"])
    w_ret = np.mean(res_swing["ret_pct"])

    print(f"  {'MÉTRICA':<20} | {'SCALPING (TP 2%, SL 1.5%)':<25} | {'SWING (TP 5%, SL 3%)'}")
    print(f"  {'─'*20} | {'─'*25} | {'─'*25}")
    print(f"  {'✅ WINS':<20} | {s_W:>4} ({s_W/sinais_totais*100:5.1f}%) {' ':>13} | {w_W:>4} ({w_W/sinais_totais*100:5.1f}%)")
    print(f"  {'❌ LOSSES':<20} | {s_L:>4} ({s_L/sinais_totais*100:5.1f}%) {' ':>13} | {w_L:>4} ({w_L/sinais_totais*100:5.1f}%)")
    print(f"  {'⏳ TIMEOUTS':<20} | {s_T:>4} ({s_T/sinais_totais*100:5.1f}%) {' ':>13} | {w_T:>4} ({w_T/sinais_totais*100:5.1f}%)")
    print(f"  {'─'*20} | {'─'*25} | {'─'*25}")
    print(f"  {'🎯 TAXA DE ACERTO':<20} | {s_W/sinais_totais*100:>24.1f}% | {w_W/sinais_totais*100:>19.1f}%")
    print(f"  {'💰 RETORNO MÉDIO':<20} | {s_ret:>24.2f}% | {w_ret:>19.2f}%")
    print(f"{'═'*70}\n")

if __name__ == "__main__":
    backtest_comparativo()
