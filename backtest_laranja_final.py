"""
╔══════════════════════════════════════════════════════════════════╗
║     ESTRATÉGIA LARANJA (SHORT 1H) - VALIDAÇÃO FINAL            ║
║     Matriz Forense: Teste de Robustez 30, 60, 90 Dias          ║
╚══════════════════════════════════════════════════════════════════╝
"""
import requests, time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone

PARES_BACKTEST = [
    "SOLUSDT", "LINKUSDT", "DOGEUSDT", "NEARUSDT",
    "APTUSDT", "AVAXUSDT", "DOTUSDT", "XRPUSDT",
    "ATOMUSDT", "INJUSDT", "SEIUSDT", "TIAUSDT",
]

# PERFIL SHORT 1H
PERFIL = {"tp": 0.95, "sl": 1.10, "expiry": 7 * 24} # Alvo 5%, Stop 10%
JANELA = 30 

def obter_historico(symbol, interval, dias):
    url = "https://api.binance.com/api/v3/klines"
    fim = int(datetime.now(timezone.utc).timestamp() * 1000)
    inicio = int((datetime.now(timezone.utc) - timedelta(days=dias)).timestamp() * 1000)
    todos, cursor = [], inicio
    while cursor < fim:
        resp = requests.get(url, params={"symbol": symbol, "interval": interval, "startTime": cursor, "endTime": fim, "limit": 1000}, timeout=15)
        if resp.status_code != 200: return None
        batch = resp.json()
        if not batch: break
        todos.extend(batch)
        cursor = batch[-1][0] + 1
        time.sleep(0.1)
    if not todos: return None
    df = pd.DataFrame(todos, columns=["ts","o","h","l","c","v","ct","qa","tr","tb","tq","i"])[["ts","o","h","l","c","v"]]
    for col in ["o","h","l","c","v"]: df[col] = pd.to_numeric(df[col])
    df["ts"] = pd.to_datetime(df["ts"], unit="ms")
    return df.set_index("ts")

def detectar_padrao_laranja(janela_df):
    gatilho = janela_df.iloc[-1]
    df_caixote = janela_df.iloc[-7:-1] 
    range_cx = (df_caixote["h"].max() / df_caixote["l"].min() - 1) * 100
    if range_cx > 8.0: return None
    corpo = abs(gatilho["c"] - gatilho["o"]) / gatilho["o"] * 100
    if corpo > 3.0: return None
    p_inf = (min(gatilho["o"], gatilho["c"]) - gatilho["l"]) / gatilho["o"] * 100
    if p_inf < 0.3: return None
    return {"preco": gatilho["c"]}

def simular_trade(df_futuro, p_in):
    tp, sl = p_in * PERFIL["tp"], p_in * PERFIL["sl"]
    for j in range(len(df_futuro)):
        if df_futuro.iloc[j]["l"] <= tp: return "WIN"
        if df_futuro.iloc[j]["h"] >= sl: return "LOSS"
    return "TIMEOUT"

def rodar_backtest(dias):
    print(f"\n🚀 INICIANDO BACKTEST DE {dias} DIAS...")
    stats = {"WIN": 0, "LOSS": 0, "TIMEOUT": 0}
    total_trades = 0
    for symbol in PARES_BACKTEST:
        df = obter_historico(symbol, "1h", dias)
        if df is None or len(df) < JANELA + PERFIL["expiry"]: continue
        trades = 0
        cooldown = 0
        for i in range(JANELA, len(df) - PERFIL["expiry"] - 1):
            if cooldown > 0:
                cooldown -= 1
                continue
            sinal = detectar_padrao_laranja(df.iloc[i - JANELA: i + 1])
            if sinal:
                res = simular_trade(df.iloc[i+1 : i + 1 + PERFIL["expiry"]], sinal["preco"])
                stats[res] += 1
                trades += 1
                cooldown = 24 # 1 dia
        total_trades += trades
    
    wr = (stats["WIN"] / (stats["WIN"] + stats["LOSS"])) * 100 if (stats["WIN"] + stats["LOSS"]) > 0 else 0
    print(f"✅ FIM {dias} DIAS: Trades: {total_trades} | WR: {wr:.1f}% | W: {stats['WIN']} L: {stats['LOSS']} T: {stats['TIMEOUT']}")
    return {"dias": dias, "trades": total_trades, "wr": wr, "win": stats["WIN"], "loss": stats["LOSS"]}

if __name__ == "__main__":
    resultados = []
    for d in [30, 60, 90]:
        resultados.append(rodar_backtest(d))
    
    print("\n" + "="*50)
    print("  RELATÓRIO FINAL DE ROBUSTEZ (SHORT 1H)")
    print("="*50)
    for r in resultados:
        print(f"  {r['dias']} DIAS -> WR: {r['wr']:.1f}% | Sinais: {r['trades']}")
    print("="*50)
