"""
Script de análise aprofundada do backtest.
Lê o CSV de resultados e calcula correlações estatísticas
entre scores, pares, períodos e resultados para sugerir
novas regras de filtragem.
"""
import pandas as pd
import numpy as np

df = pd.read_csv("backtest_v21_resultado.csv")

print("=" * 60)
print("  ANÁLISE APROFUNDADA — IDENTIFICANDO PADRÕES NOS WINS")
print("=" * 60)

wins    = df[df["resultado"] == "WIN"]
losses  = df[df["resultado"] == "LOSS"]
timeout = df[df["resultado"] == "TIMEOUT"]

# 1. Score distribution por resultado
print("\n📊 Distribuição de score (out of 9) por resultado:")
print(df.groupby(["score","resultado"]).size().unstack(fill_value=0).to_string())

print("\n📊 Score médio por resultado:")
print(df.groupby("resultado")["score"].mean().to_string())

# 2. Retorno médio dentro dos timeouts
print(f"\n📊 Timeouts com retorno POSITIVO: {len(timeout[timeout['retorno_pct']>0])} / {len(timeout)}")
print(f"   Retorno médio dos timeouts positivos: {timeout[timeout['retorno_pct']>0]['retorno_pct'].mean():.2f}%")
print(f"   Retorno médio dos timeouts negativos: {timeout[timeout['retorno_pct']<0]['retorno_pct'].mean():.2f}%")

# 3. Wins por par
print("\n📊 Wins por par (taxa de acerto):")
for sym in df["symbol"].unique():
    sub = df[df["symbol"]==sym]
    w = len(sub[sub["resultado"]=="WIN"])
    l = len(sub[sub["resultado"]=="LOSS"])
    t = len(sub[sub["resultado"]=="TIMEOUT"])
    taxa = w/len(sub)*100
    ret_t = sub[sub["resultado"]=="TIMEOUT"]["retorno_pct"].mean()
    print(f"   {sym:<14} wins:{w:2d} losses:{l:3d} timeout:{t:3d}  acerto:{taxa:.0f}%  timeout_ret_med:{ret_t:+.2f}%")

# 4. Horário dos wins (UTC)
wins_cp = wins.copy()
wins_cp["hora"] = pd.to_datetime(wins_cp["data_sinal"]).dt.hour
print(f"\n📊 Horário (UTC) dos sinais vencedores:")
print(wins_cp["hora"].value_counts().sort_index().to_string())

losses_cp = losses.copy()
losses_cp["hora"] = pd.to_datetime(losses_cp["data_sinal"]).dt.hour
print(f"\n📊 Horário (UTC) dos sinais perdedores (mais frequentes):")
print(losses_cp["hora"].value_counts().head(10).to_string())

# 5. Análise da velocidade de saída (candles)
print(f"\n📊 Candles até saída por resultado:")
print(df.groupby("resultado")["candles_ate_saida"].describe().to_string())

# 6. Wins consecutivos / sequências
print(f"\n📊 Detalhes de todos os WINS encontrados:")
print(wins[["symbol","data_sinal","preco_entrada","score","candles_ate_saida"]].to_string())

print("\n" + "=" * 60)
