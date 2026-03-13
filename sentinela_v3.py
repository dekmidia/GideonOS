import requests
import pandas as pd
import os
import argparse
from datetime import datetime

# --- CONFIGURAÇÕES DA ESTRATÉGIA ---
FILTRO_RSI_4H = 70
FILTRO_ICHIMOKU_1D = True # Preço deve estar abaixo da nuvem no 1D
LIMITE_VOLUME_24H = 50000000 # 50M USDT mínimo

def get_data(symbol, interval, limit=100):
    try:
        url = f'https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}'
        r = requests.get(url, timeout=10).json()
        df = pd.DataFrame(r, columns=['t','o','h','l','c','v','ct','q','tr','tb','tg','i'])
        df['c'] = df['c'].astype(float)
        df['h'] = df['h'].astype(float)
        df['l'] = df['l'].astype(float)
        return df
    except Exception as e:
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
    kumo_top = max(sa, sb)
    kumo_bottom = min(sa, sb)
    
    return price, sa, sb, kumo_top, kumo_bottom

def calc_bollinger(df, period=20, std=2):
    sma = df['c'].rolling(period).mean()
    std_dev = df['c'].rolling(period).std()
    upper = sma + (std_dev * std)
    lower = sma - (std_dev * std)
    return upper.iloc[-1], lower.iloc[-1]

def run_scanner():
    print(f'\n[SENTINELA V3] Iniciando Varredura de Mercado - {datetime.now().strftime("%H:%M:%S")}')
    print('------------------------------------------------------------')
    
    # Pegar todos os pares USDT com volume expressivo
    ticker_url = 'https://api.binance.com/api/v3/ticker/24hr'
    tickers = requests.get(ticker_url).json()
    
    # Filtrar apenas pares USDT e volume > LIMITE
    pairs = [t['symbol'] for t in tickers if t['symbol'].endswith('USDT') and float(t['quoteVolume']) > LIMITE_VOLUME_24H]
    
    found = 0
    for symbol in pairs[:50]: # Limitando a 50 para o teste inicial de performance
        # 1D - Filtro de Tendência
        df_1d = get_data(symbol, '1d')
        if df_1d is None: continue
        price_1d, sa, sb, kumo_top, kumo_bottom = calc_ichimoku(df_1d)
        
        if price_1d > kumo_top: continue # Tendência de alta no 1D (Fora do setup Short)
        
        # 4H - Filtro de Exaustão
        df_4h = get_data(symbol, '4h')
        if df_4h is None: continue
        rsi_4h = calc_rsi(df_4h)
        
        if rsi_4h < FILTRO_RSI_4H: continue
        
        # 1H - Gatilho Bollinger
        df_1h = get_data(symbol, '1h')
        if df_1h is None: continue
        bb_upper, bb_lower = calc_bollinger(df_1h)
        price_1h = df_1h['c'].iloc[-1]
        
        if price_1h >= (bb_upper * 0.99): # Próximo ou acima da banda superior
             print(f'🚨 SINAL SHORT: {symbol}')
             print(f'   - RSI 4H: {rsi_4h:.2f} (SOBRECOMPRA)')
             print(f'   - Ichimoku 1D: ABAIXO DA NUVEM (TENDÊNCIA OK)')
             print(f'   - Bollinger 1H: TOCANDO TOPO ({price_1h:.4f} / {bb_upper:.4f})')
             print('------------------------------------------------------------')
             found += 1
             
    if found == 0:
        print('Nenhum sinal encontrado no momento. Aguardando exaustão...')

def monitor_ledger():
    ledger_path = 'ledger_trades.md'
    if not os.path.exists(ledger_path):
        print('Erro: ledger_trades.md não encontrado.')
        return

    print(f'\n[SENTINELA V3] Monitorando Posições Ativas - {datetime.now().strftime("%H:%M:%S")}')
    print('------------------------------------------------------------')
    
    with open(ledger_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Isolar a seção "Posições Abertas"
    if '## 🟢 Posições Abertas' not in content:
        print('Seção de posições abertas não encontrada.')
        return
        
    import re
    
    # Isolar a seção "Posições Abertas" de forma mais robusta
    header = '## 🟢 Posições Abertas'
    if header not in content:
        print(f'Erro: Cabeçalho "{header}" não encontrado no Ledger.')
        return
        
    # Pegar tudo após o cabeçalho
    after_header = content.split(header)[1]
    # Tentar encontrar a próxima seção (começando com ## ou #)
    section_parts = re.split(r'\n#', after_header)
    section = section_parts[0]

    lines_to_process = section.splitlines()

    # Processar cada linha da seção
    for line in lines_to_process:
        line = line.strip()
        # Verificar se a linha contém pipes e o símbolo entre asteriscos
        if '|' in line and '**' in line:
            try:
                parts = [p.strip() for p in line.split('|')]
                # Uma linha de tabela válida tem pelo menos 8 colunas | data | symbol | side | strategy | lev | entry | tp | sl |
                if len(parts) < 8: continue
                
                # Símbolo no index 2 (**JTOUSDT**)
                symbol = parts[2].replace('*', '').strip()
                # Tipo no index 3 (Short/Long)
                side = parts[3].strip()
                # Preço de Entrada no index 6
                entry_str = parts[6].split('*')[0].strip()
                entry_price = float(entry_str)
                
                # Analisar tempo real
                df_4h = get_data(symbol, '4h')
                if df_4h is None:
                    print(f'Falha ao obter dados para {symbol}')
                    continue
                    
                rsi_4h = calc_rsi(df_4h)
                curr_price = df_4h['c'].iloc[-1]
                
                # Cálculo de PnL Aproximado (Short)
                pnl = ((entry_price / curr_price) - 1) * 100 * 8 # Assumindo 8x padrão
                
                status = 'MANTER'
                if rsi_4h < 50: status = 'REALIZAR LUCRO?'
                if (side.lower() == 'short' and curr_price <= entry_price) or (side.lower() == 'long' and curr_price >= entry_price):
                    status = 'PONTO DE BE (SAÍDA TÁTICA)'
                
                print(f'📦 {symbol} ({side}): {curr_price:.4f} (PnL Est: {pnl:.2f}%)')
                print(f'   - RSI 4H: {rsi_4h:.2f} | Status: {status}')
                print('------------------------------------------------------------')
            except Exception as e:
                continue

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Sentinela V3 - Monitor de Trading Laranja Mecânica')
    parser.add_argument('--scan', action='store_true', help='Executar varredura de mercado')
    parser.add_argument('--monitor', action='store_true', help='Monitorar posições no Ledger')
    
    args = parser.parse_args()
    
    if args.scan:
        run_scanner()
    elif args.monitor:
        monitor_ledger()
    else:
        print('Use --scan ou --monitor')
