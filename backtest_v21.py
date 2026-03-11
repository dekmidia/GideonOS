"""
╔══════════════════════════════════════════════════════════════════╗
║     CRYPTO PUMP BACKTEST v2.1 — Marcelo Vega                   ║
║     Calibrado: Score Ponderado, sem Dupla Confirmação Obrigatória║
╚══════════════════════════════════════════════════════════════════╝

MUDANÇAS v2.1 vs v2.0:
  • Squeeze >= 5 candles (era 8 — muito raro em bear market)
  • RSI < 35 OR MFI < 20 (era AND — eventos simultâneos raros)
  • MACD crossover e Ignition Candle somam +2 pontos cada no score
    mas NÃO são veto absoluto (podem estar ausentes)
  • Score mínimo: 7/14 (sem dupla confirmação obrigatória)
  • Score máximo (14/14) ainda descartado (sinal tardio)
  • Filtro de horário mantido: 05h–22h UTC
  • Volume: >= 1.2x média (levemente relaxado de 1.5x)
  • Pares alvo: altcoins + XRP (sem BTC/ETH como alvos)

Objetivo: Taxa de acerto > 30% com ~1-3 sinais/dia por par
"""

import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
import time


# ─────────────────────────────────────────────────
# CONFIGURAÇÃO
# ─────────────────────────────────────────────────
PARES_BACKTEST = [
    "SOLUSDT", "LINKUSDT", "DOGEUSDT", "NEARUSDT",
    "APTUSDT",  "AVAXUSDT", "DOTUSDT",  "XRPUSDT",
    "ATOMUSDT", "INJUSDT",  "SEIUSDT",  "TIAUSDT",
]
TP_PCT         = 1.05
SL_PCT         = 0.985
EXPIRY_CANDLES = 20
JANELA         = 200
SCORE_MINIMO   = 7
HORA_UTC_MIN   = 5
HORA_UTC_MAX   = 22


# ─────────────────────────────────────────────────
# COLETA HISTÓRICA PAGINADA — BINANCE
# ─────────────────────────────────────────────────
def obter_historico(symbol, interval="15m", dias=30):
    url    = "https://api.binance.com/api/v3/klines"
    fim    = int(datetime.now(timezone.utc).timestamp() * 1000)
    inicio = int((datetime.now(timezone.utc) - timedelta(days=dias)).timestamp() * 1000)
    todos, cursor = [], inicio
    while cursor < fim:
        resp = requests.get(url, params={
            "symbol": symbol, "interval": interval,
            "startTime": cursor, "endTime": fim, "limit": 1000
        }, timeout=15)
        if resp.status_code != 200:
            return None
        batch = resp.json()
        if not batch:
            break
        todos.extend(batch)
        cursor = batch[-1][0] + 1
        time.sleep(0.12)
    if not todos:
        return None
    df = pd.DataFrame(todos, columns=[
        "timestamp","open","high","low","close","volume",
        "close_time","qav","trades","taker_base","taker_quote","ignore"
    ])[["timestamp","open","high","low","close","volume"]].copy()
    for col in ["open","high","low","close","volume"]:
        df[col] = pd.to_numeric(df[col])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.drop_duplicates(subset="timestamp", inplace=True)
    df.set_index("timestamp", inplace=True)
    return df


# ─────────────────────────────────────────────────
# INDICADORES
# ─────────────────────────────────────────────────
def rsi(series, p=14):
    d  = series.diff()
    ag = d.clip(lower=0).ewm(alpha=1/p, min_periods=p, adjust=False).mean()
    al = (-d.clip(upper=0)).ewm(alpha=1/p, min_periods=p, adjust=False).mean()
    return 100 - (100 / (1 + ag / al.replace(0, np.nan)))

def mfi(df, p=14):
    tp  = (df["high"] + df["low"] + df["close"]) / 3
    rmf = tp * df["volume"]
    pos = rmf.where(tp > tp.shift(1), 0)
    neg = rmf.where(tp < tp.shift(1), 0)
    mfr = pos.rolling(p).sum() / neg.rolling(p).sum().replace(0, np.nan)
    return 100 - (100 / (1 + mfr))

