"""
╔══════════════════════════════════════════════════════════════════╗
║         CRYPTO PUMP — BACKTEST 30 DIAS                         ║
║     Squeeze Release + Confluence Setup Backtest Engine          ║
║     Fonte: Binance Klines históricos (15m)                      ║
╚══════════════════════════════════════════════════════════════════╝
Metodologia:
 - Baixa 30 dias de klines de 15m (~2880 candles por par)
 - Usa janela deslizante de 200 candles para calcular indicadores
 - Ao detectar padrão, simula entrada e verifica resultado
 - Saída: TP (+5%), SL (−1.5%), ou expirado (20 candles = 5h)
 - Calcula taxa de acerto, retorno médio, nº de sinais
"""

import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
import time


# ─────────────────────────────────────────────────
# PARES PARA BACKTEST
# ─────────────────────────────────────────────────
PARES_BACKTEST = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT",
    "ADAUSDT", "LINKUSDT", "DOGEUSDT", "NEARUSDT",
    "APTUSDT", "AVAXUSDT",
]

# ── Parâmetros do trade simulado ──
TP_PCT   = 1.05    # Take Profit: +5%
SL_PCT   = 0.985   # Stop Loss:   −1.5%
EXPIRY_CANDLES = 20  # 20 candles de 15m = 5 horas de timeout

# ── Parâmetros do padrão ──
SCORE_MINIMO = 6
JANELA      = 200  # candles por janela deslizante


# ─────────────────────────────────────────────────
# COLETA HISTÓRICA — BINANCE (paginada)
# ─────────────────────────────────────────────────
def obter_historico_binance(symbol: str, interval: str = "15m", dias: int = 30) -> pd.DataFrame | None:
    """
    Baixa o histórico dos últimos N dias em candles de `interval`.
    Pagina automaticamente em blocos de 1000.
    """
    url = "https://api.binance.com/api/v3/klines"
    fim   = int(datetime.now(timezone.utc).timestamp() * 1000)
    inicio = int((datetime.now(timezone.utc) - timedelta(days=dias)).timestamp() * 1000)

    todos = []
    cursor = inicio

    while cursor < fim:
        resp = requests.get(url, params={
            "symbol":    symbol,
            "interval":  interval,
            "startTime": cursor,
            "endTime":   fim,
            "limit":     1000
        }, timeout=15)

        if resp.status_code != 200:
            print(f"    Erro Binance {resp.status_code} para {symbol}")
            return None

        batch = resp.json()
        if not batch:
            break

        todos.extend(batch)
        # próxima página começa após o último candle recebido
        cursor = batch[-1][0] + 1
        time.sleep(0.15)  # rate-limit

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
# REUTILIZAÇÃO DAS FUNÇÕES DO pump_detector.py
# ─────────────────────────────────────────────────

def calcular_rsi(series, period=14):
    delta = series.diff()
    gain  = delta.clip(lower=0)
    loss  = -delta.clip(upper=0)
    ag = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    al = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = ag / al.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def calcular_mfi(df, period=14):
    tp  = (df["high"] + df["low"] + df["close"]) / 3
    rmf = tp * df["volume"]
    pos = rmf.where(tp > tp.shift(1), 0)
    neg = rmf.where(tp < tp.shift(1), 0)
    mfr = pos.rolling(period).sum() / neg.rolling(period).sum().replace(0, np.nan)
    return 100 - (100 / (1 + mfr))


def calcular_stochastic(df, k_period=14, d_period=3):
    lmin = df["low"].rolling(k_period).min()
    hmax = df["high"].rolling(k_period).max()
    k_raw = 100 * (df["close"] - lmin) / (hmax - lmin).replace(0, np.nan)
    pct_k = k_raw.rolling(d_period).mean()
    pct_d = pct_k.rolling(d_period).mean()
    return pct_k, pct_d


def calcular_squeeze(df, bb_period=20, bb_mult=2.0, kc_period=20, kc_mult=1.5):
    sma_bb = df["close"].rolling(bb_period).mean()
    std_bb = df["close"].rolling(bb_period).std()
    bb_up  = sma_bb + bb_mult * std_bb
    bb_lo  = sma_bb - bb_mult * std_bb

    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift()).abs(),
        (df["low"]  - df["close"].shift()).abs()
    ], axis=1).max(axis=1)
    atr    = tr.rolling(kc_period).mean()
    sma_kc = df["close"].rolling(kc_period).mean()
    kc_up  = sma_kc + kc_mult * atr
    kc_lo  = sma_kc - kc_mult * atr

    squeeze_on = (bb_lo > kc_lo) & (bb_up < kc_up)

    hh = df["high"].rolling(bb_period).max()
    ll = df["low"].rolling(bb_period).min()
    mid = (hh + ll) / 2
    delta_c = df["close"] - ((mid + sma_bb) / 2)
    momentum = delta_c.rolling(bb_period).apply(
        lambda x: np.polyfit(range(len(x)), x, 1)[0], raw=True
    )
    return squeeze_on, momentum


