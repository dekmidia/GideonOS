from flask import Flask, jsonify, render_template
from flask_cors import CORS
import requests
import pandas as pd
import os
import re
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Reutilizando a lógica do Sentinela V3
FILTRO_RSI_4H = 70
LIMITE_VOLUME_24H = 50000000

def get_data(symbol, interval, limit=100):
    try:
        url = f'https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}'
        r = requests.get(url, timeout=10).json()
        df = pd.DataFrame(r, columns=['t','o','h','l','c','v','ct','q','tr','tb','tg','i'])
        df['c'] = df['c'].astype(float)
        df['h'] = df['h'].astype(float)
        df['l'] = df['l'].astype(float)
        return df
    except:
        return None

def calc_rsi(df, period=14):
    delta = df['c'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1]

def calc_ichimoku(df):
    tenkan = (df['h'].rolling(9).max() + df['l'].rolling(9).min()) / 2
    kijun = (df['h'].rolling(26).max() + df['l'].rolling(26).min()) / 2
    senkou_a = ((tenkan + kijun) / 2).shift(26)
    senkou_b = ((df['h'].rolling(52).max() + df['l'].rolling(52).min()) / 2).shift(26)
    price = df['c'].iloc[-1]
    sa = senkou_a.iloc[-1]
    sb = senkou_b.iloc[-1]
    return price, max(sa, sb), min(sa, sb)

def calc_bollinger(df):
    sma = df['c'].rolling(20).mean()
    std_dev = df['c'].rolling(20).std()
    upper = sma + (std_dev * 2)
    return upper.iloc[-1]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/scanner')
def api_scanner():
    ticker_url = 'https://api.binance.com/api/v3/ticker/24hr'
    tickers = requests.get(ticker_url).json()
    pairs = [t['symbol'] for t in tickers if t['symbol'].endswith('USDT') and float(t['quoteVolume']) > LIMITE_VOLUME_24H]
    
    results = []
    for symbol in pairs[:40]: # Top 40 para velocidade
        df_1d = get_data(symbol, '1d')
        if df_1d is None: continue
        price_1d, kumo_top, _ = calc_ichimoku(df_1d)
        if price_1d > kumo_top: continue
        
        df_4h = get_data(symbol, '4h')
        if df_4h is None: continue
        rsi_4h = calc_rsi(df_4h)
        if rsi_4h < FILTRO_RSI_4H: continue
        
        df_1h = get_data(symbol, '1h')
        if df_1h is None: continue
        bb_upper = calc_bollinger(df_1h)
        price_1h = df_1h['c'].iloc[-1]
        
        results.append({
            'symbol': symbol,
            'price': price_1h,
            'rsi4h': round(rsi_4h, 2),
            'bb_upper': round(bb_upper, 4),
            'status': '🔥 ALERTA SHORT' if price_1h >= (bb_upper * 0.99) else 'MADURO'
        })
    return jsonify(results)

@app.route('/api/monitor')
def api_monitor():
    ledger_path = '../ledger_trades.md'
    if not os.path.exists(ledger_path):
        return jsonify({'error': 'Ledger não encontrado'})

    with open(ledger_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    header = '## 🟢 Posições Abertas'
    if header not in content:
        return jsonify([])
        
    after_header = content.split(header)[1]
    section = re.split(r'\n#', after_header)[0]
    
    positions = []
    for line in section.splitlines():
        if '|' in line and '**' in line:
            try:
                parts = [p.strip() for p in line.split('|')]
                if len(parts) < 8: continue
                symbol = parts[2].replace('*', '').strip()
                side = parts[3].strip()
                entry_price = float(parts[6].split('*')[0].strip())
                # Analisar tempo real
                df_4h = get_data(symbol, '4h')
                if df_4h is None: continue
                
                rsi_4h = calc_rsi(df_4h)
                curr_price, kumo_top_4h, kumo_bottom_4h = calc_ichimoku(df_4h)
                
                is_short = side.lower() == 'short'
                
                # Cálculo de PnL Direcional (8x Alavancagem padrão do usuário)
                if is_short:
                    pnl = ((entry_price / curr_price) - 1) * 100 * 8
                else:
                    pnl = ((curr_price / entry_price) - 1) * 100 * 8
                
                # --- LÓGICA DE DECISÃO AVANÇADA (MARCELO VEGA V3) ---
                status = 'TUDO CERTO: SEGURAR'
                
                # 1. Reversão de Tendência (Cruzou a Nuvem)
                if is_short and curr_price > kumo_top_4h:
                    status = 'PERIGOSO: SAIR AGORA'
                elif not is_short and curr_price < kumo_bottom_4h:
                    status = 'PERIGOSO: SAIR AGORA'
                
                # 2. Realização de Lucro (Exaustão do movimento a favor)
                elif is_short and rsi_4h < 45:
                    status = 'LUCRO NO BOLSO?'
                elif not is_short and rsi_4h > 65:
                    status = 'LUCRO NO BOLSO?'
                
                # 3. Exaustão Contra a Posição (Momento de aguardar correção)
                elif is_short and rsi_4h > 75 and pnl < 0:
                    status = 'CALMA: VAI VOLTAR'
                elif not is_short and rsi_4h < 30 and pnl < 0:
                    status = 'CALMA: VAI VOLTAR'
                
                # 4. Ponto de Equilíbrio (Break-even)
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
                    'status': status
                })
            except: continue
    return jsonify(positions)

if __name__ == '__main__':
    app.run(port=5000, debug=True)
