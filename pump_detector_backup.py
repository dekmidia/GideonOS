"""
╔══════════════════════════════════════════════════════════════════╗
║           GIDEON SENTINEL — LARANJA MECÂNICA                    ║
║     ESTRATÉGIA MULTI-TIMEFRAME (30M, 1H, 4H)                    ║
║     Fontes: Binance (Klines) + CoinGecko (rank/vol)             ║
╚══════════════════════════════════════════════════════════════════╝
"""

import requests
import pandas as pd
import numpy as np
from datetime import datetime
import time
import os
from dotenv import load_dotenv
import concurrent.futures

# Carrega variáveis de ambiente do arquivo .env
load_dotenv()

# ─────────────────────────────────────────────────
# CONFIGURAÇÕES TÉCNICAS
# ─────────────────────────────────────────────────
LISTA_PRIORIDADE = [
    'BTCUSDT', '1INCHUSDT', 'AAVEUSDT', 'ACEUSDT', 'ADAUSDT', 'AEVOUSDT', 'AGLDUSDT', 'ALGOUSDT', 'ALTUSDT', 
    'ANKRUSDT', 'APEUSDT', 'ARPAUSDT', 'ATAUSDT', 'ATOMUSDT', 'AUCTIONUSDT', 'AVAXUSDT', 'AXSUSDT', 
    'BANANAUSDT', 'BATUSDT', 'BLURUSDT', 'BNBUSDT', 'BNTUSDT', 'BOMEUSDT', 'CAKEUSDT', 'CATIUSDT', 
    'CELOUSDT', 'CHESSUSDT', 'CHRUSDT', 'CHZUSDT', 'CKBUSDT', 'DARUSDT', 'DOGEUSDT', 'DOGSUSDT', 
    'DOTUSDT', 'DUSKUSDT', 'DYDXUSDT', 'EGLDUSDT', 'EIGENUSDT', 'ENJUSDT', 'ENSUSDT', 'ETHUSDT', 
    'FILUSDT', 'FLOKIUSDT', 'FLOWUSDT', 'FLUXUSDT', 'GALAUSDT', 'GHSTUSDT', 'GLMRUSDT', 'GLMUSDT', 
    'GMTUSDT', 'GMXUSDT', 'GRTUSDT', 'GTCUSDT', 'GUSDT', 'HBARUSDT', 'HIGHUSDT', 'HMSTRUSDT', 
    'HOOKUSDT', 'ILVUSDT', 'IMXUSDT', 'INJUSDT', 'IOSTUSDT', 'IOTAUSDT', 'IOUSDT', 'JASMYUSDT', 
    'JOEUSDT', 'JTOUSDT', 'KNCUSDT', 'KSMUSDT', 'LDOUSDT', 'LINKUSDT', 'LISTAUSDT', 'LTCUSDT', 
    'LUNAUSDT', 'MANAUSDT', 'MANTAUSDT', 'METISUSDT', 'MINAUSDT', 'MOVRUSDT', 'NEARUSDT', 'NEOUSDT', 
    'NFPUSDT', 'ONTUSDT', 'OPUSDT', 'ORDIUSDT', 'OXTUSDT', 'PENDLEUSDT', 'PEOPLEUSDT', 'PERPUSDT', 
    'PIXELUSDT', 'POLUSDT', 'POLYXUSDT', 'POWRUSDT', 'PYTHUSDT', 'QNTUSDT', 'QUICKUSDT', 'RAREUSDT', 
    'RENDERUSDT', 'RIFUSDT', 'RLCUSDT', 'RUNEUSDT', 'SANDUSDT', 'SCRUSDT', 'SEIUSDT', 'SOLUSDT', 
    'STORJUSDT', 'STRKUSDT', 'SUIUSDT', 'SUNUSDT', 'SUSHIUSDT', 'SYSUSDT', 'THETAUSDT', 'TIAUSDT', 
    'TLMUSDT', 'TRXUSDT', 'UNIUSDT', 'VETUSDT', 'WAXPUSDT', 'WIFUSDT', 'XRPUSDT', 'YFIUSDT', 'YGGUSDT'
]

SIMBOLOS_BASE = [] 
SIMBOLOS_POR_CICLO = 10 

# CONFIGURAÇÃO TELEGRAM
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "") 
_raw_chat_ids = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_CHAT_IDS = [id.strip() for id in _raw_chat_ids.split(",") if id.strip()]