def verificar_padrao_em_janela(janela_df: pd.DataFrame) -> dict | None:
    """
    Aplica os indicadores em uma janela histórica e verifica o padrão principal.
    Retorna dict com o resultado ou None.
    """
    if len(janela_df) < JANELA:
        return None

    rsi            = calcular_rsi(janela_df["close"])
    mfi            = calcular_mfi(janela_df)
    pct_k, pct_d   = calcular_stochastic(janela_df)
    squeeze_on, mom = calcular_squeeze(janela_df)

    ema9   = janela_df["close"].ewm(span=9,   adjust=False).mean()
    sma20  = janela_df["close"].rolling(20).mean()
    ema200 = janela_df["close"].ewm(span=200, adjust=False).mean()
    vol_ma = janela_df["volume"].rolling(20).mean()

    i = -1
    # Squeeze liberado = estava ON, agora OFF
    sq_liberado = (not squeeze_on.iloc[i]) and squeeze_on.iloc[i-1]

    criterios = {
        "Squeeze Liberado":    sq_liberado,
        "Momentum Bullish ↑":  (mom.iloc[i] > 0) and (mom.iloc[i] > mom.iloc[i-1]),
        "EMA9 > SMA20":        ema9.iloc[i] > sma20.iloc[i],
        "RSI > 40":            rsi.iloc[i] > 40,
        "Stoch %K > %D":       (pct_k.iloc[i] > pct_d.iloc[i]) and (pct_k.iloc[i] < 80),
        "Volume OK":           janela_df["volume"].iloc[i] > vol_ma.iloc[i],
        "MFI > 50":            mfi.iloc[i] > 50,
        "Acima EMA200":        janela_df["close"].iloc[i] > ema200.iloc[i],
        "RSI < 75":            rsi.iloc[i] < 75,
    }
    score = sum(1 for v in criterios.values() if v)

    if score < SCORE_MINIMO or not sq_liberado:
        return None

    return {
        "preco_entrada": janela_df["close"].iloc[i] * 1.003,
        "score": score,
    }


# ─────────────────────────────────────────────────
# SIMULAÇÃO DE TRADE
# ─────────────────────────────────────────────────

def simular_trade(df_futuro: pd.DataFrame, preco_entrada: float) -> dict:
    """
    Dado o DataFrame dos candles APÓS o sinal, simula a entrada e verifica:
    - TP: preço sobe >= 5% em qualquer candle → WIN
    - SL: preço cai <= −1.5% em qualquer candle → LOSS
    - Expirado: nenhum dos dois acontece em EXPIRY_CANDLES candles → TIMEOUT (sem resultado)
    """
    tp_alvo = preco_entrada * TP_PCT
    sl_alvo = preco_entrada * SL_PCT

    for i in range(min(EXPIRY_CANDLES, len(df_futuro))):
        high  = df_futuro.iloc[i]["high"]
        low   = df_futuro.iloc[i]["low"]
        close = df_futuro.iloc[i]["close"]

        if high >= tp_alvo:
            retorno = ((tp_alvo / preco_entrada) - 1) * 100
            return {"resultado": "WIN", "retorno_pct": retorno, "candles_ate_saida": i+1}
        if low <= sl_alvo:
            retorno = ((sl_alvo / preco_entrada) - 1) * 100
            return {"resultado": "LOSS", "retorno_pct": retorno, "candles_ate_saida": i+1}

    # Timeout: fecha ao preço de fechamento do último candle verificado
    preco_final = df_futuro.iloc[min(EXPIRY_CANDLES-1, len(df_futuro)-1)]["close"]
    retorno = ((preco_final / preco_entrada) - 1) * 100
    return {"resultado": "TIMEOUT", "retorno_pct": retorno, "candles_ate_saida": EXPIRY_CANDLES}


# ─────────────────────────────────────────────────
# ENGINE DE BACKTEST
# ─────────────────────────────────────────────────

def rodar_backtest_par(symbol: str, df: pd.DataFrame) -> list[dict]:
    """
    Varre o histórico com janela deslizante e simula todos os trades.
    Aplica cooldown: após um sinal, ignora os próximos 10 candles.
    """
    trades = []
    cooldown = 0  # candles restantes de pausa após um sinal

    for i in range(JANELA, len(df) - EXPIRY_CANDLES - 1):
        if cooldown > 0:
            cooldown -= 1
            continue

        janela  = df.iloc[i - JANELA: i]
        sinal   = verificar_padrao_em_janela(janela)

        if sinal is None:
            continue

        # Simular trade nos candles futuros
        df_futuro = df.iloc[i: i + EXPIRY_CANDLES + 1]
        trade     = simular_trade(df_futuro, sinal["preco_entrada"])
        trade["symbol"]        = symbol
        trade["data_sinal"]    = df.index[i].strftime("%Y-%m-%d %H:%M")
        trade["preco_entrada"] = round(sinal["preco_entrada"], 6)
        trade["score"]         = sinal["score"]
        trades.append(trade)

        cooldown = 10  # evitar sinais sobrepostos no mesmo pump

    return trades


# ─────────────────────────────────────────────────
# RELATÓRIO
# ─────────────────────────────────────────────────

