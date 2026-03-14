import re
import os
import requests
import json
import pandas as pd

def get_data(symbol, interval, limit=100):
    try:
        url = f'https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}'
        r = requests.get(url, timeout=5).json()
        if not isinstance(r, list): return None
        df = pd.DataFrame(r, columns=['t','o','h','l','c','v','ct','q','tr','tb','tg','i'])
        df['c'] = df['c'].astype(float)
        df['h'] = df['h'].astype(float)
        df['l'] = df['l'].astype(float)
        df['o'] = df['o'].astype(float)
        return df
    except:
        return None

def calc_rsi(df, period=14):
    delta = df['c'].diff()
    gain = (delta.where(delta > 0, 0))
    loss = (-delta.where(delta < 0, 0))
    avg_gain = gain.ewm(com=period-1, adjust=False).mean()
    avg_loss = loss.ewm(com=period-1, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-10)
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1]

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

def test_monitor():
    ledger_path = 'ledger_trades.md'
    if not os.path.exists(ledger_path):
        print("Ledger not found")
        return

    with open(ledger_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    header = '## 🟢 Posições Abertas'
    if header not in content:
        print("Header not found")
        return
        
    after_header = content.split(header)[1]
    section = re.split(r'\n#', after_header)[0]
    
    positions = []
    print(f"Section length: {len(section)}")
    for line in section.splitlines():
        print(f"Checking line: {line}")
        if '|' in line and '**' in line:
            try:
                parts = [p.strip() for p in line.split('|')]
                print(f"Parts: {parts}")
                if len(parts) < 8: 
                    print(f"Len parts < 8: {len(parts)}")
                    continue
                symbol = parts[2].replace('*', '').strip()
                side = parts[3].strip()
                entry_price_str = parts[6].split('*')[0].strip()
                print(f"Symbol: {symbol}, Side: {side}, EntryStr: {entry_price_str}")
                entry_price = float(entry_price_str)
                
                df_4h = get_data(symbol, '4h')
                if df_4h is None: 
                    print(f"get_data failed for {symbol}")
                    continue
                
                rsi_4h = calc_rsi(df_4h)
                curr_price, kumo_top_4h, kumo_bottom_4h = calc_ichimoku(df_4h)
                
                is_short = side.lower() == 'short'
                if is_short:
                    pnl = ((entry_price / curr_price) - 1) * 100 * 8
                else:
                    pnl = ((curr_price / entry_price) - 1) * 100 * 8
                
                positions.append({
                    'symbol': symbol,
                    'side': side,
                    'pnl': round(pnl, 2)
                })
                print(f"Added {symbol}")
            except Exception as e:
                print(f"Error processing line: {e}")
                continue
    print(f"Final positions: {positions}")

test_monitor()