LIMITE_CANDLES  = 100   
COINGECKO_RANK  = 500   
VOLUME_MIN_24H  = 3_000_000 

# PERFIS LARANJA MECÂNICA (SHORT)
PERFIS_MECANICA = {
    "30m": {"tp": 0.975, "sl": 1.050, "emoji": "🕒"}, # -2.5% / +5%
    "1h":  {"tp": 0.950, "sl": 1.100, "emoji": "🕐"}, # -5% / +10%
    "4h":  {"tp": 0.950, "sl": 1.100, "emoji": "🕓"}  # -5% / +10%
}

# PERFIS RSI MOMENTUM (LONG)
PERFIS_RSI_MOMENTUM = {
    "1m":  {"tp": 1.015, "sl": 0.990, "emoji": "🚀"}, # +1.5% / -1.0%
    "5m":  {"tp": 1.030, "sl": 0.980, "emoji": "⚡"}, # +3.0% / -2.0%
    "15m": {"tp": 1.050, "sl": 0.970, "emoji": "💎"}  # +5.0% / -3.0%
}

_PROXIMO_INDICE_ROTATIVO = 0

# ─────────────────────────────────────────────────
# UTILITÁRIOS — NOTIFICAÇÕES
# ─────────────────────────────────────────────────
def enviar_telegram(mensagem: str):
    print(f"\n📡 [SENTINELA] Gerando Alerta:\n{mensagem}\n")
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_IDS: return
    for chat_id in TELEGRAM_CHAT_IDS:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": chat_id, "text": mensagem, "parse_mode": "Markdown"}
        try:
            requests.post(url, json=payload, timeout=20)
        except Exception as e:
            print(f"  ⚠️ Erro de conexão com Telegram ({chat_id}): {e}")

# ─────────────────────────────────────────────────
# COLETA — BINANCE
# ─────────────────────────────────────────────────
def obter_todos_simbolos_binance() -> list[str]:
    try:
        url = "https://api.binance.com/api/v3/exchangeInfo"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return [s['symbol'] for s in data['symbols'] if s['symbol'].endswith('USDT') and s['status'] == 'TRADING']
    except Exception as e:
        print(f"  ⚠️ Erro ao buscar símbolos da Binance: {e}")
    return []

def obter_klines(symbol: str, interval: str, limit: int = LIMITE_CANDLES) -> pd.DataFrame | None:
    # BTCDOMUSDT só existe nos Futuros
    base_url = "https://fapi.binance.com/fapi/v1/klines" if "DOM" in symbol else "https://api.binance.com/api/v3/klines"
    try:
        resp = requests.get(base_url, params={"symbol": symbol, "interval": interval, "limit": limit}, timeout=10)
        if resp.status_code != 200: return None
        raw = resp.json()
        df = pd.DataFrame(raw, columns=[
            "timestamp","open","high","low","close","volume",
            "close_time","qav","trades","taker_base","taker_quote","ignore"
        ])
        df = df[["timestamp","open","high","low","close","volume"]].copy()
        for col in ["open","high","low","close","volume"]:
            df[col] = pd.to_numeric(df[col])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)
        return df
    except:
        return None

def calcular_atr(df: pd.DataFrame, period: int = 14) -> float:
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    atr = true_range.rolling(period).mean().iloc[-1]
    return atr

def estimar_tempo_alvo(preco: float, alvo: float, atr: float) -> int:
    distancia = abs(preco - alvo)
    if atr == 0 or np.isnan(atr): return 0
    candles = distancia / (atr * 0.7)
    return int(round(max(1, candles)))

