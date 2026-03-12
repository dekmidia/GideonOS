import subprocess
import re
import os

def run_backtest(dias):
    print(f"--- Executando Backtest: {dias} dias ---")
    with open("backtest_laranja_short.py", "r", encoding="utf-8") as f:
        content = f.read()
    
    # Substituição global de 180 pelo valor de teste
    new_content = content.replace(", 180)", f", {dias})")
    
    temp_file = f"temp_backtest_{dias}.py"
    with open(temp_file, "w", encoding="utf-8") as f:
        f.write(new_content)
    
    # Executa ignorando erros de encoding no output para evitar crash no Windows
    try:
        process = subprocess.Popen(["python", temp_file], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='ignore')
        stdout, stderr = process.communicate()
    except Exception as e:
        print(f"Falha ao executar {temp_file}: {e}")
        return 0, 0
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)
    
    # Extrair Win Rate (regex mais flexível)
    win_rate_match = re.search(r"TAXA DE ACERTO SHORT\s+\|\s+([\d\.]+)%", stdout)
    ev_match = re.search(r"EXPECTED VALUE \(EV\)\s+\|\s+([\d\.]+)%", stdout)
    
    win_rate = float(win_rate_match.group(1)) if win_rate_match else 0
    ev = float(ev_match.group(1)) if ev_match else 0
    
    if win_rate == 0 and "Nenhum sinal encontrado" in stdout:
        print(f"  Aviso: Nenhum sinal encontrado em {dias} dias.")
    elif win_rate == 0:
        print(f"  Aviso: Nao foi possivel ler os dados em {dias} dias.")
        # Debug do que foi recebido
        # print(stdout[-200:]) 
    
    return win_rate, ev

periodos = [30, 60, 90]
resultados = {}

for p in periodos:
    wr, ev = run_backtest(p)
    resultados[p] = {"WR": wr, "EV": ev}
    print(f"Resultado {p}d: WR {wr}% | EV {ev}%")

print("\n--- RESUMO FINAL ---")
valid_wr = [v["WR"] for v in resultados.values() if v["WR"] > 0]
valid_ev = [v["EV"] for v in resultados.values() if v["EV"] != 0]

media_wr = sum(valid_wr) / len(valid_wr) if valid_wr else 0
media_ev = sum(valid_ev) / len(valid_ev) if valid_ev else 0

print(f"Media Taxa de Acerto: {media_wr:.2f}%")
print(f"Media Expected Value: {media_ev:.2f}%")