def stochastic(df, k=14, d=3):
    lo = df["low"].rolling(k).min()
    hi = df["high"].rolling(k).max()
    pk = (100 * (df["close"] - lo) / (hi - lo).replace(0, np.nan)).rolling(d).mean()
    pd_ = pk.rolling(d).mean()
    return pk, pd_

def squeeze(df, bb_p=20, bb_m=2.0, kc_p=20, kc_m=1.5):
    sma = df["close"].rolling(bb_p).mean()
    std = df["close"].rolling(bb_p).std()
    bb_up = sma + bb_m * std; bb_lo = sma - bb_m * std
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift()).abs(),
        (df["low"]  - df["close"].shift()).abs()
    ], axis=1).max(axis=1)
    atr   = tr.rolling(kc_p).mean()
    smakc = df["close"].rolling(kc_p).mean()
    kc_up = smakc + kc_m * atr; kc_lo = smakc - kc_m * atr
    sq_on = (bb_lo > kc_lo) & (bb_up < kc_up)
    hh  = df["high"].rolling(bb_p).max()
    ll  = df["low"].rolling(bb_p).min()
    mid = (hh + ll) / 2
    mom = (df["close"] - ((mid + sma) / 2)).rolling(bb_p).apply(
        lambda x: np.polyfit(range(len(x)), x, 1)[0], raw=True
    )
    return sq_on, mom

def macd_ind(series, fast=12, slow=26, signal=9):
    ef = series.ewm(span=fast, adjust=False).mean()
    es = series.ewm(span=slow, adjust=False).mean()
    ml = ef - es
    sl = ml.ewm(span=signal, adjust=False).mean()
    return ml, sl, ml - sl