# ─────────────────────────────────────────────────
# INDICADORES & DETECÇÃO
# ─────────────────────────────────────────────────
def calcular_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def detectar_laranja_mecanica(df: pd.DataFrame, interval: str) -> dict | None:
    """Estratégia Laranja Mecânica: Varredura de Liquidez."""
    if df is None or len(df) < 30: return None
    
    gatilho = df.iloc[-1]
    df_caixote = df.iloc[-7:-1] 
    
    max_recent = df_caixote["high"].max()
    min_recent = df_caixote["low"].min()
    range_caixote = (max_recent / min_recent - 1) * 100
    
    if range_caixote > 8.0: return None
    
    corpo_gatilho = abs(gatilho["close"] - gatilho["open"]) / gatilho["open"] * 100
    if corpo_gatilho > 3.0: return None
        
    pavio_superior = (gatilho["high"] - max(gatilho["open"], gatilho["close"])) / gatilho["open"] * 100
    if pavio_superior < 0.5: return None
    
    rsi = calcular_rsi(df["close"]).iloc[-1]
    atr = calcular_atr(df)
        
    return {
        "estrategia": "Laranja Mecânica",
        "timeframe": interval,
        "preco": gatilho["close"], 
        "range_cx": round(range_caixote, 2),
        "pavio_sup": round(pavio_superior, 2),
        "rsi": round(rsi, 1),
        "atr": atr,
        "score": 10 if rsi > 70 else 8
    }

def detectar_rsi_momentum(df: pd.DataFrame, interval: str) -> dict | None:
    """Estratégia RSI Momentum < 50: Recuperação de fundo."""
    if df is None or len(df) < 20: return None
    
    rsi_series = calcular_rsi(df["close"])
    rsi_atual = rsi_series.iloc[-1]
    rsi_anterior = rsi_series.iloc[-2]
    
    gatilho = df.iloc[-1]
    
    # Condições: RSI < 50 AND RSI subindo AND Vela Verde
    if rsi_atual < 50 and rsi_atual > rsi_anterior and gatilho["close"] > gatilho["open"]:
        return {
            "estrategia": "RSI Momentum",
            "timeframe": interval,
            "preco": gatilho["close"],
            "rsi": round(rsi_atual, 1),
            "rsi_anterior": round(rsi_anterior, 1),
            "atr": calcular_atr(df),
            "score": 10 if rsi_atual < 30 else 8
        }
    return None

def validar_altseason() -> bool:
    """Valida se o cenário macro é favorável para Altcoins."""
    try:
        # BTCDOM e BTC no timeframe de 1h para filtro macro
        df_btc = obter_klines("BTCUSDT", "1h", 50)
        df_dom = obter_klines("BTCDOMUSDT", "1h", 50) # Futuros na Binance
        
        if df_btc is None or df_dom is None: return True # Fallback seguro
        
        # Dominância caindo? (Preço abaixo da SMA 20)
        sma_dom = df_dom["close"].rolling(20).mean().iloc[-1]
        dom_atual = df_dom["close"].iloc[-1]
        
        # BTC estável ou subindo? (Acima da SMA 20 ou quase)
        sma_btc = df_btc["close"].rolling(20).mean().iloc[-1]
        btc_atual = df_btc["close"].iloc[-1]
        
        caindo_dom = dom_atual < sma_dom
        btc_ok = btc_atual > (sma_btc * 0.995)
        
        return caindo_dom and btc_ok
    except:
        return True

def calc_ichimoku(df):
    try:
        tenkan = (df['high'].rolling(9).max() + df['low'].rolling(9).min()) / 2
        kijun = (df['high'].rolling(26).max() + df['low'].rolling(26).min()) / 2
        senkou_a = ((tenkan + kijun) / 2).shift(26)
        senkou_b = ((df['high'].rolling(52).max() + df['low'].rolling(52).min()) / 2).shift(26)
        price = df['close'].iloc[-1]
        sa = senkou_a.iloc[-1]
        sb = senkou_b.iloc[-1]
        return price, max(sa, sb), min(sa, sb)
    except: return 0, 0, 0

def obter_analise_raiox(symbol):
    """Realiza análise técnica multitempo para o sistema de veto."""
    intervals = ['1m', '5m', '15m', '30m', '1h', '4h']
    analysis = {}
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        future_to_int = {executor.submit(obter_klines, symbol, i, 100): i for i in intervals}
        for future in concurrent.futures.as_completed(future_to_int):
            interval = future_to_int[future]
            try:
                df = future.result()
                if df is not None:
                    rsi = calcular_rsi(df['close']).iloc[-1]
                    price, sa, sb = calc_ichimoku(df)
                    above_cloud = df.iloc[-1]['close'] > sa
                    below_cloud = df.iloc[-1]['close'] < sb
                    trend = "ALTA" if above_cloud else ("BAIXA" if below_cloud else "NEUTRO")
                    analysis[interval] = {"rsi": rsi, "trend": trend}
            except: pass
    
    # Motor de Veredito (Simplificado para o Bot)
    weights = {'4h': 2.0, '1h': 1.8, '30m': 1.5, '15m': 1.5, '5m': 1.2, '1m': 0.8}
    total_weight = sum(weights.values())
    bull_score = 0
    for i, w in weights.items():
        if i in analysis:
            if analysis[i]['trend'] == "ALTA": bull_score += w
            elif analysis[i]['trend'] == "NEUTRO": bull_score += (w / 2)
            
    confidence = (bull_score / (total_weight or 1)) * 100
    return {"confidence": confidence, "verdict": "ALTA" if confidence > 60 else ("BAIXA" if confidence < 40 else "NEUTRO")}

