"""
╔══════════════════════════════════════════════════════════════════╗
║     CRYPTO PUMP BACKTEST v2 — Marcelo Vega                     ║
║     Detector Refinado: MACD + Ignition Candle + 8 Regras       ║
╚══════════════════════════════════════════════════════════════════╝

NOVIDADES v2 vs v1:
  + MACD (12/26/9) como confirmação de momentum
  + Ignition Candle: candle >= +2% nos últimos 3 candles
  + RSI/MFI lookback: precisam ter tocado oversold nos últimos 20 candles
  + Squeeze comprimido >= 8 candles consecutivos antes de liberar
  + Filtro de horário: apenas 05h–22h UTC
  + Volume: >= 1.5x a média (antes era apenas > média)
  + EMA200 no 1h (macro filter externo — simplificado aqui)
  + Score máximo 8/9 (score 9 descartado)
  + Altcoins apenas como alvo (BTC/ETH/BNB/ADA excluídos como alvos)
  + Momentum crescente em 3 candles consecutivos

TP  = +5%    SL = -1.5%    Timeout = 20 candles (5h)
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
    "APTUSDT",  "AVAXUSDT", "DOTUSDT",  "MATICUSDT",
    "XRPUSDT",  "ADAUSDT",  "BNBUSDT",  "ATOMUSDT",
]
# BTC/ETH removidos como alvos (usados só para contexto macro)
PARES_MACRO_VETO = {"BTCUSDT", "ETHUSDT", "BNBUSDT", "ADAUSDT"}

TP_PCT          = 1.05
SL_PCT          = 0.985
EXPIRY_CANDLES  = 20
JANELA          = 200
SCORE_MINIMO    = 6

HORA_UTC_MIN    = 5   # 02:00 Brasília
HORA_UTC_MAX    = 22  # 19:00 Brasília


# ─────────────────────────────────────────────────
# COLETA HISTÓRICA PAGINADA — BINANCE
# ─────────────────────────────────────────────────
def obter_historico(symbol, interval="15m", dias=30):
    url = "https://api.binance.com/api/v3/klines"
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
    pctk = 100 * (df["close"] - lo) / (hi - lo).replace(0, np.nan)
    smooth_k = pctk.rolling(d).mean()
    pctd     = smooth_k.rolling(d).mean()
    return smooth_k, pctd

def squeeze(df, bb_p=20, bb_m=2.0, kc_p=20, kc_m=1.5):
    sma = df["close"].rolling(bb_p).mean()
    std = df["close"].rolling(bb_p).std()
    bb_up = sma + bb_m * std;  bb_lo = sma - bb_m * std
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift()).abs(),
        (df["low"]  - df["close"].shift()).abs()
    ], axis=1).max(axis=1)
    atr  = tr.rolling(kc_p).mean()
    smkc = df["close"].rolling(kc_p).mean()
    kc_up = smkc + kc_m * atr; kc_lo = smkc - kc_m * atr
    sq_on = (bb_lo > kc_lo) & (bb_up < kc_up)
    hh  = df["high"].rolling(bb_p).max()
    ll  = df["low"].rolling(bb_p).min()
    mid = (hh + ll) / 2
    mom = (df["close"] - ((mid + sma) / 2)).rolling(bb_p).apply(
        lambda x: np.polyfit(range(len(x)), x, 1)[0], raw=True
    )
    return sq_on, mom

def macd(series, fast=12, slow=26, signal=9):
    """Retorna (macd_line, signal_line, histogram)."""
    ema_f = series.ewm(span=fast, adjust=False).mean()
    ema_s = series.ewm(span=slow, adjust=False).mean()
    macd_line   = ema_f - ema_s
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram   = macd_line - signal_line
    return macd_line, signal_line, histogram


# ─────────────────────────────────────────────────
# DETECTOR v2
# ─────────────────────────────────────────────────
def detectar_v2(janela_df: pd.DataFrame, hora_utc: int) -> dict | None:

    if len(janela_df) < JANELA:
        return None

    # ── Filtro de horário ───────────────────────
    if not (HORA_UTC_MIN <= hora_utc <= HORA_UTC_MAX):
        return None

    # ── Cálculo dos indicadores ──────────────────
    close   = janela_df["close"]
    rsi_s   = rsi(close)
    mfi_s   = mfi(janela_df)
    pctk, pctd = stochastic(janela_df)
    sq_on, mom = squeeze(janela_df)
    macd_l, macd_sig, macd_hist = macd(close)

    ema9    = close.ewm(span=9,   adjust=False).mean()
    sma20   = close.rolling(20).mean()
    ema200  = close.ewm(span=200, adjust=False).mean()
    vol_ma  = janela_df["volume"].rolling(20).mean()

    i = -1  # vela atual

    # ── REGRA 1: Squeeze comprimido >= 8 candles antes de liberar ──
    sq_arr = sq_on.values
    # Conta quantos candles consecutivos estavam ON antes de agora
    sq_consecutivos = 0
    for j in range(len(sq_arr) - 2, max(len(sq_arr) - 30, 0), -1):
        if sq_arr[j]:
            sq_consecutivos += 1
        else:
            break
    squeeze_valido = (not sq_on.iloc[i]) and sq_on.iloc[i-1] and (sq_consecutivos >= 8)

    if not squeeze_valido:
        return None

    # ── REGRA 2: Momentum crescente por >= 3 candles consecutivos ──
    mom_crescente_3 = (
        mom.iloc[i]   > mom.iloc[i-1] > mom.iloc[i-2]
        and mom.iloc[i] > 0
    )

    # ── REGRA 3: RSI/MFI tiveram oversold nos últimos 20 candles ──
    rsi_lookback  = rsi_s.iloc[-21:-1]
    mfi_lookback  = mfi_s.iloc[-21:-1]
    rsi_oversold  = (rsi_lookback < 35).any()
    mfi_oversold  = (mfi_lookback < 20).any()
    oversold_recente = rsi_oversold and mfi_oversold

    # ── REGRA 4: Ignition Candle (>= +2% em um dos últimos 3 candles) ──
    opens  = janela_df["open"].iloc[-4:-1]
    closes = janela_df["close"].iloc[-4:-1]
    ignition = ((closes - opens) / opens >= 0.02).any()

    # ── REGRA 5: MACD crossover bullish (linha cruzou acima do sinal) ──
    macd_cross = (
        macd_l.iloc[i] > macd_sig.iloc[i]
        and macd_l.iloc[i-1] <= macd_sig.iloc[i-1]
    )
    macd_hist_positivo = macd_hist.iloc[i] > 0

    # ── REGRA 6: Volume >= 1.5x média ──
    volume_forte = janela_df["volume"].iloc[i] >= 1.5 * vol_ma.iloc[i]

    # ── Critérios base (score) ──────────────────
    criterios = {
        "Squeeze >= 8 candles":   squeeze_valido,        # obrigatório
        "Momentum crescente 3c":  mom_crescente_3,
        "Oversold RSI<35+MFI<20": oversold_recente,
        "Ignition Candle +2%":    ignition,
        "MACD crossover":         macd_cross,
        "MACD hist positivo":     macd_hist_positivo,
        "EMA9 > SMA20":           ema9.iloc[i] > sma20.iloc[i],
        "RSI 38–65":              38 < rsi_s.iloc[i] < 65,
        "MFI > 50":               mfi_s.iloc[i] > 50,
        "Stoch %K > %D":          (pctk.iloc[i] > pctd.iloc[i]) and (pctk.iloc[i] < 80),
        "Volume >= 1.5x":         volume_forte,
        "Acima EMA200":           close.iloc[i] > ema200.iloc[i],
    }
    score = sum(1 for v in criterios.values() if v)

    # Score ajustado: exigir mínimo 7/12 E os critérios chave
    # Critérios obrigatórios além do squeeze: oversold + ignition ou MACD
    tem_confirmacao = oversold_recente and (ignition or macd_cross)

    if score < 7 or not tem_confirmacao:
        return None

    # Score máximo (12/12) pode ser tarde demais — descartar
    if score >= 12:
        return None

    preco = close.iloc[i]
    return {
        "preco_entrada": preco * 1.003,
        "score":         score,
        "total":         len(criterios),
        "rsi":           round(rsi_s.iloc[i], 1),
        "mfi":           round(mfi_s.iloc[i], 1),
        "macd_cross":    macd_cross,
        "ignition":      ignition,
        "oversold":      oversold_recente,
        "sq_candles":    sq_consecutivos,
        "criterios":     criterios,
    }


# ─────────────────────────────────────────────────
# SIMULAÇÃO DE TRADE
# ─────────────────────────────────────────────────
def simular_trade(df_futuro, preco_entrada):
    tp = preco_entrada * TP_PCT
    sl = preco_entrada * SL_PCT
    for i in range(min(EXPIRY_CANDLES, len(df_futuro))):
        h = df_futuro.iloc[i]["high"]
        l = df_futuro.iloc[i]["low"]
        if h >= tp:
            return {"resultado": "WIN",  "retorno_pct": (tp/preco_entrada-1)*100, "candles": i+1}
        if l <= sl:
            return {"resultado": "LOSS", "retorno_pct": (sl/preco_entrada-1)*100, "candles": i+1}
    preco_final = df_futuro.iloc[min(EXPIRY_CANDLES-1, len(df_futuro)-1)]["close"]
    return {"resultado": "TIMEOUT", "retorno_pct": (preco_final/preco_entrada-1)*100, "candles": EXPIRY_CANDLES}


# ─────────────────────────────────────────────────
# BACKTEST POR PAR
# ─────────────────────────────────────────────────
def backtest_par(symbol, df):
    trades   = []
    cooldown = 0
    for i in range(JANELA, len(df) - EXPIRY_CANDLES - 1):
        if cooldown > 0:
            cooldown -= 1
            continue
        hora_utc = df.index[i].hour
        janela   = df.iloc[i - JANELA: i]
        sinal    = detectar_v2(janela, hora_utc)
        if sinal is None:
            continue
        df_fut = df.iloc[i: i + EXPIRY_CANDLES + 1]
        trade  = simular_trade(df_fut, sinal["preco_entrada"])
        trades.append({
            "symbol":        symbol,
            "data_sinal":    df.index[i].strftime("%Y-%m-%d %H:%M"),
            "preco_entrada": round(sinal["preco_entrada"], 6),
            "score":         sinal["score"],
            "total":         sinal["total"],
            "rsi":           sinal["rsi"],
            "mfi":           sinal["mfi"],
            "macd_cross":    sinal["macd_cross"],
            "ignition":      sinal["ignition"],
            "oversold":      sinal["oversold"],
            "sq_candles":    sinal["sq_candles"],
            **trade,
        })
        cooldown = 10
    return trades


# ─────────────────────────────────────────────────
# RELATÓRIO
# ─────────────────────────────────────────────────
def relatorio(todos):
    df = pd.DataFrame(todos)
    if df.empty:
        print("\n  ❌ Nenhum sinal gerado. Regras muito restritivas.")
        return

    wins    = df[df["resultado"] == "WIN"]
    losses  = df[df["resultado"] == "LOSS"]
    timeout = df[df["resultado"] == "TIMEOUT"]
    total   = len(df)
    taxa    = len(wins)/total*100

    print(f"\n{'═'*64}")
    print(f"  📊 RESULTADO BACKTEST v2 — 30 DIAS")
    print(f"{'═'*64}")
    print(f"  Total de sinais   : {total}")
    print(f"  ✅ Wins           : {len(wins)}  ({len(wins)/total*100:.1f}%)")
    print(f"  ❌ Losses         : {len(losses)} ({len(losses)/total*100:.1f}%)")
    print(f"  ⏳ Timeout        : {len(timeout)} ({len(timeout)/total*100:.1f}%)")
    print(f"  {'─'*40}")
    print(f"  Taxa de acerto    : {taxa:.1f}%")
    print(f"  Retorno médio/trade: {df['retorno_pct'].mean():+.2f}%")
    retorno_wins  = wins['retorno_pct'].mean()  if len(wins)>0  else 0
    retorno_loss  = losses['retorno_pct'].mean() if len(losses)>0 else 0
    retorno_time  = timeout['retorno_pct'].mean() if len(timeout)>0 else 0
    print(f"  Retorno médio wins : {retorno_wins:+.2f}%")
    print(f"  Retorno médio loss : {retorno_loss:+.2f}%")
    print(f"  Retorno médio tmout: {retorno_time:+.2f}%")
    print(f"  Maior ganho        : {df['retorno_pct'].max():+.2f}%")
    print(f"  Maior perda        : {df['retorno_pct'].min():+.2f}%")

    print(f"\n{'─'*64}")
    print(f"  RESULTADO POR PAR")
    print(f"{'─'*64}")
    print(f"  {'Par':<13} {'N':>4} {'W':>3} {'L':>4} {'T':>4} {'Acerto%':>8} {'Ret.Med':>8}")
    for sym in df["symbol"].unique():
        s = df[df["symbol"]==sym]
        w = len(s[s["resultado"]=="WIN"])
        l = len(s[s["resultado"]=="LOSS"])
        t = len(s[s["resultado"]=="TIMEOUT"])
        print(f"  {sym:<13} {len(s):>4} {w:>3} {l:>4} {t:>4} {w/len(s)*100:>7.1f}% {s['retorno_pct'].mean():>+7.2f}%")

    print(f"\n{'─'*64}")
    print(f"  ANÁLISE DOS NOVOS FILTROS")
    print(f"{'─'*64}")
    print(f"  Sinais com MACD crossover : {df['macd_cross'].sum()} ({df['macd_cross'].mean()*100:.0f}%)")
    print(f"  Sinais com Ignition (+2%) : {df['ignition'].sum()} ({df['ignition'].mean()*100:.0f}%)")
    print(f"  Sinais com Oversold prévio: {df['oversold'].sum()} ({df['oversold'].mean()*100:.0f}%)")
    print(f"  Squeeze médio comprimido  : {df['sq_candles'].mean():.1f} candles")
    print(f"  Score médio dos sinais    : {df['score'].mean():.1f}/{df['total'].iloc[0]}")
    print()

    # Tabela de todos os trades
    print(f"  {'Par':<13} {'Data':>17} {'Entrada':>12} {'Res':>8} {'Ret%':>7} {'Sc':>4} {'MACD':>5} {'Ign':>4}")
    print(f"  {'─'*13} {'─'*17} {'─'*12} {'─'*8} {'─'*7} {'─'*4} {'─'*5} {'─'*4}")
    for r in df.itertuples():
        ic = "✅" if r.resultado=="WIN" else ("❌" if r.resultado=="LOSS" else "⏳")
        mc = "✓" if r.macd_cross else "·"
        ig = "✓" if r.ignition else "·"
        print(f"  {r.symbol:<13} {r.data_sinal:>17} ${r.preco_entrada:>11,.4f} "
              f" {ic}{r.resultado:<5} {r.retorno_pct:>+6.2f}% {r.score:>2}/{r.total} {mc:>5} {ig:>4}")

    print(f"\n{'═'*64}")
    df.to_csv("backtest_v2_resultado.csv", index=False)
    print(f"  💾 Salvo em: backtest_v2_resultado.csv\n")


# ─────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n╔══════════════════════════════════════════╗")
    print("║   BACKTEST v2 + MACD + IGNITION CANDLE ║")
    print(f"║   Início: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}          ║")
    print("╚══════════════════════════════════════════╝\n")

    todos = []
    for symbol in PARES_BACKTEST:
        print(f"  ⬇️  Baixando {symbol}...")
        df = obter_historico(symbol, "15m", 30)
        if df is None or len(df) < JANELA + EXPIRY_CANDLES + 10:
            print(f"     ⚠️  Dados insuficientes.\n")
            continue
        print(f"     ✅ {len(df)} candles. Analisando...")
        t = backtest_par(symbol, df)
        print(f"     📌 {len(t)} sinais v2.\n")
        todos.extend(t)

    relatorio(todos)
