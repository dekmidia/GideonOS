# 📐 Referência de Indicadores Técnicos

## RSI — Relative Strength Index

```
RSI = 100 - [100 / (1 + RS)]
RS  = Média de ganhos (n períodos) / Média de perdas (n períodos)
n   = 14 (padrão)

Interpretação:
  < 30  = Sobrevenda (possível reversão alta)
  30-40 = Zona de recuperação (sinal: cruzar acima de 40)
  40-60 = Neutro
  60-70 = Momentum forte
  > 70  = Sobrecompra (cautela para novos longs)
```

---

## MFI — Money Flow Index

```
Typical Price (TP) = (High + Low + Close) / 3
Raw Money Flow    = TP × Volume
Money Ratio       = Positive MF / Negative MF
MFI               = 100 - [100 / (1 + Money Ratio)]
n                 = 14 (padrão)

Interpretação:
  < 20  = Sobrevenda (possível reversão)
  > 80  = Sobrecompra (cautela)
  Cruzar 50 para cima = Capital entrando — sinal bullish
```

---

## Stochastic Oscillator

```
%K = [(Close - Lowest Low) / (Highest High - Lowest Low)] × 100
     Período: 14 candles

%D = SMA de 3 períodos do %K

Smooth %K = SMA de 3 do %K bruto (Stoch Slow)

Interpretação:
  %K < 20 = Sobrevenda
  %K > 80 = Sobrecompra
  Cruzamento %K > %D com %K < 20 = SINAL DE COMPRA FORTE
  Cruzamento %K > %D na zona neutra = confirmação de tendência
```

---

## Squeeze Momentum (LazyBear)

```
Componentes:
  BB  = Bollinger Bands (20 períodos, 2.0σ)
  KC  = Keltner Channels (20 períodos, 1.5 ATR)

Squeeze ON  = BB está DENTRO do KC (compressão de volatilidade)
Squeeze OFF = BB está FORA do KC (liberação — movimento iminente)

Momentum = Média linear do desvio do preço em relação à média

Histograma:
  Verde crescente  = Momentum bullish forte    ✅ SINAL
  Verde decrescente = Momentum bullish fraco   ⚠️
  Vermelho crescente = Momentum bearish forte  ❌
  Vermelho decrescente = Momentum bearish fraco ⚠️

SINAL DE COMPRA: Squeeze OFF + Histograma verde nascente
```

---

## Bollinger Bands

```
Middle Band = SMA(20)
Upper Band  = SMA(20) + 2σ
Lower Band  = SMA(20) - 2σ

σ = Desvio padrão do Close dos últimos 20 períodos

Interpretação relevante para pump:
  Squeeze (bandas estreitas) + rompimento da banda superior = pump
  Toque na banda inferior + volume + reversão = setup de entrada
  %B = (Close - Lower) / (Upper - Lower)
    %B > 1.0 = acima da banda superior (breakout)
    %B < 0.0 = abaixo da banda inferior (sobrevenda)
```

---

## EMA 9 — Exponential Moving Average

```
EMA(t) = Close(t) × k + EMA(t-1) × (1-k)
k = 2 / (n + 1) = 2 / 10 = 0.1818

Papel: média rápida de curto prazo
Cruzamento EMA9 > SMA20 = mudança de momentum para bullish
```

---

## SMA 20 — Simple Moving Average

```
SMA(20) = Soma dos últimos 20 closes / 20

Papel: média de referência intermediária
Funciona como suporte dinâmico em tendências de alta
```

---

## EMA 200 — Exponential Moving Average Longa

```
k = 2 / 201 = 0.00995

Papel: define o regime macro da moeda
Preço ACIMA da EMA200 = mercado em tendência de alta macro
Preço ABAIXO da EMA200 = mercado em tendência de baixa macro

Regra: NUNCA emitir sinal de compra com preço abaixo da EMA200
       (exceto em setups de reversão explicitamente identificados)
```

---

## Parâmetros de Cálculo por Timeframe

| Indicador | 5m | 15m | 1h |
|---|---|---|---|
| RSI | Confirma | **Principal** | Contexto |
| MFI | Confirma | **Principal** | Contexto |
| Stochastic | Ruído | **Principal** | Filtro macro |
| Squeeze | Scalp | **Principal** | Tendência |
| BB | Confirma | **Principal** | Range |
| EMA 9 | Ruído | **Sinal** | Tendência |
| SMA 20 | Suporte | **Sinal** | Tendência |
| EMA 200 | Irrelevante | Referência | **Filtro macro** |

> **Regra de ouro:** O sinal nasce no 15m, é confirmado pelo 1h e executado no 5m.
