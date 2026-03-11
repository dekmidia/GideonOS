import os
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def testar_conexao():
    print(f"--- TESTE DE CONEXÃO TELEGRAM ---")
    if not TOKEN or not CHAT_ID:
        print("❌ ERRO: Variáveis de ambiente não encontradas no .env")
        return

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": "🚀 *Gideon Sentinel:* Conexão Estabelecida!\nO scanner está pronto para envio de sinais.",
        "parse_mode": "Markdown"
    }
    
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            print("✅ SUCESSO! Verifique seu Telegram.")
        else:
            print(f"❌ FALHA: Status {resp.status_code} - {resp.text}")
    except Exception as e:
        print(f"❌ ERRO: {e}")

if __name__ == "__main__":
    testar_conexao()
