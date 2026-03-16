import os
import requests
import pandas as pd
import numpy as np
import hmac
import hashlib
import time
import re
import concurrent.futures
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__)
CORS(app)

BINGX_URL = "https://open-api.bingx.com"
LEDGER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'ledger_trades.md')

# SESSÃO GLOBAL PARA REUSO DE CONEXÕES (SPEED UP)
http_session = requests.Session()

# CACHE PARA STATUS MACRO (ALTSEASON / BTC)
macro_cache = {
    "data": None,
    "last_update": 0
}

def get_bingx_signature(params_str, secret):
    return hmac.new(secret.encode('utf-8'), params_str.encode('utf-8'), hashlib.sha256).hexdigest()

# Reutilizando a lógica do Sentinela V3
FILTRO_RSI_4H = 70
LIMITE_VOLUME_24H = 5000000

# PERFIS LARANJA MECÂNICA (SHORT) - Sincronizado com pump_detector.py
PERFIS_MECANICA = {
    "30m": {"tp": 0.975, "sl": 1.050, "emoji": "🕒"}, # -2.5% / +5%
    "1h":  {"tp": 0.950, "sl": 1.100, "emoji": "🕐"}, # -5% / +10%
    "4h":  {"tp": 0.950, "sl": 1.100, "emoji": "🕓"}  # -5% / +10%
}

# PERFIS RSI MOMENTUM (LONG)
PERFIS_RSI_MOMENTUM = {
    "1m":  {"tp": 1.015, "sl": 0.990, "emoji": "🚀"},
    "5m":  {"tp": 1.030, "sl": 0.980, "emoji": "⚡"},
    "15m": {"tp": 1.050, "sl": 0.970, "emoji": "💎"}
}