# ─────────────────────────────────────────────────
# DETECTOR v2.1 — SCORE PONDERADO
# ─────────────────────────────────────────────────
def detectar_v21(janela_df: pd.DataFrame, hora_utc: int) -> dict | None:

    if len(janela_df) < JANELA:
        return None

    # Filtro de horário
    if not (HORA_UTC_MIN <= hora_utc <= HORA_UTC_MAX):
        return None

    close   = janela_df["close"]
    rsi_s   = rsi(close)
    mfi_s   = mfi(janela_df)
    pctk, pctd = stochastic(janela_df)
    sq_on, mom = squeeze(janela_df)
    macd_l, macd_sig, macd_hist = macd_ind(close)

    ema9   = close.ewm(span=9,   adjust=False).mean()
    sma20  = close.rolling(20).mean()
    ema200 = close.ewm(span=200, adjust=False).mean()
    vol_ma = janela_df["volume"].rolling(20).mean()

    i = -1

    # ── SQUEEZE: contar candles consecutivos ON antes de liberar ──
    sq_arr = sq_on.values
    sq_consecutivos = 0
    for j in range(len(sq_arr) - 2, max(len(sq_arr) - 40, 0), -1):
        if sq_arr[j]:
            sq_consecutivos += 1
        else:
            break

    # Squeeze deve ter sido ON e agora está OFF (liberado)
    squeeze_liberado = (not sq_on.iloc[i]) and sq_on.iloc[i-1]
    if not squeeze_liberado:
        return None

    # Squeeze qualidade (calibrado: >= 5)
    squeeze_robusto = sq_consecutivos >= 5

    # ── CRITÉRIOS BASE (peso 1 cada) ──
    criterios_base = {
        "Momentum bullish crescente 2c": (mom.iloc[i] > 0) and (mom.iloc[i] > mom.iloc[i-1]),
        "EMA9 > SMA20":                 ema9.iloc[i] > sma20.iloc[i],
        "RSI 35–68":                    35 < rsi_s.iloc[i] < 68,
        "MFI > 48":                     mfi_s.iloc[i] > 48,
        "Stoch %K > %D (<80)":          (pctk.iloc[i] > pctd.iloc[i]) and (pctk.iloc[i] < 80),
        "Volume >= 1.2x":               janela_df["volume"].iloc[i] >= 1.2 * vol_ma.iloc[i],
        "Acima EMA200":                 close.iloc[i] > ema200.iloc[i],
        "Squeeze robusto (>=5c)":       squeeze_robusto,
    }

    # ── CRITÉRIOS BÔNUS (peso 2 cada — valem mais no score) ──
    # RSI < 35 OR MFI < 20 no lookback de 20 candles (v2.1: OR em vez de AND)
    rsi_lb = rsi_s.iloc[-21:-1]
    mfi_lb = mfi_s.iloc[-21:-1]
    oversold = (rsi_lb < 35).any() or (mfi_lb < 20).any()

    # MACD crossover bullish
    macd_cross = (
        macd_l.iloc[i] > macd_sig.iloc[i]
        and macd_l.iloc[i-1] <= macd_sig.iloc[i-1]
    )

    # Ignition Candle >= +2% nos últimos 3 candles
    opens  = janela_df["open"].iloc[-4:-1]
    closes = janela_df["close"].iloc[-4:-1]
    ignition = ((closes - opens) / opens >= 0.02).any()

    # Momentum crescente por 3 candles consecutivos
    mom_forte = (mom.iloc[i] > mom.iloc[i-1] > mom.iloc[i-2]) and (mom.iloc[i] > 0)

    criterios_bonus = {
        "Oversold prévio (RSI<35|MFI<20)": oversold,
        "MACD crossover bullish":           macd_cross,
        "Ignition Candle >= +2%":           ignition,
        "Momentum crescente 3c":            mom_forte,
    }

    # Score ponderado: base vale 1, bônus vale 2
    score_base  = sum(1 for v in criterios_base.values()  if v)
    score_bonus = sum(2 for v in criterios_bonus.values() if v)
    score_total = score_base + score_bonus
    max_score   = len(criterios_base) * 1 + len(criterios_bonus) * 2  # 8 + 8 = 16

    # Mínimo: 7 pontos (sem veto de confirmação dupla)
    if score_total < SCORE_MINIMO:
        return None

    # Score máximo (16) = sinal muito tardio, descartar
    if score_total >= max_score:
        return None

    preco = close.iloc[i]
    return {
        "preco_entrada":  preco * 1.003,
        "score":          score_total,
        "max_score":      max_score,
        "score_base":     score_base,
        "score_bonus":    score_bonus,
        "rsi":            round(rsi_s.iloc[i], 1),
        "mfi":            round(mfi_s.iloc[i], 1),
        "macd_cross":     macd_cross,
        "ignition":       ignition,
        "oversold":       oversold,
        "mom_forte":      mom_forte,
        "sq_candles":     sq_consecutivos,
        "criterios_base": criterios_base,
        "criterios_bonus": criterios_bonus,
    }


# ─────────────────────────────────────────────────
# SIMULAÇÃO DE TRADE
# ─────────────────────────────────────────────────
def simular_trade(df_futuro, preco_entrada):
    tp = preco_entrada * TP_PCT
    sl = preco_entrada * SL_PCT
    for i in range(min(EXPIRY_CANDLES, len(df_futuro))):
        if df_futuro.iloc[i]["high"] >= tp:
            return {"resultado": "WIN",  "retorno_pct": (tp/preco_entrada-1)*100, "candles": i+1}
        if df_futuro.iloc[i]["low"]  <= sl:
            return {"resultado": "LOSS", "retorno_pct": (sl/preco_entrada-1)*100, "candles": i+1}
    pf = df_futuro.iloc[min(EXPIRY_CANDLES-1, len(df_futuro)-1)]["close"]
    return {"resultado": "TIMEOUT", "retorno_pct": (pf/preco_entrada-1)*100, "candles": EXPIRY_CANDLES}