# ─────────────────────────────────────────────────
# COLETA — COINGECKO
# ─────────────────────────────────────────────────
def obter_dados_coingecko(simbolos_base: list[str]) -> dict:
    ids_map = {
        "BTC": "bitcoin", "ETH": "ethereum", "BNB": "binancecoin",
        "SOL": "solana", "XRP": "ripple", "ADA": "cardano",
        "AVAX": "avalanche-2", "DOGE": "dogecoin", "DOT": "polkadot",
        "LINK": "chainlink", "NEAR": "near"
    }
    ids = ",".join([ids_map.get(s, s.lower()) for s in simbolos_base])
    url = "https://api.coingecko.com/api/v3/coins/markets"
    try:
        resp = requests.get(url, params={
            "vs_currency": "usd", "ids": ids,
            "order": "market_cap_desc", "per_page": 100, "page": 1
        }, timeout=15)
        resultado = {}
        if resp.status_code == 200:
            for coin in resp.json():
                sym = coin.get("symbol","").upper()
                resultado[sym] = {
                    "rank": coin.get("market_cap_rank", 9999),
                    "volume_24h": coin.get("total_volume", 0),
                    "price_change_24h": coin.get("price_change_percentage_24h", 0),
                }
        return resultado
    except Exception as e:
        print(f"  ⚠️ Erro no CoinGecko: {e}")
        return {}