def calcular_atr(df, period=14):
    try:
        high_low = df['h'] - df['l']
        high_close = np.abs(df['h'] - df['c'].shift())
        low_close = np.abs(df['l'] - df['c'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        atr = true_range.rolling(period).mean().iloc[-1]
        return atr
    except: return 0

def estimar_tempo_alvo(preco, alvo, atr):
    try:
        distancia = abs(preco - alvo)
        if atr == 0 or np.isnan(atr): return 0
        candles = distancia / (atr * 0.7)
        return int(round(max(1, candles)))
    except: return 0

def get_data(symbol, interval, limit=100):
    try:
        # BTCDOMUSDT só existe nos Futuros
        url = f'https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}' if "DOM" in symbol else f'https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}'
        r = http_session.get(url, timeout=5).json()
        if not isinstance(r, list): return None
        df = pd.DataFrame(r, columns=['t','o','h','l','c','v','ct','q','tr','tb','tg','i'])
        df['c'] = df['c'].astype(float)
        df['h'] = df['h'].astype(float)
        df['l'] = df['l'].astype(float)
        df['o'] = df['o'].astype(float)
        return df
    except:
        return None

def get_ticker_price(symbol):
    """Busca o preço instantâneo (ticker) na Binance."""
    try:
        url = f'https://api.binance.com/api/v3/ticker/price?symbol={symbol}'
        r = http_session.get(url, timeout=2).json()
        return float(r['price'])
    except:
        return None

def get_bingx_price(symbol):
    """Busca o preço instantâneo na BingX para PnL preciso."""
    try:
        # BingX usa o par com hifen (ex: ACE-USDT)
        bx_symbol = symbol.replace('USDT', '-USDT')
        url = f'https://open-api.bingx.com/openApi/swap/v2/quote/ticker?symbol={bx_symbol}'
        r = requests.get(url, timeout=2).json()
        if r.get('code') == 0:
            return float(r['data']['lastPrice'])
        return None
    except:
        return None

def calc_rsi(df, period=14):
    try:
        delta = df['c'].diff()
        gain = (delta.where(delta > 0, 0))
        loss = (-delta.where(delta < 0, 0))
        avg_gain = gain.ewm(com=period-1, adjust=False).mean()
        avg_loss = loss.ewm(com=period-1, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, 1e-10)
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1]
    except: return 50

def calc_ichimoku(df):
    try:
        tenkan = (df['h'].rolling(9).max() + df['l'].rolling(9).min()) / 2
        kijun = (df['h'].rolling(26).max() + df['l'].rolling(26).min()) / 2
        senkou_a = ((tenkan + kijun) / 2).shift(26)
        senkou_b = ((df['h'].rolling(52).max() + df['l'].rolling(52).min()) / 2).shift(26)
        price = df['c'].iloc[-1]
        sa = senkou_a.iloc[-1]
        sb = senkou_b.iloc[-1]
        return price, max(sa, sb), min(sa, sb)
    except:
        return 0, 0, 0

def validar_altseason():
    """Valida cenário macro com cache de 60s para performance extrema."""
    global macro_cache
    agora = time.time()
    
    if macro_cache["data"] and (agora - macro_cache["last_update"] < 60):
        return macro_cache["data"]

    try:
        # Chamadas paralelas para BTC e Dominância (Speed Boost)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            f_btc = executor.submit(get_data, 'BTCUSDT', '1h', 50)
            f_dom = executor.submit(get_data, 'BTCDOMUSDT', '1h', 50)
            df_btc = f_btc.result()
            df_dom = f_dom.result()

        if df_btc is None or df_dom is None: 
            return False, "NEUTRO"
        
        sma_dom = df_dom['c'].rolling(20).mean().iloc[-1]
        dom_atual = df_dom['c'].iloc[-1]
        sma_btc = df_btc['c'].rolling(20).mean().iloc[-1]
        btc_atual = df_btc['c'].iloc[-1]
        
        altseason = dom_atual < sma_dom and btc_atual > (sma_btc * 0.995)
        status = "🌟 ALTSEASON ATIVA" if altseason else "⚠️ BTC DOMINANTE"
        
        # Atualiza Cache
        macro_cache["data"] = (altseason, status)
        macro_cache["last_update"] = agora
        
        return altseason, status
    except:
        return False, "NEUTRO"

def get_btc_status():
    """Versão simplificada para a barra de performance do dashboard."""
    _, status = validar_altseason()
    return status

def get_multi_timeframe_analysis(symbol):
    """Realiza análise técnica em 6 tempos gráficos."""
    intervals = ['1m', '5m', '15m', '30m', '1h', '4h']
    analysis = {}
    
    # Busca BTC Status ANTES ou durante para aproveitar cache/paralelismo
    btc_status = get_btc_status() if symbol != 'BTCUSDT' else "N/A"
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_int = {executor.submit(get_data, symbol, i, 100): i for i in intervals}
        for future in concurrent.futures.as_completed(future_to_int):
            interval = future_to_int[future]
            try:
                df = future.result()
                if df is not None:
                    rsi = calc_rsi(df)
                    price, sa, sb = calc_ichimoku(df)
                    # Direção da vela atual
                    candle_color = "ALTA" if df.iloc[-1]['c'] > df.iloc[-1]['o'] else "BAIXA"
                    # Relação com a Nuvem
                    above_cloud = df.iloc[-1]['c'] > sa
                    below_cloud = df.iloc[-1]['c'] < sb
                    trend = "ALTA" if above_cloud else ("BAIXA" if below_cloud else "NEUTRO")
                    
                    # Análise de Volume (Divergência)
                    avg_vol = df['v'].astype(float).tail(20).mean()
                    curr_vol = float(df['v'].iloc[-1])
                    vol_status = "NORMAL"
                    if curr_vol < avg_vol * 0.7: vol_status = "EXAUSTÃO"
                    elif curr_vol > avg_vol * 1.5: vol_status = "FORTE"
                    
                    analysis[interval] = {
                        "rsi": round(rsi, 2),
                        "trend": trend,
                        "candle": candle_color,
                        "price": df.iloc[-1]['c'],
                        "volume": vol_status
                    }
                else:
                    analysis[interval] = {"error": "Sem dados"}
            except Exception as e:
                analysis[interval] = {"error": str(e)}
    
    # Motor de Veredito Reequilibrado
    verdict = "INDETERMINADO"
    weights = {'4h': 2.0, '1h': 1.8, '30m': 1.5, '15m': 1.5, '5m': 1.2, '1m': 0.8}
    
    total_weight = 0
    bull_score = 0
    
    for i, w in weights.items():
        if i in analysis and "trend" in analysis[i]:
            total_weight += w
            if analysis[i]['trend'] == "ALTA": bull_score += w
            elif analysis[i]['trend'] == "NEUTRO": bull_score += (w / 2)
            
    confidence = (bull_score / (total_weight or 1)) * 100
    
    if confidence > 75: verdict = "🚀 ALTA FORTE"
    elif confidence > 60: verdict = "📈 ALTA PROVÁVEL"
    elif confidence < 25: verdict = "📉 QUEDA FORTE"
    elif confidence < 40: verdict = "📉 QUEDA PROVÁVEL"
    else: verdict = "⚖️ LATERAL / INDECISO"
    
    macro_trend = analysis.get('4h', {}).get('trend', 'NEUTRO')
    micro_rsi = analysis.get('5m', {}).get('rsi', 50)
    
    reason = f"Macrotendência (4h): {macro_trend}. BTC: {btc_status}. "
    if micro_rsi > 70: reason += "Sobrecomprado (RSI > 70)."
    elif micro_rsi < 30: reason += "Sobrevendido (RSI < 30)."
    
    return {
        "symbol": symbol,
        "timeframes": analysis,
        "verdict": verdict,
        "confidence": round(confidence, 1),
        "reason": reason,
        "btc_status": btc_status
    }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/manual')
def manual():
    return render_template('manual.html')

@app.route('/plano')
def plano():
    return render_template('plano.html')

import json

# Carrega moedas comuns do arquivo gerado pelo mapeador
moedas_json = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'moedas_comuns.json')
try:
    with open(moedas_json, 'r') as f:
        LISTA_PRIORIDADE = json.load(f)
