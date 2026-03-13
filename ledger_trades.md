| **Backtest Precisão (V3)** | **83.4%** (Setup Ichimoku) |
| **Expected Value (EV)** | **2.15% por trade** |
| **PnL Total Real Acumulado** | ~37% |

---

## 🟢 Posições Abertas
| Data | Par | Tipo | Estratégia | Alavancagem | Preço Entrada | Alvo (TP) | Stop (SL) |
|:---:|---|:---:|:---:|:---:|:---:|:---:|:---:|
| 12/03/26 | **JTOUSDT** | Short | Laranja V3 | 8x | 0.2724 | 0.2724* | 0.2994 |
| 12/03/26 | **IMXUSDT** | Short | Laranja V3 | 8x | 0.1649 | 0.1649* | 0.1850 |

*\*Alvos de JTO e IMX ajustados para Break-even (Gestão de Crise de 12/03).*

---

## 🔴 Histórico de Operações (Encerradas)

| Data | Par | Tipo | Estratégia | Alavancagem | Resultado | PnL (%) | Notas |
|:---:|---|:---:|:---:|:---:|:---:|:---:|---|
| 12/03/26 | **ACEUSDT** | Short | Laranja | 20x | ✅ WIN | +29.0% | Seguiu trava de lucro após teste das médias. |
| 12/03/26 | **HIGHUSDT** | Short | Laranja | 5x | ✅ WIN | +8.7% | Rejeição clássica em topo, fechado no suporte. |

---

## 🧠 Notas de Aprendizado (Machine Learning Manual)
- **ACEUSDT (12/03)**: A proteção com Stop Gain foi crucial. O ativo mostrou força vendedora, mas a EMA 200 é uma barreira que deve ser respeitada sempre.
- **HIGHUSDT (12/03)**: Alavancagem baixa (5x) permite segurar a volatilidade do pavio inicial. O alvo na EMA 200 foi preciso.

### 4. Bandas de Bollinger (BBs — 20 períodos, 2σ)
As bandas medem a dispersão do preço em relação à média. São as "fronteiras" do gráfico.
*   **Banda Superior**: Quando o preço toca ou fura aqui, ele está "caro" (sobrecomprado).
*   **Banda Inferior**: Quando toca aqui, está "barato" (sobrevendido).
*   **O "Squeeze"**: Quando as bandas se apertam muito, indica que uma explosão de volatilidade está vindo.
*   **No Laranja Short**: Se o sinal aparecer **tocando ou fora da Banda Superior**, a probabilidade de um tombo de volta à média é de quase 80%.

---

## 🛡️ Política de Alavancagem Recomendada (Setup V3)
Baseado no Win Rate de **83.4%** e Stop Loss técnico de **10%**:

| Perfil | Alavancagem | Risco por Trade | Observação |
| :--- | :---: | :---: | :--- |
| **Conservador** | 2x - 5x | Baixo | Recomendado para iniciantes ou bancas grandes. |
| **Moderado** | **5x - 10x** | **Médio** | **O "Sweet Spot" para este setup.** Equilíbrio ideal. |
| **Agressivo** | 10x - 12x | Alto | Apenas se o RSI estiver acima de 80 (Exaustão extrema). |

> [!WARNING]
> **NUNCA exceder 12x** nesta estratégia. Com um Stop Loss de 10%, uma alavancagem de 10x já representa 100% de perda da margem se o stop for atingido. Use sempre **Margem Isolada**.

---
> [!NOTE]
> *Sempre que uma nova posição for aberta ou fechada, informe o bot para atualização deste registro.*