# ─────────────────────────────────────────────────
# ENGINE PRINCIPAL
# ─────────────────────────────────────────────────
def scan_mercado():
    global _PROXIMO_INDICE_ROTATIVO
    hora = datetime.now().strftime('%H:%M:%S')
    
    slice_rotativo = SIMBOLOS_BASE[_PROXIMO_INDICE_ROTATIVO : _PROXIMO_INDICE_ROTATIVO + SIMBOLOS_POR_CICLO]
    _PROXIMO_INDICE_ROTATIVO = (_PROXIMO_INDICE_ROTATIVO + SIMBOLOS_POR_CICLO) % len(SIMBOLOS_BASE) if len(SIMBOLOS_BASE) > 0 else 0
    simbolos_ciclo = list(set(LISTA_PRIORIDADE + slice_rotativo))
    
    print(f"\n{'═' * 64}\n  🔄 Scan Laranja Mecânica: {hora} | Ativos: {len(simbolos_ciclo)}\n{'═' * 64}")

    bases = [s.replace("USDT","") for s in simbolos_ciclo]
    cg_dados = obter_dados_coingecko(bases)
    time.sleep(1.0)

    # Filtro Macro de Altseason
    altseason_ativa = validar_altseason()
    status_macro = "🌟 ALTSEASON ATIVA" if altseason_ativa else "⚠️ BTC DOMINANTE"
    print(f"  📢 Macro Status: {status_macro}")

    for symbol in simbolos_ciclo:
        # Raio-X Prévio para o Sistema de Veto
        raiox = obter_analise_raiox(symbol)
        conf = raiox['confidence']
        
        base = symbol.replace("USDT","")
        info_cg = cg_dados.get(base, {})
        rank = info_cg.get("rank", 9999)
        vol_24h = info_cg.get("volume_24h", 0)

        if symbol not in LISTA_PRIORIDADE:
            if rank > COINGECKO_RANK or vol_24h < VOLUME_MIN_24H: continue

        # --- 1. ESTRATÉGIA LARANJA MECÂNICA (SHORT) ---
        # VETO: Se IA detectou tendência de ALTA (> 65% confiança)
        if conf > 65:
            pass # Veto aplicado
        else:
            for tf, perfil in PERFIS_MECANICA.items():
                df = obter_klines(symbol, tf)
                time.sleep(0.05)
                s_mecanica = detectar_laranja_mecanica(df, tf) if df is not None else None
                
                if s_mecanica:
                    print(f"  🎯 {symbol:<10} [{tf}] → 🍊 LARANJA MECÂNICA!")
                    preco = s_mecanica['preco']
                    tp, sl = preco * perfil["tp"], preco * perfil["sl"]
                    estimativa = estimar_tempo_alvo(preco, tp, s_mecanica.get("atr", 0))
                    
                    msg = (
                        f"💎 *{tf.upper()} LARANJA MECÂNICA*\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"🔸 *Ativo:* `{symbol}`\n"
                        f"🕒 *Timeframe:* `{tf.upper()}`\n"
                        f"📉 *Entrada (Short):* `{preco:.4f}`\n"
                        f"🎯 *Alvo (TP):* `{tp:.4f}` ({round((perfil['tp']-1)*100, 1)}%)\n"
                        f"🛑 *Stop (SL):* `{sl:.4f}` (+{round((perfil['sl']-1)*100, 1)}%)\n"
                        f"⏱️ *Estimativa:* `{estimativa} velas`\n"
                        f"📊 *Score:* {s_mecanica['score']}/10\n"
                        f"📊 *IA Confiança:* {conf:.1f}%\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━"
                    )
                    enviar_telegram(msg)

        # --- 2. ESTRATÉGIA RSI MOMENTUM (LONG) ---
        # Apenas dispara se o cenário macro (Altseason) for favorável
        # VETO: Se IA detectou tendência de QUEDA (< 35% confiança)
        if altseason_ativa and conf >= 35:
            for tf, perfil in PERFIS_RSI_MOMENTUM.items():
                df = obter_klines(symbol, tf)
                time.sleep(0.05)
                s_rsi = detectar_rsi_momentum(df, tf) if df is not None else None
                
                if s_rsi:
                    print(f"  🚀 {symbol:<10} [{tf}] → RSI MOMENTUM!")
                    preco = s_rsi['preco']
                    tp, sl = preco * perfil["tp"], preco * perfil["sl"]
                    
                    msg = (
                        f"🚀 *{tf.upper()} RSI MOMENTUM*\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"🔹 *Ativo:* `{symbol}`\n"
                        f"🕒 *Timeframe:* `{tf.upper()}`\n"
                        f"📈 *Entrada (Long):* `{preco:.4f}`\n"
                        f"🎯 *Alvo (TP):* `{tp:.4f}` (+{round((perfil['tp']-1)*100, 1)}%)\n"
                        f"🛑 *Stop (SL):* `{sl:.4f}` ({round((perfil['sl']-1)*100, 1)}%)\n"
                        f"📊 *RSI:* {s_rsi['rsi']} (Anterior: {s_rsi['rsi_anterior']})\n"
                        f"📊 *Score:* {s_rsi['score']}/10\n"
                        f"📊 *IA Confiança:* {conf:.1f}%\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━"
                    )
                    enviar_telegram(msg)

def iniciar_loop():
    global SIMBOLOS_BASE
    print("\n╔════════════════════════════════════════════════════════════╗")
    print("║     GIDEON SENTINEL — LARANJA MECÂNICA                     ║")
    print(f"║     Monitorando 30m, 1h e 4h para {len(LISTA_PRIORIDADE)} ativos.           ║")
    
    todos = obter_todos_simbolos_binance()
    if todos:
        SIMBOLOS_BASE = [s for s in todos if s not in LISTA_PRIORIDADE]
        print(f"║     Outros {len(SIMBOLOS_BASE)} ativos em scan rotativo.                ║")
    print("╚════════════════════════════════════════════════════════════╝\n")

    while True:
        try:
            scan_mercado()
            agora = datetime.now().strftime('%H:%M:%S')
            print(f"\n  ⏳ [{agora}] Aguardando 5 minutos para o próximo ciclo...")
            time.sleep(300)
        except KeyboardInterrupt:
            print("\n  🛑 Monitoramento encerrado pelo usuário.")
            break
        except Exception as e:
            print(f"\n  ⚠️ Erro inesperado no loop: {e}")
            time.sleep(60)

if __name__ == "__main__":
    iniciar_loop()