except:
    LISTA_PRIORIDADE = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT']

# MODO SNOWBALL: Sincronizado com pump_detector.py
SNOWBALL_MODE = True
CONFIDENCA_MINIMA = 75 if SNOWBALL_MODE else 60

def detectar_laranja_mecanica(df, interval):
    if df is None or len(df) < 30: return None
    gatilho = df.iloc[-1]
    df_caixote = df.iloc[-7:-1] 
    
    max_recent = df_caixote["h"].max()
    min_recent = df_caixote["l"].min()
    range_caixote = (max_recent / min_recent - 1) * 100
    if range_caixote > 8.0: return None
    
    corpo_gatilho = abs(gatilho["c"] - gatilho["o"]) / gatilho["o"] * 100
    if corpo_gatilho > 3.0: return None
    
    pavio_superior = (gatilho["h"] - max(gatilho["o"], gatilho["c"])) / gatilho["o"] * 100
    if pavio_superior < 0.5: return None
    
    return {
        "estrategia": "🍊 LARANJA",
        "pavio": round(pavio_superior, 2),
        "range": round(range_caixote, 2),
        "atr": calcular_atr(df)
    }

def detectar_rsi_momentum(df, interval):
    if df is None or len(df) < 20: return None
    
    # Manual RSI para evitar dependências extras
    delta = df['c'].diff()
    gain = (delta.where(delta > 0, 0)).ewm(com=13, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(com=13, adjust=False).mean()
    rs = gain / loss.replace(0, 1e-10)
    rsi_series = 100 - (100 / (1 + rs))
    
    rsi_atual = rsi_series.iloc[-1]
    rsi_anterior = rsi_series.iloc[-2]
    gatilho = df.iloc[-1]
    
    if rsi_atual < 50 and rsi_atual > rsi_anterior and gatilho['c'] > gatilho['o']:
        return {
            "estrategia": "🚀 RSI MOMENTUM",
            "rsi": round(rsi_atual, 1),
            "rsi_anterior": round(rsi_anterior, 1),
            "atr": calcular_atr(df)
        }
    return None

def salvar_sinal_ativo(sinal):
    """Salva sinal em tempo real para o dashboard."""
    try:
        if os.path.exists('sinais_ativos.json'):
            with open('sinais_ativos.json', 'r') as f:
                sinais = json.load(f)
        else:
            sinais = []
        
        # Evitar duplicatas (mesmo símbolo e status)
        if not any(s['symbol'] == sinal['symbol'] and s['status'] == sinal['status'] for s in sinais):
            sinais.append(sinal)
            # Ordenar por score
            sinais = sorted(sinais, key=lambda x: x['score'], reverse=True)
            with open('sinais_ativos.json', 'w') as f:
                json.dump(sinais, f)
    except: pass

@app.route('/api/latest_signals')
def api_latest_signals():
    if not os.path.exists('sinais_ativos.json'):
        return jsonify([])
    try:
        with open('sinais_ativos.json', 'r') as f:
            return jsonify(json.load(f))
    except:
        return jsonify([])

@app.route('/api/scanner')
def api_scanner():
    results = []
    processed_count = 0
    total_to_process = len(LISTA_PRIORIDADE)
    
    # Limpar sinais antigos no início de uma nova varredura manual
    with open('sinais_ativos.json', 'w') as f:
        json.dump([], f)

    def check_symbol(symbol):
        local_results = []
        altseason_ativa, _ = validar_altseason()
        
        # 2. Análise de Raio-X IA para Veto
        analysis = get_multi_timeframe_analysis(symbol)
        confidence = analysis.get('confidence', 0)
        
        # 3. Tentar Laranja Mecânica (Short)
        for tf in ['30m', '1h', '4h']:
            df = get_data(symbol, tf)
            if df is None: continue
            laranja = detectar_laranja_mecanica(df, tf)
            if laranja:
                # VETO DE SHORT: IA detectou tendência de ALTA
                if confidence > (100 - CONFIDENCA_MINIMA/1.5):
                    return []

                rsi = calc_rsi(df)
                price = df['c'].iloc[-1]
                perfil = PERFIS_MECANICA.get(tf, PERFIS_MECANICA["1h"])
                tp, sl = price * perfil["tp"], price * perfil["sl"]
                estimativa = estimar_tempo_alvo(price, tp, laranja["atr"])
                signal = {
                    'symbol': symbol, 'price': price, 'rsi4h': round(rsi, 2),
                    'bb_upper': tf.upper(), 'status': f"🍊 {laranja['estrategia']} ({tf})",
                    'side': 'Short', 'tp': round(tp, 6), 'sl': round(sl, 6),
                    'estimativa': f"{estimativa} velas", 'score': 10 if (rsi > 70 and confidence < 40) else 8,
                    'ai_conf': confidence
                }
                salvar_sinal_ativo(signal)
                local_results.append(signal)
                return local_results 
        
        # 4. Tentar RSI Momentum (Long) se Altseason Ativa
        if altseason_ativa:
            for tf in ['1m', '5m', '15m']:
                df = get_data(symbol, tf)
                if df is None: continue
                rsi_m = detectar_rsi_momentum(df, tf)
                if rsi_m:
                    status_long = f"🚀 {rsi_m['estrategia']} ({tf})"
                    score_long = 10 if rsi_m['rsi'] < 30 else 8
                    
                    if confidence < CONFIDENCA_MINIMA:
                        status_long = f"🚫 VETO IA ({confidence}%)"
                        score_long = 1
                    
                    price = df['c'].iloc[-1]
                    perfil = PERFIS_RSI_MOMENTUM.get(tf, PERFIS_RSI_MOMENTUM["1m"])
                    tp, sl = price * perfil["tp"], price * perfil["sl"]
                    signal = {
                        'symbol': symbol, 'price': price, 'rsi4h': rsi_m['rsi'],
                        'bb_upper': tf.upper(), 'status': status_long,
                        'side': 'Long', 'tp': round(tp, 6), 'sl': round(sl, 6),
                        'estimativa': "Rápida", 'score': score_long,
                        'ai_conf': confidence
                    }
                    salvar_sinal_ativo(signal)
                    local_results.append(signal)
                    return local_results
        return local_results

    print(f"\n🚀 [SCANNER] Iniciando varredura manual: {total_to_process} moedas...")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
        future_to_symbol = {executor.submit(check_symbol, s): s for s in LISTA_PRIORIDADE}
        for future in concurrent.futures.as_completed(future_to_symbol):
            processed_count += 1
            if processed_count % 20 == 0:
                print(f"  ⏳ Progresso: {processed_count}/{total_to_process} moedas analisadas...")
            
            try:
                res = future.result()
                if res:
                    results.extend(res)
                    print(f"  🎯 ALERTA: {res[0]['symbol']} em {res[0]['bb_upper']}")
            except: pass

    print(f"🏁 [SCANNER] Fim da varredura. {len(results)} sinais encontrados.\n")
    return jsonify(results)

@app.route('/api/monitor')
def api_monitor():
    try:
        ledger_path = LEDGER_PATH
        if not os.path.exists(ledger_path):
            return jsonify({'error': 'Ledger não encontrado'})

        with open(ledger_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        header = '## 🟢 Posições Abertas'
        if header not in content:
            return jsonify([])
            
        after_header = content.split(header)[1]
        section = re.split(r'\n---|\n#', after_header)[0]
        
        positions = []
        for line in section.splitlines():
            if '|' in line and '**' in line:
                try:
                    parts = [p.strip() for p in line.split('|')]
                    # Nova estrutura: | Abertura | Par | TF | TTT | Tipo | Alavancagem | Entrada | Alvo | Stop |
                    if len(parts) < 10: continue
                    symbol = parts[2].replace('*', '').strip()
                    side = parts[5].strip()
                    price_str = parts[7].replace('*', '').strip()
                    entry_price = float(price_str)
                    
                    # PREÇO BINGX (Primário) -> BINANCE (Fallback)
                    curr_price = get_bingx_price(symbol)
                    if curr_price is None:
                        curr_price = get_ticker_price(symbol)
                    
                    df_4h = get_data(symbol, '4h')
                    if df_4h is None: 
                        if curr_price is None: continue
                        rsi_4h = 50
                        kumo_top_4h, kumo_bottom_4h = 0, 0
                    else:
                        rsi_4h = calc_rsi(df_4h)
                        k_price, kumo_top_4h, kumo_bottom_4h = calc_ichimoku(df_4h)
                        if curr_price is None: curr_price = k_price
                    
                    is_short = side.lower() == 'short'
                    # FÓRMULA CORRETA (Linear Futures)
                    if is_short:
                        pnl = (entry_price - curr_price) / entry_price * 100 * 8
                    else:
                        pnl = (curr_price - entry_price) / entry_price * 100 * 8
                    
                    status = 'TUDO CERTO: SEGURAR'
                    if is_short and curr_price > kumo_top_4h:
                        status = 'PERIGOSO: SAIR AGORA'
                    elif not is_short and curr_price < kumo_bottom_4h:
                        status = 'PERIGOSO: SAIR AGORA'
                    elif is_short and rsi_4h < 45:
                        status = 'LUCRO NO BOLSO?'
                    elif not is_short and rsi_4h > 65:
                        status = 'LUCRO NO BOLSO?'
                    
                    if is_short and curr_price <= entry_price:
                        status = 'PROTEÇÃO: NO ZERO'
                    elif not is_short and curr_price >= entry_price:
                        status = 'PROTEÇÃO: NO ZERO'

                    positions.append({
                        'symbol': symbol,
                        'side': side,
                        'entry': entry_price,
                        'current': curr_price,
                        'pnl': round(pnl, 2),
                        'rsi4h': round(rsi_4h, 2),
                        'kumo_4h': round(kumo_top_4h, 4),
                        'status': status,
                        'opened_at': parts[1],
                        'tf': parts[3],
                        'ttt': parts[4]
                    })
                except: continue
        # Status Macro para o Dashboard
        _, macro_status = validar_altseason()
        return jsonify({
            'positions': positions,
            'macro': macro_status
        })
    except Exception as e:
        print(f"❌ [MONITOR] Erro crítico: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/entry', methods=['POST'])
def api_entry():
    try:
        data = request.json
        symbol = data.get('symbol')
        side = data.get('side', 'Short')
        price = data.get('price')
        tf = data.get('tf', '1h')
        ttt = data.get('ttt', 'N/A')
        # Data e Hora de Abertura completa
        date = datetime.now().strftime('%d/%m/%y %H:%M:%S')
        
        # Nova Linha com 6 casas de precisão no preço de entrada
        line = f"| {date} | **{symbol}** | {tf} | {ttt} | {side} | 8x | {round(float(price), 6)} | {round(float(price), 6)}* | {round(float(price)*1.1, 6)} |\n"
        
        ledger_path = LEDGER_PATH
        with open(ledger_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Proteção contra duplicatas
        if f"**{symbol}**" in content and "## 🟢 Posições Abertas" in content:
            active_section = content.split("## 🟢 Posições Abertas")[1].split("---")[0]
            if f"**{symbol}**" in active_section:
                return jsonify({'status': 'warning', 'message': f'{symbol} já está na Carteira Ativa!'})

        header = '## 🟢 Posições Abertas'
        table_header = '|:---:|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|'
        
        if header in content and table_header in content:
            parts = content.split(table_header)
            new_content = parts[0] + table_header + "\n" + line + parts[1]
            with open(ledger_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            return jsonify({'status': 'success', 'message': f'Entrada em {symbol} registrada!'})
        return jsonify({'status': 'error', 'message': 'Seção ativa não encontrada'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/exit', methods=['POST'])
def api_exit():
    try:
        data = request.json
        symbol = data.get('symbol')
        ledger_path = LEDGER_PATH
        
        with open(ledger_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        new_lines = []
        removed_line = None
        for line in lines:
            if f"**{symbol}**" in line and '|' in line and any(s.lower() in line.lower() for s in ['Short', 'Long']):
                if not removed_line:
                    removed_line = line
                    continue
            new_lines.append(line)
        
        if removed_line:
            parts = [p.strip() for p in removed_line.split('|')]
            # parts do removed_line: 0:'', 1:Abertura, 2:Par, 3:TF, 4:TTT, 5:Tipo, 6:Alav, 7:Entrada...
            date_exit = datetime.now().strftime('%d/%m/%y %H:%M:%S')
            
            # Cabeçalho Histórico: | Abertura | Saída | Par | TF | TTT | Tipo | Resultado | PnL | Notas |
            # Metadados preservados: E=Entrada, T=Alvo, S=Stop
            metadata = f"[E:{parts[7]}, T:{parts[10]}, S:{parts[11]}]" if len(parts) > 11 else f"[E:{parts[7]}, T:{parts[8]}, S:{parts[9]}]"
            hist_line = f"| {parts[1]} | {date_exit} | **{symbol}** | {parts[3]} | {parts[4]} | {parts[5]} | ✅ WIN | +1.0% | {metadata} Fechado via Dashboard. |\n"
            
            final_lines = []
            hist_header = '## 🔴 Histórico de Operações (Encerradas)'
            for line in new_lines:
                final_lines.append(line)
                if hist_header in line:
                    final_lines.append("|:---:|:---:|---|:---:|:---:|:---:|:---:|:---:|---|\n")
                    final_lines.append(hist_line)
            
            content = "".join(final_lines).replace("|:---:|:---:|---|:---:|:---:|:---:|:---:|:---:|---\n|:---:|:---:|---|:---:|:---:|:---:|:---:|:---:|---|", "|:---:|:---:|---|:---:|:---:|:---:|:---:|:---:|---|")
            with open(ledger_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return jsonify({'status': 'success', 'message': f'Saída de {symbol} registrada!'})
        return jsonify({'status': 'error', 'message': 'Posição não encontrada'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/history')
def api_history():
    try:
        ledger_path = LEDGER_PATH
        if not os.path.exists(ledger_path): return jsonify([])

        with open(ledger_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        header = '## 🔴 Histórico de Operações (Encerradas)'
        if header not in content: return jsonify([])
            
        after_header = content.split(header)[1]
        section = re.split(r'\n#', after_header)[0]
        
        history = []
        for line in section.splitlines():
            if '|' in line and '**' in line and ('WIN' in line or 'LOSS' in line):
                try:
                    parts = [p.strip() for p in line.split('|')]
                    # Estrutura: | Abertura | Saída | Par | TF | TTT | Tipo | Resultado | PnL | Notas |
                    if len(parts) < 10: continue
                    history.append({
                        'opened_at': parts[1],
                        'closed_at': parts[2],
                        'symbol': parts[3].replace('*', '').strip(),
                        'tf': parts[4],
                        'ttt': parts[5],
                        'side': parts[6],
                        'result': parts[7],
                        'pnl': parts[8],
                        'notes': parts[9] if len(parts) > 9 else ''
                    })
                except: continue
        return jsonify(history)
    except: return jsonify([])

@app.route('/api/analyze/<symbol>')
def api_analyze(symbol):
    try:
        data = get_multi_timeframe_analysis(symbol)
        return jsonify(data)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/history/restore', methods=['POST'])
def api_history_restore():
    try:
        data = request.json
        symbol = data.get('symbol')
        opened_at = data.get('opened_at')
        
        ledger_path = LEDGER_PATH
        with open(ledger_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        new_lines = []
        restored_data = None
        
        for line in lines:
            if f"**{symbol}**" in line and opened_at in line and ('WIN' in line or 'LOSS' in line):
                parts = [p.strip() for p in line.split('|')]
                # Historico: | 1:Abertura | 2:Saída | 3:Par | 4:TF | 5:TTT | 6:Tipo | 7:Res | 8:PnL | 9:Notas |
                notes = parts[9]
                
                # Tentar extrair metadados [E:..., T:..., S:...]
                import re
                entry, target, stop = "0.0", "0.0", "0.0"
                match = re.search(r'\[E:(.*?), T:(.*?), S:(.*?)\]', notes)
                if match:
                    entry, target, stop = match.groups()
                else:
                    # Fallback: se não tiver metadados, usa o ticker atual
                    curr = get_bingx_price(symbol) or get_ticker_price(symbol) or 0.0
                    entry, target, stop = curr, curr, curr
                
                # Novo formato para Posições Abertas: | Abertura | Par | TF | TTT | Tipo | Alavancagem | Entrada | Entrada* | Alvo | Stop |
                # Nota: Na versão atual do ledger temos 9 colunas originais mas o parser atual usa mais?
                # Vamos seguir o padrão do api_entry: | date | symbol | tf | ttt | side | 8x | price | price* | tp | sl |
                restored_data = f"| {parts[1]} | **{symbol}** | {parts[4]} | {parts[5]} | {parts[6]} | 8x | {entry} | {entry}* | {target} | {stop} |\n"
                continue
            new_lines.append(line)
            
        if restored_data:
            final_lines = []
            active_header = '## 🟢 Posições Abertas'
            for line in new_lines:
                final_lines.append(line)
                if active_header in line:
                    final_lines.append("|:---:|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|\n")
                    final_lines.append(restored_data)
            
            content = "".join(final_lines).replace("|:---:|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:\n|:---:|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|", "|:---:|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|")
            with open(ledger_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return jsonify({'status': 'success', 'message': f'{symbol} restaurado!'})
            
        return jsonify({'status': 'error', 'message': 'Registro não encontrado no histórico'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/bingx/order', methods=['POST'])
def api_bingx_order():
    from dotenv import load_dotenv
    load_dotenv()
    
    api_key = os.getenv("BINGX_API_KEY")
    secret_key = os.getenv("BINGX_SECRET")
    
    if not api_key or not secret_key:
        return jsonify({'status': 'error', 'message': 'Chaves não configuradas no .env'}), 400

    try:
        data = request.json
        symbol = data.get('symbol').replace('USDT', '-USDT')
        original_side = data.get('side', 'SHORT').upper()
        margin = data.get('margin', 10)
        tp = data.get('tp')
        sl = data.get('sl')
        
        side = "SELL" if original_side == "SHORT" else "BUY"
        pos_side = "SHORT" if original_side == "SHORT" else "LONG"
        close_side = "BUY" if original_side == "SHORT" else "SELL"
        
        # 1. Alavancagem
        lev_path = "/openApi/swap/v2/trade/leverage"
        lev_params = f"leverage=8&symbol={symbol}&timestamp={int(time.time() * 1000)}&recvWindow=20000"
        lev_sig = get_bingx_signature(lev_params, secret_key)
        requests.post(f"{BINGX_URL}{lev_path}?{lev_params}&signature={lev_sig}", headers={"X-BX-APIKEY": api_key})

        # 2. Ordem Principal
        entry_price = float(data.get('price'))
        
        # Lógica de Quantidade Refinada: Evitar Qty com muitas casas decimais que a exchange rejeita
        if entry_price < 0.01:
            qty = round((float(margin) * 8.0) / entry_price, 0)
        elif entry_price < 0.1:
            qty = round((float(margin) * 8.0) / entry_price, 1)
        elif entry_price < 1.0:
            qty = round((float(margin) * 8.0) / entry_price, 2)
        else:
            qty = round((float(margin) * 8.0) / entry_price, 3)
        
        print(f"🚀 [BINGX] Ordem Principal: {symbol} | Qty: {qty} | Price: {entry_price}")

        order_path = "/openApi/swap/v2/trade/order"
        params = {
            "symbol": symbol,
            "side": side,
            "positionSide": pos_side,
            "type": "MARKET",
            "quantity": qty,
            "timestamp": int(time.time() * 1000),
            "recvWindow": 20000
        }
        query = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
        sig = get_bingx_signature(query, secret_key)
        r = http_session.post(f"{BINGX_URL}{order_path}?{query}&signature={sig}", headers={"X-BX-APIKEY": api_key})
        res = r.json()
        
        if res.get('code') == 0:
            print(f"✅ [BINGX] Sucesso na Ordem Principal")
            # 3. TP/SL - Formatação de precisão dinâmica
            def format_price(p):
                # Para moedas muito baratas, precisamos de mais precisão. Para caras, menos.
                val = float(p)
                if val < 0.001: return round(val, 6)
                if val < 0.1: return round(val, 5)
                if val < 1: return round(val, 4)
                return round(val, 3)

            tp_price = format_price(tp)
            sl_price = format_price(sl)
            
            print(f"🎯 [BINGX] Configurando Proteção: TP={tp_price} | SL={sl_price}")

            # TP
            tp_params = {
                "symbol": symbol, "side": close_side, "positionSide": pos_side,
                "type": "TAKE_PROFIT_MARKET", "stopPrice": tp_price, "quantity": qty,
                "reduceOnly": "true", "workingType": "MARK_PRICE", "timestamp": int(time.time() * 1000),
                "recvWindow": 20000
            }
            tp_query = "&".join([f"{k}={v}" for k, v in sorted(tp_params.items())])
            tp_res = http_session.post(f"{BINGX_URL}{order_path}?{tp_query}&signature={get_bingx_signature(tp_query, secret_key)}", headers={"X-BX-APIKEY": api_key}).json()
            if tp_res.get('code') != 0:
                print(f"❌ [BINGX] Falha no TP: {tp_res}") # Log completo para diagnostico
            else:
                print(f"✅ [BINGX] TP Configurado")

            # SL
            sl_params = {
                "symbol": symbol, "side": close_side, "positionSide": pos_side,
                "type": "STOP_MARKET", "stopPrice": sl_price, "quantity": qty,
                "reduceOnly": "true", "workingType": "MARK_PRICE", "timestamp": int(time.time() * 1000),
                "recvWindow": 20000
            }
            sl_query = "&".join([f"{k}={v}" for k, v in sorted(sl_params.items())])
            sl_res = http_session.post(f"{BINGX_URL}{order_path}?{sl_query}&signature={get_bingx_signature(sl_query, secret_key)}", headers={"X-BX-APIKEY": api_key}).json()
            if sl_res.get('code') != 0:
                print(f"❌ [BINGX] Falha no SL: {sl_res}") # Log completo para diagnostico
            else:
                print(f"✅ [BINGX] SL Configurado")

            return jsonify({'status': 'success', 'message': f'Operação em {symbol} executada!'})
        else:
            print(f"❌ [BINGX] Erro Crítico Ordem: {res}")
            return jsonify({'status': 'error', 'message': f"BingX: ({res.get('code')}) {res.get('msg')}"})
    except Exception as e:
        print(f"❌ [BINGX] Exceção: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(port=5000, debug=True)
