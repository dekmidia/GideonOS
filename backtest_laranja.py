"""
╔══════════════════════════════════════════════════════════════════╗
║     ESTRATÉGIA LARANJA — Padrão Preditivo 4H                   ║
║     Matriz Forense: Caixote (Range < 7%) + Doji Gatilho (Corpo < 2.5%)  ║
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

# PERFIL SWING/LONG DAYTRADE OTIMIZADO PARA 4H
PERFIL_LARANJA = {
    "tp": 1.10,      # Alvo agressivo do usuário (10% Swing)
    "sl": 0.95,      # Stop seguro (5% Swing)
    "expiry": 42     # 7 dias para bater o Alvo (42 candles de 4h)
}

JANELA = 30 # Precisa olhar 30 candles pra tras pra montar o caixote

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
    Motor Morfológico que não usa média móvel, estocástico nem MACD.
    Analisa apenas o Price Action puro.
    """
    if len(janela_df) < JANELA: return None
    
    # O candle atual (-1) é o possível inicio do PUMP (Linha Laranja).
    # Precisamos validar as condições TÉCNICAS nos candles que o AMTECEDERAM.
    gatilho = janela_df.iloc[-1]   # C-1 (O Doji Gatilho)
    i = -1
    
    # CONDIÇÃO 1: CAIXOTE ESTREITO NAS ÚLTIMAS 24 HORAS (6 velas de 4h anteriores ao gatilho)
    # A moeda tem que estar morta (acumulação). Se já esticou, descartamos.
    df_caixote = janela_df.iloc[-7:-1] 
    max_recent = df_caixote["high"].max()
    min_recent = df_caixote["low"].min()
    range_caixote = (max_recent / min_recent - 1) * 100
    
    if range_caixote > 8.0:
        return None # Moeda muito volátil, não formou a "panela de pressão"

    # CONDIÇÃO 2: A MORFOLOGIA DO CANDLE GATILHO (C-1)
    # 2.1 - O Corpo precisa ser minúsculo (Doji) indicando fim da força vendedora
    corpo_gatilho = abs(gatilho["close"] - gatilho["open"]) / gatilho["open"] * 100
    if corpo_gatilho > 3.0: 
        return None # Corpo grande demais, não é o Shrink Mestre
        
    # 2.2 - O Sweep de Fundo (A rasteira institucional)
    pavio_inferior = (min(gatilho["open"], gatilho["close"]) - gatilho["low"]) / gatilho["open"] * 100
    if pavio_inferior < 0.3:
        return None # Sem pavio, sem raspagem de de stops dos sardinhas
        
    # SE CHEGOU AQUI: O PADRÃO LARANJA ACONTECEU AGORA! 
    # Validou C-1 Doji após lateralização
    return {
        "preco": gatilho["close"], 
        "corpo": corpo_gatilho, 
        "range_cx": range_caixote,
        "pavio": pavio_inferior
    }

def simular_trade(df_futuro, p_in, perfil):
    tp, sl = p_in * perfil["tp"], p_in * perfil["sl"]
    for j in range(len(df_futuro)):
        if df_futuro.iloc[j]["high"] >= tp: return "WIN", (tp/p_in-1)*100
        if df_futuro.iloc[j]["low"]  <= sl: return "LOSS", (sl/p_in-1)*100
    pf = df_futuro.iloc[-1]["close"]
    return "TIMEOUT", (pf/p_in-1)*100

def backtest_laranja():
    print("\n╔═════════════════════════════════════════════════════╗")
    print("║   ESTRATÉGIA LARANJA — PADRÃO FORENSE 4H            ║")
    print(f"║   C-1 Doji (Corpo < 3%) + Caixote Mestre (< 8%)     ║")
    print("╚═════════════════════════════════════════════════════╝\n")
    
    res = {"WIN":0, "LOSS":0, "TIMEOUT":0, "ret_pct": []}
    sinais_totais = 0
    trades_log = []

    # Como é gráfico de 4H, precisamos de 180 dias (Meio ano) pra ter volume de amostragem
    for symbol in PARES_BACKTEST:
        print(f"  ⬇️  Baixando {symbol} (180 dias / 4H)...", end=" ", flush=True)
        df = obter_historico(symbol, "4h", 180)
        
        if df is None or len(df) < JANELA + PERFIL_LARANJA["expiry"] + 10:
            print("PULADO")
            continue
            
        trades = 0
        cooldown = 0
        
        for i in range(JANELA, len(df) - PERFIL_LARANJA["expiry"] - 1):
            if cooldown > 0:
                cooldown -= 1
                continue
                
            sinal = detectar_padrao_laranja(df.iloc[i - JANELA: i + 1])
            if not sinal: continue
            
            df_swing = df.iloc[i+1: i + 1 + PERFIL_LARANJA["expiry"]]
            rs, ret = simular_trade(df_swing, sinal["preco"], PERFIL_LARANJA)
            res[rs] += 1
            res["ret_pct"].append(ret)
            
            trades_log.append({
                "symbol": symbol, "data": df.index[i].strftime("%Y-%m-%d %H:%M"),
                "rs": rs, "ret": ret, "cx": sinal["range_cx"], "corpo": sinal["corpo"], "pavio": sinal["pavio"]
            })
            trades += 1
            cooldown = 12 # Esperar pelo menos 2 dias após identificar o gatilho na mesma moeda
            
        sinais_totais += trades
        print(f"✅ {trades} sinais")

    print(f"\n{'═'*70}")
    print(f"  📊 RESULTADO PADRÃO LARANJA (Gráfico 4H)")
    print(f"     TP +10.0% | SL -5.0% | Target: Swing 7 Dias")
    print(f"{'═'*70}")
    
    if sinais_totais == 0:
        print("Nenhum sinal encontrado com a Morfologia exigida.")
        return
        
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
        print("\n  Detalhes do Scanner (Últimos 15 achados):")
        for r in trades_df.tail(15).itertuples():
            ic = "✅" if r.rs=="WIN" else ("❌" if r.rs=="LOSS" else "⏳")
            print(f"  {r.symbol:<10} {r.data} {ic}{r.rs:<8} {r.ret:>+6.2f}% | Cx:{r.cx:>3.1f}% Corpo:{r.corpo:>3.1f}% Pavio:{r.pavio:>3.1f}%")
    print(f"{'═'*70}\n")
            
if __name__ == "__main__":
    backtest_laranja()
