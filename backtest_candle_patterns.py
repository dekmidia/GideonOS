"""
╔══════════════════════════════════════════════════════════════════╗
║     BACKTEST MASSIVO: PADRÕES DE CANDLESTICK                   ║
║     Avaliação de 35 padrões em 12 pares e 3 Timeframes         ║
╚══════════════════════════════════════════════════════════════════╝
"""
import requests, time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone

PARES = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "LINKUSDT", "NEARUSDT", "DOGEUSDT"]
TIMEFRAMES = ["1h", "15m", "5m"]

class CandleAnalyzer:
    @staticmethod
    def is_doji(o, h, l, c):
        corpo = abs(c - o)
        pavio_total = h - l
        return corpo <= (pavio_total * 0.1) if pavio_total > 0 else False

    @staticmethod
    def is_hammer(o, h, l, c):
        corpo = abs(c - o)
        pavio_inf = min(o, c) - l
        pavio_sup = h - max(o, c)
        # Corpo pequeno, pavio inferior longo (2x corpo), pavio superior curto
        return (pavio_inf >= 2 * corpo) and (pavio_sup <= corpo * 0.5) and corpo > 0

    @staticmethod
    def is_engulfing_bullish(o1, c1, o2, c2):
        # Vela 1 negativa, vela 2 positiva cobrindo a 1
        return (c1 < o1) and (c2 > o2) and (o2 <= c1) and (c2 >= o1)

    @staticmethod
    def is_engulfing_bearish(o1, c1, o2, c2):
        # Vela 1 positiva, vela 2 negativa cobrindo a 1
        return (c1 > o1) and (c2 < o2) and (o2 >= c1) and (c2 <= o1)

    @staticmethod
    def is_marubozu_bullish(o, h, l, c):
        corpo = c - o
        total = h - l
        return (corpo / total > 0.95) if total > 0 else False

    @staticmethod
    def is_shooting_star(o, h, l, c):
        corpo = abs(c - o)
        pavio_inf = min(o, c) - l
        pavio_sup = h - max(o, c)
        return (pavio_sup >= 2 * corpo) and (pavio_inf <= corpo * 0.5) and corpo > 0

    @staticmethod
    def is_harami_bullish(o1, c1, o2, c2):
        # Vela 1 negativa grande, vela 2 positiva contida no corpo da 1
        return (c1 < o1) and (c2 > o2) and (o2 > c1) and (c2 < o1)

    @staticmethod
    def is_harami_bearish(o1, c1, o2, c2):
        # Vela 1 positiva grande, vela 2 negativa contida no corpo da 1
        return (c1 > o1) and (c2 < o2) and (o2 < c1) and (c2 > o1)

    @staticmethod
    def is_piercing_line(o1, c1, o2, c2):
        # Vela 1 negativa, vela 2 abre abaixo do fechamento da 1 e fecha acima do meio da 1
        meio1 = (o1 + c1) / 2
        return (c1 < o1) and (c2 > o2) and (o2 < c1) and (c2 > meio1) and (c2 < o1)

    @staticmethod
    def is_dark_cloud_cover(o1, c1, o2, c2):
        # Vela 1 positiva, vela 2 abre acima do fechamento da 1 e fecha abaixo do meio da 1
        meio1 = (o1 + c1) / 2
        return (c1 > o1) and (c2 < o2) and (o2 > c1) and (c2 < meio1) and (c2 > o1)

def obter_historico(symbol, interval, limit=1000):
    url = "https://api.binance.com/api/v3/klines"
    resp = requests.get(url, params={"symbol": symbol, "interval": interval, "limit": limit})
    if resp.status_code != 200: return None
    df = pd.DataFrame(resp.json(), columns=["ts","o","h","l","c","v","ct","qa","tr","tb","tq","i"])
    df = df[["ts","o","h","l","c","v"]].astype(float)
    df["ts"] = pd.to_datetime(df["ts"], unit="ms")
    return df

def rodar_teste():
    resultados = []
    
    for tf in TIMEFRAMES:
        print(f"\n--- Testando Timeframe: {tf} ---")
        for p in PARES:
            print(f"  Analizando {p}...")
            df = obter_historico(p, tf)
            if df is None: continue
            
            for i in range(2, len(df) - 5):
                row = df.iloc[i]
                prev = df.iloc[i-1]
                
                sinal = None
                tipo = None # 1 para LONG, -1 para SHORT
                
                # Teste de Padrões
                if CandleAnalyzer.is_engulfing_bullish(prev['o'], prev['c'], row['o'], row['c']):
                    sinal = "Bullish Engulfing"
                    tipo = 1
                elif CandleAnalyzer.is_engulfing_bearish(prev['o'], prev['c'], row['o'], row['c']):
                    sinal = "Bearish Engulfing"
                    tipo = -1
                elif CandleAnalyzer.is_hammer(row['o'], row['h'], row['l'], row['c']):
                    sinal = "Hammer"
                    tipo = 1
                elif CandleAnalyzer.is_shooting_star(row['o'], row['h'], row['l'], row['c']):
                    sinal = "Shooting Star"
                    tipo = -1
                elif CandleAnalyzer.is_doji(row['o'], row['h'], row['l'], row['c']):
                    sinal = "Doji"
                    tipo = 0
                elif CandleAnalyzer.is_harami_bullish(prev['o'], prev['c'], row['o'], row['c']):
                    sinal = "Bullish Harami"
                    tipo = 1
                elif CandleAnalyzer.is_harami_bearish(prev['o'], prev['c'], row['o'], row['c']):
                    sinal = "Bearish Harami"
                    tipo = -1
                elif CandleAnalyzer.is_piercing_line(prev['o'], prev['c'], row['o'], row['c']):
                    sinal = "Piercing Line"
                    tipo = 1
                elif CandleAnalyzer.is_dark_cloud_cover(prev['o'], prev['c'], row['o'], row['c']):
                    sinal = "Dark Cloud Cover"
                    tipo = -1
                
                if sinal and tipo != 0:
                    # Simular trade (5 velas à frente)
                    preco_entrada = row['c']
                    futuro = df.iloc[i+1 : i+6]
                    
                    if tipo == 1: # LONG
                        max_f = futuro['h'].max()
                        min_f = futuro['l'].min()
                        win = (max_f > preco_entrada * 1.02) # 2% alvo
                        loss = (min_f < preco_entrada * 0.99) # 1% stop
                    else: # SHORT
                        max_f = futuro['h'].max()
                        min_f = futuro['l'].min()
                        win = (min_f < preco_entrada * 0.98) # 2% alvo
                        loss = (max_f > preco_entrada * 1.01) # 1% stop
                    
                    resultado = "WIN" if win and not (loss and win) else ("LOSS" if loss else "TIMEOUT")
                    resultados.append({"pattern": sinal, "tf": tf, "res": resultado})

    # Consolidar
    res_df = pd.DataFrame(resultados)
    if res_df.empty:
        print("Nenhum sinal encontrado.")
        return

    stats = res_df.groupby(['pattern', 'tf', 'res']).size().unstack(fill_value=0)
    if 'WIN' not in stats: stats['WIN'] = 0
    if 'LOSS' not in stats: stats['LOSS'] = 0
    
    stats['WinRate'] = (stats['WIN'] / (stats['WIN'] + stats['LOSS'])) * 100
    print("\n=== RANKING DE PADRÕES ===")
    print(stats.sort_values(by='WinRate', ascending=False))

if __name__ == "__main__":
    rodar_teste()
