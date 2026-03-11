"""
Script de Análise dos Bull Traps (Losses)
Lê backtest_v21_resultado.csv para investigar o que 
diferencia as falsas explosões (135 losses) dos wins reais.
Foco em: Posição do Preço vs EMA200 e Volume.
"""
import pandas as pd

df = pd.read_csv("backtest_v21_resultado.csv")
losses = df[df["resultado"] == "LOSS"]
wins   = df[df["resultado"] == "WIN"]
total  = len(df)

print("\n" + "="*60)
print(" 🔬 ANÁLISE DE FALHAS: DISSECANDO OS BULL TRAPS (LOSSES)")
print("="*60)

print(f"\n📊 Total de Sinais: {total} | LOSSES: {len(losses)} ({len(losses)/total*100:.1f}%) | WINS: {len(wins)}")

# 1. Correlação com Crossover MACD
print("\n📈 RELAÇÃO COM CONFIRMAÇÕES (A regra não evitou a armadilha?)")
losses_macd = losses[losses["macd_cross"] == True]
wins_macd   = wins[wins["macd_cross"] == True]
print(f"   MACD Crossover presente em LOSSES: {len(losses_macd)} ({len(losses_macd)/len(losses)*100:.1f}%)")
print(f"   MACD Crossover presente em WINS  : {len(wins_macd)} ({len(wins_macd)/len(wins)*100:.1f}%)")

losses_ign = losses[losses["ignition"] == True]
wins_ign   = wins[wins["ignition"] == True]
print(f"   Ignition (+2%) presente em LOSSES: {len(losses_ign)} ({len(losses_ign)/len(losses)*100:.1f}%)")
print(f"   Ignition (+2%) presente em WINS  : {len(wins_ign)} ({len(wins_ign)/len(wins)*100:.1f}%)")

# 2. Score médio da armadilha
print("\n🎯 O SCORE PREVÊ A ARMADILHA?")
print(f"   Score médio nos WINS  : {wins['score'].mean():.2f}")
print(f"   Score médio nos LOSSES: {losses['score'].mean():.2f}")

# 3. RSI Extremo na armadilha?
print("\n🌡️ RSI NA HORA DO SINAL (Superaquecido ou Frio?)")
print("   (WINS)")
print(f"      Média : {wins['rsi'].mean():.1f}")
print(f"      Máximo: {wins['rsi'].max():.1f} | Mínimo: {wins['rsi'].min():.1f}")
print("   (LOSSES)")
print(f"      Média : {losses['rsi'].mean():.1f}")
print(f"      Máximo: {losses['rsi'].max():.1f} | Mínimo: {losses['rsi'].min():.1f}")
print(f"      Quantos LOSSES tinham RSI > 60 no gatilho? {len(losses[losses['rsi'] > 60])} ({len(losses[losses['rsi'] > 60])/len(losses)*100:.1f}%)")

# 4. Velocidade da Morte
print("\n⏳ QUANTO TEMPO DEMORA PRA DAR ERRADO? (Candles até o SL)")
print("   (WINS até o TP)")
print(f"      Média: {wins['candles'].mean():.1f} candles ({wins['candles'].mean()*15/60:.1f}h)")
print(f"      Rápido (<= 3 candles) : {len(wins[wins['candles'] <= 3])}")
print("   (LOSSES até o SL)")
print(f"      Média: {losses['candles'].mean():.1f} candles ({losses['candles'].mean()*15/60:.1f}h)")
print(f"      Rápido (<= 3 candles) : {len(losses[losses['candles'] <= 3])} ({len(losses[losses['candles'] <= 3])/len(losses)*100:.1f}%)")

print("\n" + "="*60 + "\n")
