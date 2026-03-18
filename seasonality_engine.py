import requests
import pandas as pd
import numpy as np
import os
import json
from datetime import datetime, timedelta

CACHE_DIR = "cache_seasonality"
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

class SeasonalityEngine:
    def __init__(self):
        self.base_url = "https://api.binance.com/api/v3/klines"

    def fetch_historical_data(self, symbol, years=10):
        cache_file = os.path.join(CACHE_DIR, f"{symbol}_1d.csv")
        
        # Se cache existe e é de hoje, carrega
        if os.path.exists(cache_file):
            mtime = datetime.fromtimestamp(os.path.getmtime(cache_file))
            if mtime.date() == datetime.now().date():
                return pd.read_csv(cache_file, index_col=0, parse_dates=True)

        print(f"Baixando histórico de {years} anos para {symbol}...")
        end_time = int(datetime.now().timestamp() * 1000)
        start_time = int((datetime.now() - timedelta(days=365 * years)).timestamp() * 1000)
        
        all_klines = []
        current_start = start_time
        
        while current_start < end_time:
            params = {
                "symbol": symbol,
                "interval": "1d",
                "startTime": current_start,
                "limit": 1000
            }
            try:
                response = requests.get(self.base_url, params=params, timeout=10)
                data = response.json()
                if not data:
                    break
                all_klines.extend(data)
                current_start = data[-1][0] + 1
                if len(data) < 1000:
                    break
            except Exception as e:
                print(f"Erro ao baixar dados: {e}")
                break

        if not all_klines:
            return None

        df = pd.DataFrame(all_klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'qav', 'num_trades', 'taker_base', 'taker_quote', 'ignore'
        ])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        df['close'] = df['close'].astype(float)
        
        # Salva no cache
        df[['close']].to_csv(cache_file)
        return df[['close']]

    def calculate_seasonality(self, symbol):
        df = self.fetch_historical_data(symbol)
        if df is None or df.empty:
            return None

        # Calcula variação percentual diária
        df['pct_change'] = df['close'].pct_change()
        
        # Agrupa por dia do ano
        # Usamos (mes, dia) para evitar problemas com anos bissextos de forma simples
        df['day_of_year'] = df.index.strftime('%m-%d')
        
        seasonal_avg = df.groupby('day_of_year')['pct_change'].mean()
        
        # Suavização (Rolling Mean) para evitar bicos
        seasonal_avg_smooth = seasonal_avg.rolling(window=7, center=True, min_periods=1).mean()
        
        # Projeção para os próximos 30 dias
        now = datetime.now()
        projection = []
        
        # Calculamos o caminho bruto primeiro
        raw_path = []
        current_val = 1.0
        for i in range(45):
            target_date = now + timedelta(days=i-15)
            day_key = target_date.strftime('%m-%d')
            change = seasonal_avg_smooth.get(day_key, 0)
            current_val *= (1 + change)
            raw_path.append(current_val)

        # Normalizamos para que o índice 15 (Hoje) seja exatamente 1.0
        base_val = raw_path[15] if len(raw_path) > 15 else 1.0
        
        for i in range(45):
            target_date = now + timedelta(days=i-15)
            normalized_multiplier = raw_path[i] / base_val
            
            projection.append({
                "date": target_date.strftime('%Y-%m-%d'),
                "multiplier": round(normalized_multiplier, 6),
                "is_future": i > 15
            })

        # Score Sazonal (Tendência para os próximos 30 dias - Sincronizado com Alpha ROI)
        next_30_days = [ (now + timedelta(days=i)).strftime('%m-%d') for i in range(1, 31) ]
        avg_next_30 = sum([seasonal_avg_smooth.get(d, 0) for d in next_30_days]) / 30
        
        season_score = min(max(avg_next_30 * 5000, -10), 10) 
        
        return {
            "symbol": symbol,
            "projection": projection,
            "score": round(season_score, 1),
            "trend": "ALTA" if season_score > 0.5 else ("BAIXA" if season_score < -0.5 else "NEUTRO")
        }

if __name__ == "__main__":
    engine = SeasonalityEngine()
    result = engine.calculate_seasonality("BTCUSDT")
    print(json.dumps(result, indent=2))
