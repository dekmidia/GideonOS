"""
╔══════════════════════════════════════════════════════════════════╗
║           CRYPTO PUMP DETECTOR — Marcelo Vega                   ║
║     ESTRATÉGIA LARANJA SHORT (1H) — FOCO EXCLUSIVO              ║
║     Fontes: Binance (Klines 1h) + CoinGecko (rank/vol)          ║
╚══════════════════════════════════════════════════════════════════╝
"""

import requests
import pandas as pd
import numpy as np
from datetime import datetime
import time
import os
from dotenv import load_dotenv

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
# Suporta múltiplos IDs separados por vírgula
_raw_chat_ids = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_CHAT_IDS = [id.strip() for id in _raw_chat_ids.split(",") if id.strip()]

LIMITE_CANDLES  = 100   
COINGECKO_RANK  = 500   
VOLUME_MIN_24H  = 3_000_000 

_PROXIMO_INDICE_ROTATIVO = 0

# ─────────────────────────────────────────────────
# UTILITÁRIOS — NOTIFICAÇÕES
# ─────────────────────────────────────────────────
def enviar_telegram(mensagem: str):
    """Envia alerta para o bot do Telegram para todos os destinatários configurados."""
    print(f"\n📡 [SENTINELA] Gerando Alerta:\n{mensagem}\n")
    
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_IDS:
        return
        
    for chat_id in TELEGRAM_CHAT_IDS:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": chat_id, "text": mensagem, "parse_mode": "Markdown"}
        try:
            # Timeout de 20s para conexões lentas
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
    url = "https://api.binance.com/api/v3/klines"
    try:
        resp = requests.get(url, params={"symbol": symbol, "interval": interval, "limit": limit}, timeout=10)
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
    """Calcula o ATR médio dos últimos períodos."""
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    atr = true_range.rolling(period).mean().iloc[-1]
    return atr

def estimar_tempo_alvo(preco: float, alvo: float, atr: float) -> int:
    """Estima quantos candles faltam para atingir o alvo baseado no ATR."""
    distancia = abs(preco - alvo)
    # Usamos 70% do ATR como velocidade média direcional conservadora
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

def detectar_padrao_laranja(df: pd.DataFrame, interval: str) -> dict | None:
    """Estratégia Laranja Short (1H): Varredura e Exaustão."""
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
        "estrategia": "Laranja Short",
        "timeframe": interval,
        "preco": gatilho["close"], 
        "range_cx": round(range_caixote, 2),
        "pavio_sup": round(pavio_superior, 2),
        "rsi": round(rsi, 1),
        "atr": atr,
        "score": 10 if rsi > 70 else 8
    }

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
    
    print(f"\n{'═' * 64}\n  🔄 Scan Híbrido: {hora} | Ativos: {len(simbolos_ciclo)}\n{'═' * 64}")

    bases = [s.replace("USDT","") for s in simbolos_ciclo]
    cg_dados = obter_dados_coingecko(bases)
    time.sleep(1.0)

    sinais_encontrados = []

    for symbol in simbolos_ciclo:
        base = symbol.replace("USDT","")
        info_cg = cg_dados.get(base, {})
        rank = info_cg.get("rank", 9999)
        vol_24h = info_cg.get("volume_24h", 0)
        change_24h = info_cg.get("price_change_24h", 0)

        if symbol not in LISTA_PRIORIDADE:
            if rank > COINGECKO_RANK or vol_24h < VOLUME_MIN_24H: continue

        df_1h = obter_klines(symbol, "1h")
        time.sleep(0.2) # Delay para evitar Rate Limit na Binance

        s_laranja = detectar_padrao_laranja(df_1h, "1h") if df_1h is not None else None
        
        if s_laranja:
            print(f"  🎯 {symbol:<10} → 🍊 LARANJA SHORT!")
            sinais_encontrados.append({"symbol": symbol, "detalhes": s_laranja, "change": change_24h})

    if sinais_encontrados:
        print(f"\n{'═' * 64}\n  📋 SINAIS ENCONTRADOS\n{'═' * 64}")
        for s in sinais_encontrados:
            det = s["detalhes"]
            symbol = s["symbol"]
            preco = det['preco']
            tp = preco * 0.95 
            sl = preco * 1.10 
            estimativa_candles = estimar_tempo_alvo(preco, tp, det.get("atr", 0))
            
            msg = (
                f"🍊 *SINAL DETECTADO: LARANJA SHORT*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💎 *Ativo:* `{symbol}`\n"
                f"⌛ *Timeframe:* `1 Hora (1H)`\n"
                f"📈 *Preço de Entrada:* `{preco:.4f}`\n"
                f"🎯 *Alvo (Take Profit):* `{tp:.4f}` (-5%)\n"
                f"🛑 *Stop (Stop Loss):* `{sl:.4f}` (+10%)\n"
                f"⏱️ *Estimativa p/ Alvo:* `{estimativa_candles} candles` (~{estimativa_candles}h)\n"
                f"⚖️ *Alavancagem Sugerida:* 5x\n"
                f"📊 *Score:* {det['score']}/10\n"
                f"━━━━━━━━━━━━━━━━━━━━━━"
            )
            enviar_telegram(msg)
            print(f"  {symbol:<12} 🍊 SHORT {preco:>10.4f} Score: {det['score']}")
    else:
        print("\n  ❌ Nenhuma oportunidade Laranja Short neste ciclo.")

def iniciar_loop():
    global SIMBOLOS_BASE
    print("\n╔════════════════════════════════════════════════════════════╗")
    print("║     GIDEON SENTINEL — FOCO LARANJA SHORT (1H)              ║")
    print(f"║     Monitorando {len(LISTA_PRIORIDADE)} ativos prioritários.               ║")
    
    todos = obter_todos_simbolos_binance()
    if todos:
        SIMBOLOS_BASE = [s for s in todos if s not in LISTA_PRIORIDADE]
        print(f"║     Scan Rotativo de {len(SIMBOLOS_BASE)} outros ativos ativos.           ║")
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
            print("  Retentando em 60 segundos...")
            time.sleep(60)

if __name__ == "__main__":
    iniciar_loop()
