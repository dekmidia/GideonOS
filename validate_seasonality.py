import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta
import sys

# Adiciona o diretório atual ao path para importar o motor
sys.path.append(os.getcwd())
from seasonality_engine import SeasonalityEngine

def run_backtest(symbol="BTCUSDT"):
    engine = SeasonalityEngine()
    df = engine.fetch_historical_data(symbol, years=10)
    
    if df is None:
        print("Erro: Não foi possível baixar dados.")
        return

    df['pct_change'] = df['close'].pct_change()
    df['day_of_year'] = df.index.strftime('%m-%d')
    
    # Vamos testar a eficácia da projeção de 30 dias em janelas passadas
    # Pegamos os últimos 3 anos para validar individualmente
    years_to_test = [2021, 2022, 2023, 2024, 2025]
    results = []

    # Calcula a média sazonal excluindo o ano que estamos testando (Out-of-sample simples)
    for test_year in years_to_test:
        train_df = df[df.index.year != test_year]
        test_df = df[df.index.year == test_year]
        
        if test_df.empty: continue

        # Média Sazonal Global (sem o ano de teste)
        seasonal_avg = train_df.groupby('day_of_year')['pct_change'].mean()
        seasonal_avg_smooth = seasonal_avg.rolling(window=7, center=True, min_periods=1).mean()

        # Testar cada mês do ano de teste
        matches = 0
        total_tests = 0
        
        for month in range(1, 13):
            month_start = datetime(test_year, month, 1)
            # Janela de 30 dias
            month_end = month_start + timedelta(days=30)
            
            if month_end > df.index.max(): break
            
            # Projeção Sazonal Acumulada para esses 30 dias
            proj_return = 1.0
            for i in range(30):
                d_key = (month_start + timedelta(days=i)).strftime('%m-%d')
                change = seasonal_avg_smooth.get(d_key, 0)
                proj_return *= (1 + change)
            
            actual_return = df.loc[month_end, 'close'] / df.loc[month_start, 'close']
            
            # Direção (Acertou se ambos subiram ou ambos caíram)
            if (proj_return > 1.0 and actual_return > 1.0) or (proj_return < 1.0 and actual_return < 1.0):
                matches += 1
            
            total_tests += 1
        
        win_rate = (matches / total_tests * 100) if total_tests > 0 else 0
        results.append({
            "Ano": test_year,
            "Testes": total_tests,
            "Acertos Direcionais": matches,
            "Taxa de Acerto": f"{win_rate:.1f}%"
        })

    return pd.DataFrame(results)

if __name__ == "__main__":
    print("Iniciando Backtest de Sazonalidade (BTCUSDT)...")
    res = run_backtest("BTCUSDT")
    print("\nRESULTADOS POR ANO (Acerto da Projeção de 30 dias):")
    print(res.to_string(index=False))
    
    # Média Geral
    acc_list = [float(x.replace('%','')) for x in res['Taxa de Acerto']]
    print(f"\nTAXA DE ACERTO MÉDIA (10 ANOS): {sum(acc_list)/len(acc_list):.1f}%")
    print("\nNota: Um acerto > 50% indica vantagem estatística real sobre o aleatório.")
