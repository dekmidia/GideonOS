import requests

binance_list = [
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

def get_bingx_symbols():
    try:
        r = requests.get('https://open-api.bingx.com/openApi/swap/v2/quote/contracts')
        data = r.json()
        if data.get('code') == 0:
            return [c['symbol'].replace('-', '') for c in data['data'] if c['symbol'].endswith('-USDT')]
        return []
    except Exception as e:
        print(f"Error fetching symbols: {e}")
        return []

bingx_list = get_bingx_symbols()
final_list = sorted([s for s in binance_list if s in bingx_list])

print("LISTA_PRIORIDADE = [")
for i in range(0, len(final_list), 5):
    chunk = final_list[i:i+5]
    line = "    " + ", ".join([f"'{s}'" for s in chunk]) + ","
    print(line)
print("]")