# ─────────────────────────────────────────────────
# BACKTEST POR PAR
# ─────────────────────────────────────────────────
def backtest_par(symbol, df):
    trades, cooldown = [], 0
    for i in range(JANELA, len(df) - EXPIRY_CANDLES - 1):
        if cooldown > 0:
            cooldown -= 1
            continue
        hora_utc = df.index[i].hour
        sinal = detectar_v21(df.iloc[i - JANELA: i], hora_utc)
        if sinal is None:
            continue
        trade = simular_trade(df.iloc[i: i + EXPIRY_CANDLES + 1], sinal["preco_entrada"])
        trades.append({
            "symbol":        symbol,
            "data_sinal":    df.index[i].strftime("%Y-%m-%d %H:%M"),
            "preco_entrada": round(sinal["preco_entrada"], 6),
            "score":         sinal["score"],
            "max_score":     sinal["max_score"],
            "score_base":    sinal["score_base"],
            "score_bonus":   sinal["score_bonus"],
            "rsi":           sinal["rsi"],
            "mfi":           sinal["mfi"],
            "macd_cross":    sinal["macd_cross"],
            "ignition":      sinal["ignition"],
            "oversold":      sinal["oversold"],
            "mom_forte":     sinal["mom_forte"],
            "sq_candles":    sinal["sq_candles"],
            **trade,
        })
        cooldown = 10
    return trades


