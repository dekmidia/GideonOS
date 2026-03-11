"""
╔══════════════════════════════════════════════════════════════════╗
║     DAY TRADE ENGINE (Vega Breakout + User Risk Framework)     ║
║     TP 1.5% | SL 1.0% | Max 5 Trades/dia | Trava em 3 Losses   ║
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

# PERFIL DAY TRADE (FRAMEWORK MESTRE)
DAY_TRADE = {
    "tp": 1.015,     # Win 1.5%
    "sl": 0.990,     # Loss 1.0%
    "expiry": 96,    # Limite até 24h para concretizar (4 * 24 = 96 de 15m)
    "max_trades": 5, # Máximo 5 operações / dia / par
    "max_losses": 3  # Parar se tiver 3 reds no mesmo dia
}

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
    """ Momentum Breakout """
    if len(janela_df) < JANELA: return None
    
    close = janela_df["close"]
    vol = janela_df["volume"]
    
    ema50 = close.ewm(span=50, adjust=False).mean()
    ema200 = close.ewm(span=200, adjust=False).mean()
    
    i = -1
    
    if not (ema50.iloc[i] > ema200.iloc[i] and close.iloc[i] > ema50.iloc[i]):
        return None

    highest_high_40 = janela_df["high"].iloc[-41:-1].max()
    if close.iloc[i] <= highest_high_40:
        return None
        
    vol_sma_40 = vol.iloc[-41:-1].mean()
    if vol.iloc[i] < (2.5 * vol_sma_40):
        return None
        
    rsi_s = rsi(close)
    if rsi_s.iloc[i] < 60:
        return None

    return {"preco": close.iloc[i], "rsi": rsi_s.iloc[i], "vol_ratio": vol.iloc[i]/vol_sma_40}

def simular_trade(df_futuro, p_in, perfil):
    tp, sl = p_in * perfil["tp"], p_in * perfil["sl"]
    for i in range(min(perfil["expiry"], len(df_futuro))):
        if df_futuro.iloc[i]["high"] >= tp: return "WIN", (tp/p_in-1)*100
        if df_futuro.iloc[i]["low"]  <= sl: return "LOSS", (sl/p_in-1)*100
    pf = df_futuro.iloc[min(perfil["expiry"]-1, len(df_futuro)-1)]["close"]
    return "TIMEOUT", (pf/p_in-1)*100

def backtest_daytrade():
    print("\n╔═════════════════════════════════════════════════════╗")
    print("║   DAY TRADE ENGINE — RISCO: WIN 1.5% | LOSS 1.0%    ║")
    print("║   LIMITE DA NUVEM: Max 5 trades ou 3 losses/dia     ║")
    print("╚═════════════════════════════════════════════════════╝\n")
    
    res = {"WIN":0, "LOSS":0, "TIMEOUT":0, "ret_pct": []}
    sinais_totais = 0
    trades_log = []

    for symbol in PARES_BACKTEST:
        print(f"  ⬇️  Baixando {symbol} (30 dias)...", end=" ", flush=True)
        df = obter_historico(symbol, "15m", 30)
        if df is None or len(df) < JANELA + DAY_TRADE["expiry"] + 10:
            print("PULADO")
            continue
            
        trades = 0
        cooldown = 0
        
        # Controle de Risco Diário
        dia_atual = None
        operacoes_dia = 0
        losses_dia = 0
        
        for i in range(JANELA, len(df) - DAY_TRADE["expiry"] - 1):
            if cooldown > 0:
                cooldown -= 1
                continue
                
            data_atual = df.index[i].date()
            if data_atual != dia_atual:
                dia_atual = data_atual
                operacoes_dia = 0
                losses_dia = 0
                
            # Verifica a Trava Diária
            if operacoes_dia >= DAY_TRADE["max_trades"] or losses_dia >= DAY_TRADE["max_losses"]:
                continue # Pula o resto do dia

            sinal = detectar_vega(df.iloc[i - JANELA: i + 1])
            if not sinal: continue
            
            df_swing = df.iloc[i+1: i + 1 + DAY_TRADE["expiry"]]
            rs, ret = simular_trade(df_swing, sinal["preco"], DAY_TRADE)
            res[rs] += 1
            res["ret_pct"].append(ret)
            
            operacoes_dia += 1
            if rs == "LOSS":
                losses_dia += 1
            
            trades_log.append({
                "symbol": symbol, "data": df.index[i].strftime("%Y-%m-%d %H:%M"),
                "rs": rs, "ret": ret, "op_dia": operacoes_dia, "loss_dia": losses_dia
            })
            trades += 1
            cooldown = 4 # Congela 1 horinha apenas para não morder o mesmo candle seguido
            
        sinais_totais += trades
        print(f"✅ {trades} sinais")

    print(f"\n{'═'*70}")
    print(f"  📊 RESULTADO DAY TRADE (Vega + Limite Diário)")
    print(f"     TP +1.5% | SL -1.0% | Max {DAY_TRADE['max_trades']} ops/dia | Trava {DAY_TRADE['max_losses']} red/dia")
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
    print(f"  {'🎯 TAXA DE ACERTO':<20} | {s_W/(s_W+s_L)*100 if s_W+s_L > 0 else 0:>20.1f}% (descontando timeouts)")
    print(f"  {'💰 RETORNO MÉDIO':<20} | {s_ret:>20.2f}%")
    print(f"{'═'*70}\n")
    
    trades_df = pd.DataFrame(trades_log)
    if not trades_df.empty:
        print("  Detalhe dos Sinais Day Trade:")
        for r in trades_df.itertuples():
            ic = "✅" if r.rs=="WIN" else ("❌" if r.rs=="LOSS" else "⏳")
            print(f"  {r.symbol:<10} {r.data} {ic}{r.rs:<8} {r.ret:>+6.2f}% | Op dia:{r.op_dia} Loss dia:{r.loss_dia}")
            
if __name__ == "__main__":
    backtest_daytrade()
