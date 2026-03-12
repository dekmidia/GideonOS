"""
╔══════════════════════════════════════════════════════════════════╗
║     ESTRATÉGIA LARANJA (SHORT MULTI-TIMEFRAME 1M & 5M)         ║
║     Matriz Forense: Explora os 70% de Falso Rompimento         ║
║     Validação: 1m, 5m                                          ║
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

# PERFIS PROPORCIONAIS POR TIMEFRAME (SHORT)
PERFIS = {
    "1m": {"tp": 0.997, "sl": 1.002, "expiry": 60, "dias": 3},
    "5m": {"tp": 0.992, "sl": 1.004, "expiry": 72, "dias": 15},
    "30m": {"tp": 0.975, "sl": 1.050, "expiry": 48, "dias": 30},
    "1h": {"tp": 0.950, "sl": 1.100, "expiry": 168, "dias": 90},
    "4h": {"tp": 0.950, "sl": 1.100, "expiry": 42, "dias": 180},
    "1d": {"tp": 0.900, "sl": 1.200, "expiry": 30, "dias": 365}
}

JANELA = 30 

def obter_historico(symbol, interval, dias):
    url    = "https://api.binance.com/api/v3/klines"
    fim    = int(datetime.now(timezone.utc).timestamp() * 1000)
    inicio = int((datetime.now(timezone.utc) - timedelta(days=dias)).timestamp() * 1000)
    todos, cursor = [], inicio
    while cursor < fim:
        try:
            resp = requests.get(url, params={"symbol": symbol, "interval": interval, "startTime": cursor, "endTime": fim, "limit": 1000}, timeout=15)
            if resp.status_code != 200: 
                print(f"Erro API: {resp.status_code}")
                return None
            batch = resp.json()
            if not batch: break
            todos.extend(batch)
            cursor = batch[-1][0] + 1
            time.sleep(0.12)
        except Exception as e:
            print(f"Erro conexão: {e}")
            return None
            
    if not todos: return None
    df = pd.DataFrame(todos, columns=["timestamp","open","high","low","close","volume","close_time","qav","trades","taker_base","taker_quote","ignore"])[["timestamp","open","high","low","close","volume"]].copy()
    for col in ["open","high","low","close","volume"]: df[col] = pd.to_numeric(df[col])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.drop_duplicates(subset="timestamp", inplace=True)
    df.set_index("timestamp", inplace=True)
    return df

def detectar_padrao_laranja(janela_df):
    if len(janela_df) < JANELA: return None
    
    gatilho = janela_df.iloc[-1]
    
    df_caixote = janela_df.iloc[-7:-1] 
    max_recent = df_caixote["high"].max()
    min_recent = df_caixote["low"].min()
    range_caixote = (max_recent / min_recent - 1) * 100
    
    # Tolerância do caixote apertado
    if range_caixote > 8.0: return None

    # Corpo do Doji (<=3%)
    corpo_gatilho = abs(gatilho["close"] - gatilho["open"]) / gatilho["open"] * 100
    if corpo_gatilho > 3.0: return None
        
    # Pavio de varredura
    pavio_inferior = (min(gatilho["open"], gatilho["close"]) - gatilho["low"]) / gatilho["open"] * 100
    if pavio_inferior < 0.3: return None
        
    return {
        "preco": gatilho["close"], 
        "corpo": corpo_gatilho, 
        "range_cx": range_caixote,
        "pavio": pavio_inferior
    }

def simular_trade_short(df_futuro, p_in, perfil):
    tp, sl = p_in * perfil["tp"], p_in * perfil["sl"]
    
    for j in range(len(df_futuro)):
        low_atual = df_futuro.iloc[j]["low"]
        high_atual = df_futuro.iloc[j]["high"]
        
        # Atingiu alvo de venda (Ganha quando cai)
        if low_atual <= tp: 
            return "WIN (SHORT)", ((p_in - tp) / p_in) * 100 
            
        # Stopado pela subida (Perde quando sobe)
        if high_atual >= sl: 
            return "LOSS (SHORT)", ((p_in - sl) / p_in) * 100
            
    pf = df_futuro.iloc[-1]["close"]
    return "TIMEOUT", ((p_in - pf) / p_in) * 100

def rodar_backtest(interval):
    perfil = PERFIS[interval]
    print(f"\n" + "="*55)
    print(f"   REVOLTA DO LARANJA - SHORT NO GRAFICO {interval.upper():<11} ")
    print(f"   Alvo Tatico: TP Queda {(1-perfil['tp'])*100:.1f}% | SL Alta {(perfil['sl']-1)*100:.1f}%     ")
    print("="*55 + "\n")
    
    res = {"WIN":0, "LOSS":0, "TIMEOUT":0, "ret_pct": []}
    sinais_totais = 0

    for symbol in PARES_BACKTEST:
        print(f"  Down: {symbol} ({perfil['dias']} dias / {interval})...", end=" ", flush=True)
        df = obter_historico(symbol, interval, perfil["dias"])
        
        if df is None or len(df) < JANELA + perfil["expiry"] + 10:
            print("PULADO")
            continue
            
        trades = 0
        cooldown = 0
        
        for i in range(JANELA, len(df) - perfil["expiry"] - 1):
            if cooldown > 0:
                cooldown -= 1
                continue
                
            sinal = detectar_padrao_laranja(df.iloc[i - JANELA: i + 1])
            if not sinal: continue
            
            df_swing = df.iloc[i+1: i + 1 + perfil["expiry"]]
            rs_raw, ret = simular_trade_short(df_swing, sinal["preco"], perfil)
            
            if "WIN" in rs_raw: res["WIN"] += 1
            elif "LOSS" in rs_raw: res["LOSS"] += 1
            else: res["TIMEOUT"] += 1
                
            res["ret_pct"].append(ret)
            
            trades += 1
            # Cooldown proporcional
            cooldown = 12 if interval == "5m" else 30
            
        sinais_totais += trades
        print(f"OK: {trades} operacoes")

    print(f"\n{'='*70}")
    print(f"  RESULTADO SHORT ({interval.upper()})")
    print(f"{'='*70}")
    
    if sinais_totais == 0:
        print("Nenhum sinal encontrado.\n")
        return
        
    s_W, s_L, s_T = res["WIN"], res["LOSS"], res["TIMEOUT"]
    s_ret = np.mean(res["ret_pct"])

    print(f"  {'WIN (Mercado Caiu)':<25} | {s_W:>4} ({s_W/sinais_totais*100:4.1f}%)")
    print(f"  {'LOSS (Mercado Subiu)':<25} | {s_L:>4} ({s_L/sinais_totais*100:4.1f}%)")
    print(f"  {'TIMEOUTS':<25} | {s_T:>4} ({s_T/sinais_totais*100:4.1f}%)")
    print(f"  {'-'*45}")
    print(f"  {'TAXA DE ACERTO SHORT':<25} | {s_W/(s_W+s_L)*100 if s_W+s_L > 0 else 0:>20.1f}%")
    print(f"  {'EXPECTED VALUE (EV)':<25} | {s_ret:>20.2f}% POR TRADE")
    print(f"{'='*70}\n")
            
if __name__ == "__main__":
    for tf in ["30m", "1h", "4h", "1d"]:
        rodar_backtest(tf)