# ─────────────────────────────────────────────────
# RELATÓRIO COMPARATIVO
# ─────────────────────────────────────────────────
def relatorio(todos):
    print(f"\n{'═'*68}")
    print(f"  📊 RESULTADO BACKTEST v2.1 — CALIBRADO (30 DIAS)")
    print(f"{'═'*68}")

    if not todos:
        print("\n  ❌ Nenhum sinal. Requer calibração adicional.")
        return

    df = pd.DataFrame(todos)
    wins   = df[df["resultado"] == "WIN"]
    losses = df[df["resultado"] == "LOSS"]
    tmout  = df[df["resultado"] == "TIMEOUT"]
    total  = len(df)
    taxa   = len(wins)/total*100

    print(f"\n  {'MÉTRICA':<30} {'v1 (base)':>10} {'v2.1 (refinado)':>15}")
    print(f"  {'─'*30} {'─'*10} {'─'*15}")
    print(f"  {'Total de sinais':<30} {'373':>10} {total:>15}")
    print(f"  {'Taxa de acerto':<30} {'2.4%':>10} {taxa:>14.1f}%")
    print(f"  {'Retorno médio/trade':<30} {'-0.39%':>10} {df['retorno_pct'].mean():>+14.2f}%")
    ret_w = wins['retorno_pct'].mean()  if len(wins)>0  else 0
    ret_l = losses['retorno_pct'].mean() if len(losses)>0 else 0
    ret_t = tmout['retorno_pct'].mean()  if len(tmout)>0  else 0
    print(f"  {'Retorno médio wins':<30} {'+5.00%':>10} {ret_w:>+14.2f}%")
    print(f"  {'Retorno médio losses':<30} {'-1.50%':>10} {ret_l:>+14.2f}%")
    print(f"  {'Retorno médio timeout':<30} {'+0.27%':>10} {ret_t:>+14.2f}%")
    print(f"  {'Wins':<30} {'9 (2.4%)':>10} {len(wins):>4} ({len(wins)/total*100:.1f}%){' ':>6}")
    print(f"  {'Losses':<30} {'169 (45%)':>10} {len(losses):>4} ({len(losses)/total*100:.1f}%){' ':>5}")
    print(f"  {'Timeouts':<30} {'195 (52%)':>10} {len(tmout):>4} ({len(tmout)/total*100:.1f}%){' ':>5}")

    print(f"\n{'─'*68}")
    print(f"  RESULTADO POR PAR")
    print(f"{'─'*68}")
    print(f"  {'Par':<14} {'N':>4} {'W':>4} {'L':>4} {'T':>4} {'Acerto%':>8} {'Ret.Med':>9} {'Sc.Médio':>9}")
    print(f"  {'─'*14} {'─'*4} {'─'*4} {'─'*4} {'─'*4} {'─'*8} {'─'*9} {'─'*9}")
    for sym in df["symbol"].unique():
        s  = df[df["symbol"]==sym]
        w  = len(s[s["resultado"]=="WIN"])
        l  = len(s[s["resultado"]=="LOSS"])
        t  = len(s[s["resultado"]=="TIMEOUT"])
        sc = s["score"].mean()
        print(f"  {sym:<14} {len(s):>4} {w:>4} {l:>4} {t:>4} "
              f"{w/len(s)*100:>7.1f}% {s['retorno_pct'].mean():>+8.2f}% {sc:>8.1f}")

    print(f"\n{'─'*68}")
    print(f"  IMPACTO DOS NOVOS FILTROS (% dos sinais que os têm)")
    print(f"{'─'*68}")
    print(f"  MACD crossover bullish    : {df['macd_cross'].mean()*100:>5.1f}%  | wins com MACD: {(wins['macd_cross'].sum()/len(wins)*100 if len(wins)>0 else 0):.0f}%")
    print(f"  Ignition Candle >= +2%    : {df['ignition'].mean()*100:>5.1f}%  | wins com Ignition: {(wins['ignition'].sum()/len(wins)*100 if len(wins)>0 else 0):.0f}%")
    print(f"  Oversold prévio RSI|MFI   : {df['oversold'].mean()*100:>5.1f}%  | wins com Oversold: {(wins['oversold'].sum()/len(wins)*100 if len(wins)>0 else 0):.0f}%")
    print(f"  Momentum forte (3c)       : {df['mom_forte'].mean()*100:>5.1f}%  | wins com Mom3c: {(wins['mom_forte'].sum()/len(wins)*100 if len(wins)>0 else 0):.0f}%")
    print(f"  Score médio geral         : {df['score'].mean():.1f}/{df['max_score'].iloc[0]}")
    print(f"  Score médio bônus         : {df['score_bonus'].mean():.1f}")

    print(f"\n{'─'*68}")
    print(f"  TODOS OS SINAIS GERADOS")
    print(f"{'─'*68}")
    print(f"  {'Par':<13} {'Data':>17} {'Entrada':>11} {'Res':>8} {'Ret%':>7} {'Sc':>5} {'M':>2} {'I':>2} {'O':>2}")
    for r in df.itertuples():
        ic = "✅" if r.resultado=="WIN" else ("❌" if r.resultado=="LOSS" else "⏳")
        print(f"  {r.symbol:<13} {r.data_sinal:>17} ${r.preco_entrada:>10,.4f} "
              f" {ic}{r.resultado:<5} {r.retorno_pct:>+6.2f}% {r.score:>2}/{r.max_score} "
              f"{'✓' if r.macd_cross else '·':>2} {'✓' if r.ignition else '·':>2} {'✓' if r.oversold else '·':>2}")

    print(f"\n{'═'*68}")
    print(f"  ⚠️  Resultados históricos não garantem performance futura.")
    print(f"{'═'*68}\n")

    df.to_csv("backtest_v21_resultado.csv", index=False)
    print(f"  💾 Salvo em: backtest_v21_resultado.csv\n")


# ─────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n╔══════════════════════════════════════════════╗")
    print("║   BACKTEST v2.1 CALIBRADO — MARCELO VEGA   ║")
    print(f"║   Início: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}            ║")
    print("╚══════════════════════════════════════════════╝\n")

    todos = []
    for symbol in PARES_BACKTEST:
        print(f"  ⬇️  Baixando {symbol} (30 dias, 15m)...")
        df = obter_historico(symbol, "15m", 30)
        if df is None or len(df) < JANELA + EXPIRY_CANDLES + 10:
            print(f"     ⚠️  Dados insuficientes.\n")
            continue
        print(f"     ✅ {len(df)} candles. Analisando com v2.1...")
        t = backtest_par(symbol, df)
        print(f"     📌 {len(t)} sinais.\n")
        todos.extend(t)

    relatorio(todos)
