"""
╔══════════════════════════════════════════════════════════════════╗
║     PROJETO LARANJA — FORENSE DO MOMENTO ZERO (GRÁFICO 4H)       ║
║     Extração do Padrão Morfológico Prévio ao Pump Institucional  ║
╚══════════════════════════════════════════════════════════════════╝
"""
import requests, time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone

# 7 Coordenadas exatas do Momento Laranja (Início do Pump no gráfico 4H) do Usuário:
COORDENADAS = [
    {"symbol": "DYDXUSDT", "ts_str": "2026-02-24 05:00:00"},
    {"symbol": "ILVUSDT",  "ts_str": "2026-03-08 05:00:00"},
    {"symbol": "MAVUSDT",  "ts_str": "2025-12-31 05:00:00"},
    {"symbol": "PIXELUSDT","ts_str": "2026-03-10 01:00:00"},
    {"symbol": "RONINUSDT","ts_str": "2026-03-09 21:00:00"},
    {"symbol": "XAIUSDT",  "ts_str": "2026-03-10 01:00:00"},
    {"symbol": "SSVUSDT",  "ts_str": "2026-01-25 17:00:00"}
]

def baixar_janela_forense(symbol, dt_zero):
    # Vamos baixar 20 candles antes do Momento Laranja e 5 depois para ter um bom raio-x
    ts_msec = int(dt_zero.timestamp() * 1000)
    # 4H = 14400000 msec. Puxar uns 6 dias pra trás e 1 pra frente
    inicio = ts_msec - (20 * 14400000)
    fim    = ts_msec + (5 * 14400000)
    
    url = "https://api.binance.com/api/v3/klines"
    resp = requests.get(url, params={"symbol": symbol, "interval": "4h", "startTime": inicio, "endTime": fim, "limit": 50}, timeout=10)
    
    if resp.status_code != 200: 
        print(f"Erro ao baixar dados para {symbol}")
        return None
        
    batch = resp.json()
    if not batch: return None
    
    df = pd.DataFrame(batch, columns=["timestamp","open","high","low","close","volume","close_time","qav","trades","taker_base","taker_quote","ignore"])[["timestamp","open","high","low","close","volume"]].copy()
    for col in ["open","high","low","close","volume"]: df[col] = pd.to_numeric(df[col])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)
    
    return df

def dissecar_anatomia():
    print("\n╔═════════════════════════════════════════════════════╗")
    print("║   LABORATÓRIO FORENSE (A MATRIZ DA LINHA LARANJA)   ║")
    print("╚═════════════════════════════════════════════════════╝\n")
    
    todas_analises = []

    for c in COORDENADAS:
        # A API recebe UTC+0, e as datas do usuario provavelmente sao BRT (UTC-3). 
        # Entao somamos 3 horas pra achar a vela certa na Binance.
        dt_brt = datetime.strptime(c["ts_str"], "%Y-%m-%d %H:%M:%S")
        dt_zero = dt_brt + timedelta(hours=3)
        symbol = c["symbol"]
        
        print(f"🔬 Analisando Cena do Crime: {symbol} em {c['ts_str']}")
        df = baixar_janela_forense(symbol, dt_zero)
        
        if df is None or len(df) == 0:
            print(f"   [!] Historico vazio para {symbol}.")
            continue
            
        # Pega o index numérico da vela mais proxima ao Momento Laranja
        idx_zero = df.index.get_indexer([dt_zero], method='nearest')[0]
        vela_zero_real = df.index[idx_zero]
        print(f"   📍 Vela Laranja mapeada na Binance: {vela_zero_real}")
        
        if idx_zero < 5:
            print("   [!] Histórico insuficiente para olhar para trás.")
            continue
            
        # O histórico mestre dos 3 candles anteriores (O preparatório do Pump)
        c0 = df.iloc[idx_zero]     # A Linha Laranja em Si (A explosão)
        c1 = df.iloc[idx_zero - 1] # 4 Horas Antes
        c2 = df.iloc[idx_zero - 2] # 8 Horas Antes
        c3 = df.iloc[idx_zero - 3] # 12 Horas Antes
        c4 = df.iloc[idx_zero - 4] # 16 Horas Antes
        
        # --- CARACTERÍSTICAS DA EXPLOSÃO (C0) ---
        boom_pct = (c0.high / c0.open - 1) * 100
        vol_c0 = c0.volume
        
        # --- ANATOMIA DOS 3 CANDLES ANTERIORES: ACUMULAÇÃO OU LIQUIDEZ ---
        # 1. Tamanho do Corpo vs Pavio Inferior no C-1
        corpo_c1 = abs(c1.close - c1.open) / c1.open * 100
        pavio_inf_c1 = (min(c1.open, c1.close) - c1.low) / c1.open * 100
        
        # 2. Variação de Volume C1 vs Média Anterior
        vol_medio_antigo = df["volume"].iloc[idx_zero-10 : idx_zero-1].mean()
        vol_queda = c1.volume < vol_medio_antigo  # Seca de volume antes de explodir?
        
        # 3. Compressão de Volatilidade nos candles c1 a c4
        max_high_ant = df["high"].iloc[idx_zero-5 : idx_zero].max()
        min_low_ant = df["low"].iloc[idx_zero-5 : idx_zero].min()
        caixote_pct = (max_high_ant / min_low_ant - 1) * 100
        
        print(f"   🔥 VELAS ANTES DA LINHA LARANJA (C-1, C-2, C-3):")
        print(f"   * Tam. Corpo do Candle que antecede (C-1): {corpo_c1:.2f}% (Doji / Shrink?)")
        print(f"   * Pavio inferior do C-1 (Captura de Fundo): {pavio_inf_c1:.2f}%")
        print(f"   * Caixote anterior (Amplitude 20h antes): {caixote_pct:.2f}%")
        print(f"   * Seca de Volume no candle antes de explodir? {'SIM (Spring/Acúmulo)' if vol_queda else 'NÃO (Fluxo contínuo)'}")
        print(f"   * EXPLOSÃO DA LINHA LARANJA: Candle de {boom_pct:.1f}% com volume {vol_c0/vol_medio_antigo:.1f}x maior que a média.\n")
        
        todas_analises.append({
            "symbol": symbol, "corpo": corpo_c1, "pavio": pavio_inf_c1, 
            "compressao": caixote_pct, "secou_vol": vol_queda
        })

    print("\n╔═════════════════════════════════════════════════════╗")
    print("║   GENÉTICA DO PADRÃO (O PONTO EM COMUM ENTRE ELAS)  ║")
    print("╚═════════════════════════════════════════════════════╝")
    
    df_res = pd.DataFrame(todas_analises)
    if not df_res.empty:
        print(f"Média do Corpo Anterior (C-1): {df_res['corpo'].mean():.2f}% (Candles muito espremidos?)")
        print(f"Pavio Inferior Médio (Sweep): {df_res['pavio'].mean():.2f}%")
        print(f"Range do Caixote (Contração Máxima): {df_res['compressao'].mean():.2f}%")
        print(f"O Volume Secou antes do Pump em: {(df_res['secou_vol'].sum() / len(df_res))*100:.0f}% das vezes")

if __name__ == "__main__":
    dissecar_anatomia()
