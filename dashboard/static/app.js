const API_URL = 'http://127.0.0.1:5000/api';

const STATUS_EXPLAIN = {
    'TUDO CERTO: SEGURAR': 'Tudo sob controle. O plano continua o mesmo: manter a posição e esperar o preço baixar.',
    'PERIGOSO: SAIR AGORA': 'Atenção! O mercado virou contra nós agora. O risco aumentou muito e pode ser melhor sair da posição.',
    'LUCRO NO BOLSO?': 'Hora de colher! O preço já caiu bastante. Pode ser uma boa hora para garantir o seu lucro agora.',
    'CALMA: VAI VOLTAR': 'Fique tranquilo. O preço subiu demais e está cansado. Ele deve voltar a cair em breve, então vale a pena esperar.',
    'PROTEÇÃO: NO ZERO': 'Ponto de Segurança! O preço voltou para onde você entrou. Proteja-se para não sair no prejuízo.'
};

// --- LOGICA TRADING VIEW ---
function openChart(symbol) {
    const modal = document.getElementById('chart-modal');
    document.getElementById('modal-symbol').innerText = symbol;
    modal.style.display = 'flex';

    new TradingView.widget({
        "autosize": true,
        "symbol": `BINANCE:${symbol}`,
        "interval": "240",
        "timezone": "Etc/UTC",
        "theme": "dark",
        "style": "1",
        "locale": "br",
        "toolbar_bg": "#f1f3f6",
        "enable_publishing": false,
        "hide_side_toolbar": false,
        "allow_symbol_change": true,
        "studies": [
            "IchimokuCloud@tv-basicstudies",
            "BollingerBands@tv-basicstudies",
            "RSI@tv-basicstudies"
        ],
        "container_id": "tradingview-container"
    });
}

function closeModal() {
    document.getElementById('chart-modal').style.display = 'none';
    document.getElementById('tradingview-container').innerHTML = ''; // Limpa o widget
}

// Listeners do Modal
document.getElementById('close-modal').onclick = closeModal;
window.onclick = (event) => {
    if (event.target == document.getElementById('chart-modal')) closeModal();
};

async function updatePortfolio() {
    try {
        const response = await fetch(`${API_URL}/monitor`);
        const positions = await response.json();
        
        const grid = document.getElementById('portfolio-grid');
        grid.innerHTML = '';

        if (positions.length === 0) {
            grid.innerHTML = '<div class="card" style="text-align:center;">Nenhuma posição ativa no Ledger.</div>';
            return;
        }

        positions.forEach(pos => {
            const card = document.createElement('div');
            card.className = 'card';
            card.onclick = () => openChart(pos.symbol);
            card.style.cursor = 'pointer';
            
            const isProfit = pos.pnl >= 0;
            const pnlClass = isProfit ? 'green' : 'red';
            const explanation = STATUS_EXPLAIN[pos.status] || 'Análise tática em processamento...';
            
            card.innerHTML = `
                <div class="card-header">
                    <span class="symbol-name">${pos.symbol}</span>
                    <span class="pnl-badge ${pnlClass}">${isProfit ? '+' : ''}${pos.pnl}%</span>
                </div>
                <div class="card-body">
                    <div class="data-item">
                        <span class="label">ENTRADA</span>
                        <span class="value">${pos.entry}</span>
                    </div>
                    <div class="data-item">
                        <span class="label">ATUAL</span>
                        <span class="value">${pos.current}</span>
                    </div>
                    <div class="data-item">
                        <span class="label">STATUS</span>
                        <div class="status-container" onclick="event.stopPropagation()">
                            <span class="value status-value">${pos.status}</span>
                            <div class="tooltip">${explanation}</div>
                        </div>
                    </div>
                    <div class="data-item">
                        <span class="label">RSI 4H</span>
                        <span class="value">${pos.rsi4h}</span>
                    </div>
                </div>
            `;
            grid.appendChild(card);
        });
    } catch (err) {
        console.error('Erro ao atualizar carteira:', err);
    }
}

async function updateScanner() {
    try {
        const response = await fetch(`${API_URL}/scanner`);
        const signals = await response.json();
        
        const tbody = document.getElementById('scanner-body');
        tbody.innerHTML = '';

        if (signals.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" style="text-align: center;">Varredura completa. Sem sinais no momento.</td></tr>';
            return;
        }

        signals.forEach(sig => {
            const row = document.createElement('tr');
            row.style.cursor = 'pointer';
            row.onclick = () => openChart(sig.symbol);
            
            const statusClass = sig.status.includes('ALERTA') ? 'alert-short' : 'maduro';
            
            row.innerHTML = `
                <td><strong>${sig.symbol}</strong></td>
                <td>${sig.price}</td>
                <td>${sig.rsi4h}</td>
                <td>${sig.bb_upper}</td>
                <td><span class="status-tag ${statusClass}">${sig.status}</span></td>
            `;
            tbody.appendChild(row);
        });
        
        // Log update
        const logArea = document.getElementById('log-display');
        logArea.innerText = `[SCANNER] Última atualização: ${new Date().toLocaleTimeString()}`;
        
    } catch (err) {
        console.error('Erro ao atualizar scanner:', err);
    }
}

function updateTime() {
    const now = new Date();
    document.getElementById('time-display').innerText = now.toLocaleTimeString();
}

// Inicia os processos
updatePortfolio();
updateScanner();
setInterval(updatePortfolio, 30000); // 30s para carteira
setInterval(updateScanner, 60000);   // 1min para scanner
setInterval(updateTime, 1000);
