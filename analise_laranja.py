import os
import requests
import json
import base64

print("Para analisar as imagens enviadas e extrair o padrão morfológico dos candles no gráfico de 4H antes da linha laranja, precisamos usar inteligência visual para descrever a estrutura de preço/candle/volume das 8 imagens na pasta `images`.")

print("\nAs imagens são:")
for img in os.listdir("C:\\Users\\Douglas Rodolfo\\Documents\\GideonOS\\images"):
    print("-", img)

print("\nIsso irá orientar a nova heurística Preditiva Laranja.")