def exibir_relatorio(todos_trades: list[dict]):
    df = pd.DataFrame(todos_trades)
    if df.empty:
        print("\n  ❌ Nenhum sinal foi gerado em 30 dias para os pares testados.")
        return

    wins    = df[df["resultado"] == "WIN"]
    losses  = df[df["resultado"] == "LOSS"]
    timeout = df[df["resultado"] == "TIMEOUT"]

    total = len(df)
    taxa  = len(wins) / total * 100

    print(f"\n{'═'*64}")
    print(f"  📊 RESULTADO GERAL DO BACKTEST (30 dias)")
    print(f"{'═'*64}")
    print(f"  Total de sinais gerados : {total}")
    print(f"  ✅ Wins (TP atingido)   : {len(wins)}  ({len(wins)/total*100:.1f}%)")
    print(f"  ❌ Losses (SL atingido) : {len(losses)} ({len(losses)/total*100:.1f}%)")
    print(f"  ⏳ Timeout (5h sem saída): {len(timeout)} ({len(timeout)/total*100:.1f}%)")
    print(f"  {'─'*40}")
    print(f"  Taxa de acerto          : {taxa:.1f}%")
    print(f"  Retorno médio por trade : {df['retorno_pct'].mean():+.2f}%")
    print(f"  Retorno médio (wins)    : {wins['retorno_pct'].mean():+.2f}%" if len(wins) > 0 else "  Retorno médio (wins)    : —")
    print(f"  Retorno médio (losses)  : {losses['retorno_pct'].mean():+.2f}%" if len(losses) > 0 else "  Retorno médio (losses)  : —")
    print(f"  Maior ganho             : {df['retorno_pct'].max():+.2f}%")
    print(f"  Maior perda             : {df['retorno_pct'].min():+.2f}%")
    print(f"  Média de candles até saída: {df['candles_ate_saida'].mean():.0f} candles ({df['candles_ate_saida'].mean()*15/60:.1f}h)")

    print(f"\n{'─'*64}")
    print(f"  📋 RESULTADO POR PAR")
    print(f"{'─'*64}")
    print(f"  {'Par':<14} {'Sinais':>7} {'Wins':>6} {'Losses':>7} {'Timeout':>8} {'Acerto%':>8} {'Retorno Médio':>14}")
    print(f"  {'─'*14} {'─'*7} {'─'*6} {'─'*7} {'─'*8} {'─'*8} {'─'*14}")

    for symbol in df["symbol"].unique():
        sub  = df[df["symbol"] == symbol]
        w    = len(sub[sub["resultado"] == "WIN"])
        l    = len(sub[sub["resultado"] == "LOSS"])
        t    = len(sub[sub["resultado"] == "TIMEOUT"])
        n    = len(sub)
        ta   = w/n*100
        ret  = sub["retorno_pct"].mean()
        print(f"  {symbol:<14} {n:>7} {w:>6} {l:>7} {t:>8} {ta:>7.1f}% {ret:>+13.2f}%")

    print(f"\n{'─'*64}")
    print(f"  📝 TODOS OS SINAIS GERADOS (últimos 15 ou todos):")
    print(f"{'─'*64}")
    print(f"  {'Par':<14} {'Data':>17} {'Entrada':>12} {'Resultado':>10} {'Retorno':>8} {'Score':>6}")
    print(f"  {'─'*14} {'─'*17} {'─'*12} {'─'*10} {'─'*8} {'─'*6}")

    subset = df.tail(30).itertuples()
    for r in subset:
        icone = "✅" if r.resultado == "WIN" else ("❌" if r.resultado == "LOSS" else "⏳")
        print(f"  {r.symbol:<14} {r.data_sinal:>17} ${r.preco_entrada:>11,.4f} "
              f"  {icone} {r.resultado:<6} {r.retorno_pct:>+7.2f}%  {r.score}/9")

    print(f"\n{'═'*64}")
    print(f"  Aviso: simulação histórica. Resultados passados não garantem futuros.")
    print(f"{'═'*64}\n")

    # Salvar CSV
    df.to_csv("backtest_resultado.csv", index=False)
    print(f"  💾 Resultado completo salvo em: backtest_resultado.csv\n")


# ─────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n╔══════════════════════════════════════════╗")
    print("║   BACKTEST — 30 DIAS — MARCELO VEGA    ║")
    print(f"║   Início: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}          ║")
    print("╚══════════════════════════════════════════╝\n")

    todos_trades = []

    for symbol in PARES_BACKTEST:
        print(f"  ⬇️  Baixando histórico de {symbol} (30 dias, 15m)...")
        df_hist = obter_historico_binance(symbol, interval="15m", dias=30)

        if df_hist is None or len(df_hist) < JANELA + EXPIRY_CANDLES + 10:
            print(f"     ⚠️  Dados insuficientes para {symbol}, pulando.\n")
            continue

        print(f"     ✅ {len(df_hist)} candles baixados. Rodando backtest...")
        trades = rodar_backtest_par(symbol, df_hist)
        print(f"     📌 {len(trades)} sinais encontrados em {symbol}\n")
        todos_trades.extend(trades)

    exibir_relatorio(todos_trades)
