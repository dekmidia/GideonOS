"""
╔══════════════════════════════════════════════════════════════════╗
║     ESTRATÉGIA LARANJA (REVERSA) — Padrão Preditivo 4H         ║
║     Matriz Forense: Explora os 70% de Falso Rompimento         ║
║     Operação SHORT: Vende na Linha Laranja (TP -5%, SL +10%)   ║
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

# PERFIL SHORT (A APOSTA É QUE O ATIVO VAI CAIR ANTES DE SUBIR)
PERFIL_SHORT = {
    "tp": 0.95,      # Alvo (Lucro): Queda de 5%
    "sl": 1.10,      # Stop (Prejuízo): Alta de 10%
    "expiry": 42     # 7 dias 
}

JANELA = 30 

def obter_historico(symbol, interval="4h", dias=180):
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

def detectar_padrao_laranja(janela_df):
    """
    Motor Morfológico IDÊNTICO ao Scanner Laranja Original.
    Nosso objetivo é achar as exatas mesmas entradas que antes deram Loss.
    """
    if len(janela_df) < JANELA: return None
    
    gatilho = janela_df.iloc[-1]
    
    df_caixote = janela_df.iloc[-7:-1] 
    max_recent = df_caixote["high"].max()
    min_recent = df_caixote["low"].min()
    range_caixote = (max_recent / min_recent - 1) * 100
    if range_caixote > 8.0: return None

    corpo_gatilho = abs(gatilho["close"] - gatilho["open"]) / gatilho["open"] * 100
    if corpo_gatilho > 3.0: return None
        
    pavio_inferior = (min(gatilho["open"], gatilho["close"]) - gatilho["low"]) / gatilho["open"] * 100
    if pavio_inferior < 0.3: return None
        
    return {
        "preco": gatilho["close"], 
        "corpo": corpo_gatilho, 
        "range_cx": range_caixote,
        "pavio": pavio_inferior
    }

def simular_trade_short(df_futuro, p_in, perfil):
    """
    MUDANÇA CRUCIAL:
    Numa operação SHORT (Venda a descoberto), ganhamos dinheiro quando preço CAI.
    Portanto o TP (Take Profit) é atingido quando bate min de 0.95 (5% abaixo).
    O SL (Stop Loss) é atingido quando bate max de 1.10 (10% acima).
    """
    tp, sl = p_in * perfil["tp"], p_in * perfil["sl"]
    
    for j in range(len(df_futuro)):
        low_atual = df_futuro.iloc[j]["low"]
        high_atual = df_futuro.iloc[j]["high"]
        
        # Testar se bateu no alvo 5% pra baixo
        if low_atual <= tp: 
            # Ganhamos 5% (positivo porque apostamos na queda)
            return "WIN (SHORT)", ((p_in - tp) / p_in) * 100 
            
        # Testar se o mercado disparou 10% contra a gente (Stopou)
        if high_atual >= sl: 
            return "LOSS (SHORT)", ((p_in - sl) / p_in) * 100
            
    pf = df_futuro.iloc[-1]["close"]
    return "TIMEOUT", ((p_in - pf) / p_in) * 100

def backtest_laranja_short():
    print("\n╔═════════════════════════════════════════════════════╗")
    print("║   A REVOLTA DO LARANJA — OPERAÇÃO SHORT 4H          ║")
    print(f"║   Alvo Tático: TP +5.0% Queda | SL -10.0% Alta      ║")
    print("╚═════════════════════════════════════════════════════╝\n")
    
    res = {"WIN":0, "LOSS":0, "TIMEOUT":0, "ret_pct": []}
    sinais_totais = 0

    for symbol in PARES_BACKTEST:
        print(f"  ⬇️  Baixando {symbol} (180 dias / 4H)...", end=" ", flush=True)
        df = obter_historico(symbol, "4h", 180)
        
        if df is None or len(df) < JANELA + PERFIL_SHORT["expiry"] + 10:
            print("PULADO")
            continue
            
        trades = 0
        cooldown = 0
        
        for i in range(JANELA, len(df) - PERFIL_SHORT["expiry"] - 1):
            if cooldown > 0:
                cooldown -= 1
                continue
                
            sinal = detectar_padrao_laranja(df.iloc[i - JANELA: i + 1])
            if not sinal: continue
            
            df_swing = df.iloc[i+1: i + 1 + PERFIL_SHORT["expiry"]]
            rs_raw, ret = simular_trade_short(df_swing, sinal["preco"], PERFIL_SHORT)
            
            if "WIN" in rs_raw: res["WIN"] += 1
            elif "LOSS" in rs_raw: res["LOSS"] += 1
            else: res["TIMEOUT"] += 1
                
            res["ret_pct"].append(ret)
            
            trades += 1
            cooldown = 12 
            
        sinais_totais += trades
        print(f"✅ {trades} operações (Vendidas)")

    print(f"\n{'═'*70}")
    print(f"  📊 RESULTADO PADRÃO LARANJA INVERTIDO (SHORT)")
    print(f"     Apostando na queda: TP (+5.0%) | SL (-10.0%)")
    print(f"{'═'*70}")
    
    if sinais_totais == 0:
        print("Nenhum sinal encontrado.")
        return
        
    s_W, s_L, s_T = res["WIN"], res["LOSS"], res["TIMEOUT"]
    s_ret = np.mean(res["ret_pct"])

    print(f"  {'✅ WIN (Mercado Caiu)':<25} | {s_W:>4} ({s_W/sinais_totais*100:4.1f}%)")
    print(f"  {'❌ LOSS (Mercado Subiu)':<25} | {s_L:>4} ({s_L/sinais_totais*100:4.1f}%)")
    print(f"  {'⏳ TIMEOUTS':<25} | {s_T:>4} ({s_T/sinais_totais*100:4.1f}%)")
    print(f"  {'─'*45}")
    print(f"  {'🎯 TAXA DE ACERTO SHORT':<25} | {s_W/(s_W+s_L)*100 if s_W+s_L > 0 else 0:>20.1f}%")
    print(f"  {'💰 EXPECTED VALUE (EV)':<25} | {s_ret:>20.2f}% POR TRADE")
    print(f"{'═'*70}\n")
            
if __name__ == "__main__":
    backtest_laranja_short()
