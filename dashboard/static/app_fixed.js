const API_URL = 'http://127.0.0.1:5000/api';

// --- ESTADO DE SINAIS PINADOS (FAVORITOS) ---
let pinnedSignals = JSON.parse(localStorage.getItem('sentinel_pins') || '[]');

// --- SISTEMA DE ALERTA EM SEGUNDO PLANO (WEB NOTIFICATIONS) ---
let notificationPermission = false;
if ("Notification" in window) {
    if (Notification.permission === "granted") {
        notificationPermission = true;
    } else {
        Notification.requestPermission().then(permission => {
            notificationPermission = (permission === "granted");
        });
    }
}

function sendDesktopNotification(title, message, symbol) {
    if (notificationPermission && document.hidden) {
        new Notification(title, {
            body: message,
            icon: '/static/img/logo.png' // Fallback se existir
        }).onclick = () => {
            window.focus();
            openChart(symbol);
        };
    }
}

// --- CONTROLE DE DUPLICATAS DE NOTIFICAÇÃO ---
const notifiedSignals = new Set();
// Limpa o cache de notificações a cada 1 hora para evitar acúmulo de memória
setInterval(() => notifiedSignals.clear(), 3600000);

// --- CONTAINER DE ALERTAS VISUAIS (SUBSTUTUTO AO TOAST PARA SINAIS) ---
function showPersistentAlert(sig) {
    // DESATIVADO COMPLETAMENTE: O usuário optou por desativar todos os alertas automáticos (Toasts e Desktop)
    return;

    /*
    const signalId = `${sig.symbol}-${sig.side}-${sig.bb_upper}`;
    ...
    */
}

function createAlertContainer() {
    const container = document.createElement('div');
    container.id = 'alert-stack';
    document.body.appendChild(container);
    return container;
}

// --- SISTEMA DE NOTIFICAÇÕES TOAST (INFO RÁPIDA) ---
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = 'toast';
    
    const icons = {
        success: '✅',
        error: '❌',
        info: 'ℹ️',
        gold: '🏆'
    };
    
    toast.innerHTML = `
        <span class="toast-icon">${icons[type] || '🔔'}</span>
        <span>${message}</span>
    `;
    
    container.appendChild(toast);
    setTimeout(() => toast.classList.add('show'), 10);
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 400);
    }, 4000);
}

// --- FUNÇÃO CLIQUE PARA COPIAR ---
async function copyText(text, label) {
    try {
        await navigator.clipboard.writeText(text);
        showToast(`${label} copiado: ${text}`, 'success');
        console.log(`[UI] ${label} copiado para clipboard: ${text}`);
    } catch (err) {
        console.error('Falha ao copiar:', err);
        showToast('Erro ao copiar valor', 'error');
    }
}

function getExplanation(status, side) {
    const isShort = side.toLowerCase() === 'short';
    
    const mapping = {
        'TUDO CERTO: SEGURAR': isShort 
            ? 'Tudo sob controle. O preço deve continuar baixando.' 
            : 'Tudo sob controle. O preço deve continuar subindo.',
        
        'PERIGOSO: SAIR AGORA': isShort
            ? 'Atenção! O preço deve subir agora. O risco de prejuízo ficou muito alto, melhor sair.'
            : 'Atenção! O preço deve cair agora. O risco de prejuízo ficou muito alto, melhor sair.',
        
        'LUCRO NO BOLSO?': isShort
            ? 'O preço já baixou bastante. Ele pode voltar a subir a qualquer hora, garanta seu lucro.'
            : 'O preço já subiu bastante. Ele pode voltar a cair a qualquer hora, garanta seu lucro.',
        
        'CALMA: VAI VOLTAR': isShort
            ? 'O preço subiu demais e está "cansado". Ele deve voltar a baixar em breve, espere.'
            : 'O preço caiu demais e está "cansado". Ele deve voltar a subir em breve, espere.',
        
        'PROTEÇÃO: NO ZERO': 'Você não perde mais nada aqui. O preço voltou para onde você entrou, proteja seu capital.'
    };
    
    return mapping[status] || 'Análise tática em processamento...';
}

// --- LOGICA DE SINAIS PINADOS (FAVORITOS) ---
function togglePin(sinalStr) {
    const sig = JSON.parse(decodeURIComponent(sinalStr));
    const index = pinnedSignals.findIndex(p => p.symbol === sig.symbol);
    
    if (index === -1) {
        pinnedSignals.push(sig);
        showToast(`${sig.symbol} fixado nos favoritos!`, 'success');
    } else {
        pinnedSignals.splice(index, 1);
        showToast(`${sig.symbol} removido dos favoritos.`, 'info');
    }
    
    localStorage.setItem('sentinel_pins', JSON.stringify(pinnedSignals));
    renderPinnedSignals();
    // Atualiza o scanner para refletir o estado do botão
    const latestData = JSON.parse(localStorage.getItem('sentinel_latest_scan') || '[]');
    updateScanner(latestData, true); 
}

function renderPinnedSignals() {
    const section = document.getElementById('pinned-section');
    const tbody = document.getElementById('pinned-body');
    
    if (!section || !tbody) return;

    if (pinnedSignals.length === 0) {
        section.classList.add('hidden');
        return;
    }
    
    section.classList.remove('hidden');
    tbody.innerHTML = '';
    
    pinnedSignals.forEach(sig => {
        const row = document.createElement('tr');
        const side = sig.side || (sig.status.includes('SHORT') || sig.status.includes('LARANJA') ? 'Short' : 'Long');
        const statusClass = side === 'Short' ? 'alert-short' : (sig.status.includes('VETO') ? 'btc-neutro' : 'maduro');
        
        const seasonScore = sig.season_score !== undefined ? sig.season_score : '--';
        const seasonClass = sig.season_trend === 'ALTA' ? 'season-up' : (sig.season_trend === 'BAIXA' ? 'season-down' : '');
        const seasonEmoji = sig.season_trend === 'ALTA' ? '📈' : (sig.season_trend === 'BAIXA' ? '📉' : '⚖️');

        row.innerHTML = `
            <td style="color: var(--text-dim); font-size: 0.75rem;">${sig.timestamp || '--:--:--'}</td>
            <td onclick="openChart('${sig.symbol}')" style="cursor: pointer;">
                <strong>${sig.symbol}</strong><br>
                <small style="color:var(--text-dim);">${sig.bb_upper}</small>
            </td>
            <td class="copyable" onclick="event.stopPropagation(); copyText('${sig.price}', 'Preço')">${sig.price}</td>
            <td class="copyable" style="color: var(--neon-blue);" onclick="event.stopPropagation(); copyText('${sig.tp}', 'TP')">${sig.tp}</td>
            <td class="copyable" style="color: var(--loss-red);" onclick="event.stopPropagation(); copyText('${sig.sl}', 'SL')">${sig.sl}</td>
            <td style="text-align:center;">${sig.score}/10</td>
            <td style="text-align:center;"><span class="season-badge ${seasonClass}">${seasonEmoji} ${seasonScore}</span></td>
            <td><span class="status-tag ${statusClass}">${sig.status}</span></td>
            <td>
                <div style="display: flex; gap: 4px;">
                    <button class="btn-pin active" onclick="togglePin('${encodeURIComponent(JSON.stringify(sig))}')">⭐</button>
                    <button class="btn-action btn-entry pulse-success" onclick="handleEntry('${sig.symbol}', '${sig.price}', '${side}', '${sig.tp}', '${sig.sl}', '${sig.bb_upper}', '${sig.estimativa}')">ENTRAR</button>
                    <button class="btn-action pulse-blue btn-raiox-action" 
                            style="background: var(--neon-blue); padding: 8px 12px; min-width: 40px;" 
                            onclick="event.stopPropagation(); openAnalysis('${sig.symbol}')">⚡</button>
                </div>
            </td>
        `;
        tbody.appendChild(row);
    });
}

// --- LOGICA TRADING VIEW ---
function openChart(symbol) {
    const modal = document.getElementById('chart-modal');
    document.getElementById('modal-symbol').innerText = symbol;
    modal.style.display = 'flex';

    new TradingView.widget({
        "autosize": true,
        "symbol": `BINANCE:${symbol}`,
        "interval": "5",
        "timezone": "Etc/UTC",
        "theme": "dark",
        "style": "1",
        "locale": "br",
        "toolbar_bg": "#f1f3f6",
        "enable_publishing": false,
        "hide_side_toolbar": false,
        "allow_symbol_change": true,
        "studies": [
            "MAExp@tv-basicstudies", // EMA 9
            "MAExp@tv-basicstudies", // EMA 20
            "MAExp@tv-basicstudies", // EMA 200
            "BollingerBands@tv-basicstudies",
            "RSI@tv-basicstudies",
            "AverageTrueRange@tv-basicstudies"
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

// --- LOGICA DE ACOES (ENTRADA/SAIDA) ---
// --- ORDENS BINGX ---
const orderModal = document.getElementById('order-modal');
const closeOrderBtn = document.getElementById('close-order-modal');
const confirmOrderBtn = document.getElementById('btn-confirm-order');

// --- ORDENS SAÍDA (EXIT) ---
const exitModal = document.getElementById('exit-order-modal');
const btnConfirmExit = document.getElementById('btn-confirm-exit');
const btnCancelExit = document.getElementById('btn-cancel-exit');
let pendingExitSymbol = null;
let selectedExitResult = 'WIN'; // Default

function setExitResult(res) {
    selectedExitResult = res;
    // Feedback visual nos botões do modal
    const buttons = document.querySelectorAll('#exit-order-modal .btn-action');
    buttons.forEach(btn => {
        if (btn.innerText.includes(res)) {
            btn.style.boxShadow = '0 0 15px var(--neon-orange)';
            btn.style.border = '2px solid white';
        } else if (btn.innerText.includes('WIN') || btn.innerText.includes('LOSS')) {
            btn.style.boxShadow = 'none';
            btn.style.border = 'none';
        }
    });

    const pnlInput = document.getElementById('exit-pnl-input');
    if (res === 'WIN' && !pnlInput.value.includes('+')) pnlInput.value = '+1.0%';
    if (res === 'LOSS' && !pnlInput.value.includes('-')) pnlInput.value = '-1.0%';
}

async function confirmExit() {
    if (!pendingExitSymbol) return;
    
    const pnlValue = document.getElementById('exit-pnl-input').value || (selectedExitResult === 'WIN' ? '+1.0%' : '-1.0%');
    
    try {
        const response = await fetch(`${API_URL}/exit`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ 
                symbol: pendingExitSymbol,
                result: selectedExitResult,
                pnl: pnlValue
            })
        });
        const result = await response.json();
        if (result.status === 'success') {
            showToast(`${pendingExitSymbol} encerrada: ${selectedExitResult} (${pnlValue})`, 'info');
            exitModal.style.display = 'none';
            updatePortfolio();
            updateHistory();
        } else {
            alert('Erro ao encerrar: ' + result.message);
        }
    } catch (err) {
        console.error('Erro na saída:', err);
    }
}

btnCancelExit.onclick = () => exitModal.style.display = 'none';
btnConfirmExit.onclick = confirmExit;

let activeOrderData = null;

function handleEntry(symbol, price, side, tp, sl, tf, ttt) {
    console.log(`[UI] handleEntry disparado para ${symbol}`, { price, side, tp, sl, tf, ttt });
    const isShort = side.toLowerCase() === 'short';
    
    // Fallback caso tp/sl não venham (segurança)
    const finalTp = tp || (isShort ? price * 0.95 : price * 1.05);
    const finalSl = sl || (isShort ? price * 1.10 : price * 0.90);

    activeOrderData = { 
        symbol, 
        price, 
        side: side.toUpperCase(), 
        tp: parseFloat(finalTp).toFixed(6), 
        sl: parseFloat(finalSl).toFixed(6),
        tf: tf || '1h',
        ttt: ttt || 'N/A'
    };

    if (!orderModal) {
        console.error('[FATAL] Elemento order-modal não encontrado no DOM!');
        alert('Erro interno: Modal de confirmação não encontrado.');
        return;
    }

    document.getElementById('order-symbol').innerText = symbol;
    document.getElementById('order-side').innerText = activeOrderData.side;
    document.getElementById('order-side').className = `order-row ${isShort ? 'side-short' : 'side-long'}`;
    document.getElementById('order-entry').innerText = price;
    document.getElementById('order-tp').innerText = activeOrderData.tp;
    document.getElementById('order-sl').innerText = activeOrderData.sl;

    orderModal.style.display = 'flex';
}

closeOrderBtn.onclick = () => orderModal.style.display = 'none';

confirmOrderBtn.onclick = async () => {
    const margin = document.getElementById('order-margin').value;
    confirmOrderBtn.disabled = true;
    confirmOrderBtn.innerText = 'ENVIANDO...';

    try {
        const res = await fetch(`${API_URL}/bingx/order`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ...activeOrderData, margin })
        });
        const data = await res.json();

        if (data.status === 'success') {
            showToast(`Ordem de ${activeOrderData.side} enviada para ${activeOrderData.symbol}!`, 'success');
            orderModal.style.display = 'none';
            // Após sucesso na BingX, registra no Ledger local com TF e TTT
            await fetch(`${API_URL}/entry`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    symbol: activeOrderData.symbol, 
                    side: activeOrderData.side, 
                    price: activeOrderData.price,
                    tf: activeOrderData.tf,
                    ttt: activeOrderData.ttt,
                    tp: activeOrderData.tp,
                    sl: activeOrderData.sl
                })
            });
            updatePortfolio();
        } else {
            showToast(`Erro na BingX: ${data.message}`, 'error');
        }
    } catch (err) {
        showToast('Erro ao conectar com o Servidor.', 'error');
    } finally {
        confirmOrderBtn.disabled = false;
        confirmOrderBtn.innerText = 'EXECUTAR NA BINGX';
    }
};

async function openAnalysis(symbol) {
    const drawer = document.getElementById('analysis-drawer');
    const grid = document.getElementById('analysis-grid');
    const symbolTitle = document.getElementById('drawer-symbol');
    const verdictValue = document.getElementById('verdict-value');
    const verdictReason = document.getElementById('verdict-reason');
    const confValue = document.getElementById('conf-value');
    const confFill = document.getElementById('conf-fill');

    symbolTitle.innerText = `RAIO-X: ${symbol}`;
    grid.innerHTML = '<div style="grid-column: 1/-1; text-align: center; padding: 20px;">Iniciando varredura multitempo...</div>';
    verdictValue.innerText = '---';
    verdictReason.innerText = 'Consultando 6 tempos gráficos na API...';
    confFill.style.width = '0%';
    confValue.innerText = '0%';
    
    drawer.classList.add('open');

    try {
        const response = await fetch(`${API_URL}/analyze/${symbol}`);
        const data = await response.json();
        
        if (data.status === 'error') throw new Error(data.message);

        // Badge do BTC
        const btcClass = data.btc_status === 'ALTA' ? 'btc-alta' : (data.btc_status === 'BAIXA' ? 'btc-baixa' : 'btc-neutro');
        symbolTitle.innerHTML = `${symbol} <span class="btc-badge ${btcClass}">BTC: ${data.btc_status}</span>`;

        // Renderizar Grid de Timeframes
        grid.innerHTML = '';
        const tfs = ['1m', '5m', '15m', '30m', '1h', '4h'];
        tfs.forEach(tf => {
            const info = data.timeframes[tf];
            if (!info) return; // Proteção contra TF ausente

            const block = document.createElement('div');
            block.className = 'tf-block';
            
            const color = info.trend === 'ALTA' ? 'var(--win-green)' : (info.trend === 'BAIXA' ? 'var(--loss-red)' : 'rgba(255,255,255,0.4)');
            const volStatus = info.volume || 'NORMAL';
            const volClass = volStatus === 'EXAUSTÃO' ? 'vol-exaustao' : (volStatus === 'FORTE' ? 'vol-forte' : '');
            const trendText = info.trend || 'N/A';
            const rsiVal = info.rsi !== undefined ? info.rsi : '??';
            const candleText = info.candle || '';

            block.innerHTML = `
                <span class="tf-label">${tf}</span>
                <span class="tf-status" style="color: ${color}">${trendText}</span>
                <span class="tf-rsi">RSI: ${rsiVal} | ${candleText}</span>
                <span class="vol-badge ${volClass}">${volStatus}</span>
            `;
            grid.appendChild(block);
        });

        // Renderizar Veredito
        verdictValue.innerText = data.verdict || 'INDETERMINADO';
        verdictReason.innerText = data.reason || 'Sem detalhes técnicos.';
        confFill.style.width = `${data.confidence || 0}%`;
        confValue.innerText = `${data.confidence || 0}%`;

        // Carregar Sazonalidade
        loadSeasonality(symbol);

    } catch (err) {
        console.error('[ERRO RAIO-X]', err);
        grid.innerHTML = `<div style="grid-column: 1/-1; color: var(--loss-red);">Erro na análise: ${err.message}</div>`;
    }
}

function closeAnalysis() {
    document.getElementById('analysis-drawer').classList.remove('open');
}

async function handleRestore(symbol, openedAt) {
    if (!confirm(`Deseja restaurar ${symbol} para a carteira ativa?`)) return;
    try {
        const response = await fetch('/api/history/restore', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ symbol, opened_at: openedAt })
        });
        const result = await response.json();
        if (result.status === 'success') {
            updatePortfolio();
            updateHistory();
        } else {
            alert('Erro ao restaurar: ' + result.message);
        }
    } catch (error) {
        console.error('Erro ao restaurar:', error);
    }
}

async function handleExit(symbol) {
    pendingExitSymbol = symbol;
    document.getElementById('exit-symbol-display').innerText = symbol;
    document.getElementById('exit-pnl-input').value = '';
    setExitResult('WIN'); // Reset para WIN por padrão
    exitModal.style.display = 'flex';
}

async function updatePortfolio() {
    try {
        const response = await fetch(`${API_URL}/monitor`);
        const data = await response.json();
        
        let positions = [];
        let macroStatus = "NEUTRO";

        if (data && data.positions) {
            positions = data.positions;
            macroStatus = data.macro;
        } else if (Array.isArray(data)) {
            positions = data;
        }

        const tbody = document.getElementById('portfolio-body');
        tbody.innerHTML = '';

        if (!Array.isArray(positions)) {
            console.error('[UI] Monitor recebeu dado inválido:', positions);
            tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color: var(--loss-red);">Erro ao carregar posições: ${positions.error || 'Resposta inválida'}</td></tr>`;
            return;
        }

        if (positions.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;">Nenhuma posição ativa no Ledger.</td></tr>';
            return;
        }

        let totalPnl = 0;
        positions.forEach(pos => {
            const row = document.createElement('tr');
            
            const pnlValue = parseFloat(pos.pnl) || 0;
            totalPnl += pnlValue;
            
            const isProfit = pnlValue >= 0;
            const pnlClass = isProfit ? 'green' : 'red';
            const explanation = getExplanation(pos.status, pos.side);
            
            row.innerHTML = `
                <td onclick="openChart('${pos.symbol}')" style="cursor: pointer;">
                    <strong>${pos.symbol}</strong><br>
                    <small style="color: #94a3b8;">${pos.side} - ${pos.tf}</small>
                </td>
                <td style="font-size: 0.75rem;">${pos.opened_at}</td>
                <td><strong>${pos.entry}</strong> / ${pos.current}</td>
                <td class="expectancy-ttt">${pos.ttt}</td>
                <td><span class="pnl-badge ${pnlClass}">${isProfit ? '+' : ''}${pnlValue.toFixed(2)}%</span></td>
                <td style="font-size: 0.75rem;">
                    <span style="color: var(--neon-blue);">${pos.tp || 'N/A'}</span> / 
                    <span style="color: var(--loss-red);">${pos.sl || 'N/A'}</span>
                </td>
                <td>
                    <div class="status-container" onclick="event.stopPropagation()">
                        <span class="value status-value">${pos.status} | ${pos.rsi4h}</span>
                        <div class="tooltip">${explanation}</div>
                    </div>
                </td>
                <td>
                    <div style="display: flex; gap: 8px;">
                        <button class="btn-action pulse-blue" style="background: var(--neon-blue); padding: 8px 12px;" onclick="event.stopPropagation(); openAnalysis('${pos.symbol}')">⚡ IA</button>
                        <button class="btn-action btn-exit" style="margin-top: 0; padding: 8px 12px;" onclick="event.stopPropagation(); handleExit('${pos.symbol}')">FECHAR</button>
                    </div>
                </td>
            `;
            tbody.appendChild(row);
        });

        // ATUALIZAR BARRA DE PERFORMANCE GLOBAL
        const activeTrades = positions.length;
        
        document.getElementById('global-trades').innerText = activeTrades;
        const pnlEl = document.getElementById('global-pnl');
        pnlEl.innerText = `${totalPnl > 0 ? '+' : ''}${totalPnl.toFixed(2)}%`;
        pnlEl.className = `perf-value ${totalPnl >= 0 ? 'green' : 'red'}`;

        // Determinar Tendência Global (vinda do Servidor)
        const trendEl = document.getElementById('global-trend');
        trendEl.innerText = macroStatus;
        if (macroStatus.includes('ALTSEASON')) trendEl.style.color = 'var(--win-green)';
        else if (macroStatus.includes('DOMINANTE')) trendEl.style.color = 'var(--neon-orange)';
        else trendEl.style.color = 'white';

    } catch (err) {
        console.error('Erro ao atualizar carteira:', err);
    }
}

async function manualScan() {
    const btn = document.getElementById('btn-scan');
    const tbody = document.getElementById('scanner-body');
    const logArea = document.getElementById('log-display');
    const progressContainer = document.getElementById('progress-container');
    const progressBar = document.getElementById('progress-bar');

    btn.disabled = true;
    btn.innerText = 'SCANEANDO...';
    progressContainer.classList.remove('progress-hidden');
    progressBar.style.width = '0%';
    
    tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--neon-orange);">Executando varredura multithread em +400 moedas...</td></tr>';
    logArea.innerText = `[SCANNER] Iniciando varredura manual em ${new Date().toLocaleTimeString()}...`;
    showToast('Iniciando varredura em 400+ moedas...', 'info');

    // Polling de sinais parciais para não deixar a tela vazia
    const pollInterval = setInterval(() => {
        updateScanner(true); // true = modo silencioso (sem limpar tela)
    }, 3000);

    // Animação de progresso (estimativa)
    let progress = 0;
    const progressInterval = setInterval(() => {
        if (progress < 95) {
            progress += (95 - progress) * 0.05;
            progressBar.style.width = `${progress}%`;
        }
    }, 1000);

    try {
        await updateScanner();
        progressBar.style.width = '100%';
        logArea.innerText = `[SCANNER] Varredura finalizada com sucesso!`;
        showToast('Scanner finalizado. Novas oportunidades disponíveis!', 'success');
    } catch (err) {
        logArea.innerText = `[SCANNER] Falha na varredura.`;
    } finally {
        clearInterval(pollInterval);
        clearInterval(progressInterval);
        setTimeout(() => {
            progressContainer.classList.add('progress-hidden');
            btn.disabled = false;
            btn.innerText = 'SCANEAR AGORA';
        }, 1500);
    }
}

let scannerSortOrder = 'desc'; // 'desc' ou 'asc'

function toggleScannerSort() {
    scannerSortOrder = scannerSortOrder === 'desc' ? 'asc' : 'desc';
    const scoreHeader = document.getElementById('header-score');
    if (scoreHeader) {
        scoreHeader.innerText = `Score ${scannerSortOrder === 'desc' ? '▼' : '▲'}`;
    }
    updateScanner();
}

async function updateScanner(isSilent = false) {
    try {
        const endpoint = isSilent ? 'latest_signals' : 'scanner';
        const response = await fetch(`${API_URL}/${endpoint}`);
        let signals = await response.json();
        
        if (isSilent && signals.length === 0) return; // Não limpa nada se for silent e vazio

        // Aplicar ordenação
        signals.sort((a, b) => {
            const scoreA = parseFloat(a.score) || 0;
            const scoreB = parseFloat(b.score) || 0;
            return scannerSortOrder === 'desc' ? scoreB - scoreA : scoreA - scoreB;
        });

        const tbody = document.getElementById('scanner-body');
        
        // Se houver sinais novos e houver mudança na contagem, atualiza a tabela
        // Ou se não for silent (que é quando a varredura termina)
        const currentRows = tbody.querySelectorAll('tr').length;
        if (isSilent && signals.length <= (currentRows > 1 ? currentRows : 0) && currentRows > 1) {
            return; // Evita re-renderizar se não houver novidades
        }

        // Salva para persistência do estado do scanner (botões pin)
        localStorage.setItem('sentinel_latest_scan', JSON.stringify(signals));

        tbody.innerHTML = '';

        if (signals.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" style="text-align: center;">Varredura completa. Sem sinais no momento.</td></tr>';
            return;
        }

        signals.forEach(sig => {
            const row = document.createElement('tr');
            row.style.cursor = 'pointer';
            
            // Disparar Alerta Visual se for sinal novo e de confiança (somente no polling silencioso)
            if (isSilent && !sig.status.includes('VETO') && sig.score >= 8) {
                showPersistentAlert(sig);
            }

            // Destaque para Sinais de Ouro e Veto
            if (sig.status.includes('VETO')) {
                row.style.opacity = '0.6';
            } else if (parseFloat(sig.score) >= 8.5) {
                row.classList.add('gold-signal');
            }
            
            const side = sig.side || (sig.status.includes('SHORT') || sig.status.includes('LARANJA') ? 'Short' : 'Long');
            const statusClass = side === 'Short' ? 'alert-short' : (sig.status.includes('VETO') ? 'btc-neutro' : 'maduro');
            const isPinned = pinnedSignals.some(p => p.symbol === sig.symbol);

            const seasonScore = sig.season_score !== undefined ? sig.season_score : '--';
            const seasonClass = sig.season_trend === 'ALTA' ? 'season-up' : (sig.season_trend === 'BAIXA' ? 'season-down' : '');
            const seasonEmoji = sig.season_trend === 'ALTA' ? '📈' : (sig.season_trend === 'BAIXA' ? '📉' : '⚖️');

            row.innerHTML = `
                <td style="color: var(--text-dim); font-size: 0.75rem;">${sig.timestamp || '--:--:--'}</td>
                <td onclick="openChart('${sig.symbol}')" style="cursor: pointer;"><strong>${sig.symbol}</strong><br><small style="color:var(--text-dim);">${sig.bb_upper}</small></td>
                <td class="copyable" onclick="event.stopPropagation(); copyText('${sig.price}', 'Preço')">${sig.price}</td>
                <td class="copyable" style="color: var(--neon-blue);" onclick="event.stopPropagation(); copyText('${sig.tp}', 'TP')">${sig.tp}</td>
                <td class="copyable" style="color: var(--loss-red);" onclick="event.stopPropagation(); copyText('${sig.sl}', 'SL')">${sig.sl}</td>
                <td style="text-align:center;">${sig.score}/10</td>
                <td style="text-align:center;"><span class="season-badge ${seasonClass}">${seasonEmoji} ${seasonScore}</span></td>
                <td><span class="status-tag ${statusClass}">${sig.status}</span></td>
                <td>
                    <div style="display: flex; gap: 4px;">
                        <button class="btn-pin ${isPinned ? 'active' : ''}" onclick="event.stopPropagation(); togglePin('${encodeURIComponent(JSON.stringify(sig))}')">⭐</button>
                        <button class="btn-action btn-entry pulse-success btn-entry-action">ENTRAR</button>
                        <button class="btn-action pulse-blue btn-raiox-action" 
                                style="background: var(--neon-blue); padding: 8px 12px; min-width: 40px;" 
                                onclick="event.stopPropagation(); console.log('[UI] Abrindo Raio-X para ${sig.symbol}'); openAnalysis('${sig.symbol}')">⚡</button>
                    </div>
                </td>
            `;

            const bntEntry = row.querySelector('.btn-entry-action');
            bntEntry.addEventListener('click', (e) => {
                e.stopPropagation();
                handleEntry(sig.symbol, sig.price, side, sig.tp, sig.sl, sig.bb_upper, sig.estimativa);
            });

            tbody.appendChild(row);
        });
        
        renderPinnedSignals(); // Garante que a seção de favoritos esteja sincronizada
        
        if (!isSilent) {
            const logArea = document.getElementById('log-display');
            logArea.innerText = `[SCANNER] Varredura finalizada às ${new Date().toLocaleTimeString()}`;
        }
        
    } catch (err) {
        if (!isSilent) {
            console.error('Erro ao atualizar scanner:', err);
            const tbody = document.getElementById('scanner-body');
            tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--loss-red);">Erro na conexão com a Binance.</td></tr>';
        }
    }
}

function updateTime() {
    const now = new Date();
    document.getElementById('time-display').innerText = now.toLocaleTimeString();
}

// --- LOGICA DE NAVEGACAO (TABS) ---
function switchTab(tabId) {
    // Esconde todos os conteúdos e remove active das abas
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    document.querySelectorAll('.tab-link').forEach(l => l.classList.remove('active'));
    
    // Mostra o selecionado
    document.getElementById(tabId).classList.add('active');
    
    // Ativa o botão correto (busca pelo onclick que contém o tabId)
    document.querySelector(`.tab-link[onclick*="${tabId}"]`).classList.add('active');
    
    // Se for a aba de histórico, carrega os dados
    if (tabId === 'history-section') {
        updateHistory();
    }
}

async function updateHistory() {
    try {
        const response = await fetch(`${API_URL}/history`);
        const history = await response.json();
        
        const tbody = document.getElementById('history-body');
        tbody.innerHTML = '';

        if (history.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align: center;">Nenhum registro no histórico.</td></tr>';
            return;
        }

        history.forEach(trade => {
            const row = document.createElement('tr');
            const isWin = trade.result.includes('WIN');
            const resultTag = isWin ? 'maduro' : 'alert-short'; // Reutilizando cores
            const pnlClass = trade.pnl.includes('+') ? 'green' : 'red';

            row.innerHTML = `
                <td style="font-size: 0.75rem;">${trade.opened_at}</td>
                <td style="font-size: 0.75rem;">${trade.closed_at}</td>
                <td><strong>${trade.symbol}</strong></td>
                <td>${trade.tf}</td>
                <td>${trade.ttt}</td>
                <td>${trade.side}</td>
                <td><span class="status-tag ${resultTag}">${trade.result}</span></td>
                <td><span class="${pnlClass}">${trade.pnl}</span></td>
                <td style="font-size: 0.75rem; color: #94a3b8;">${trade.notes}</td>
                <td>
                    <button class="btn-action pulse-blue" style="padding: 4px 10px; font-size: 0.65rem; background: var(--neon-blue); min-width: auto; height: auto;" 
                        onclick="handleRestore('${trade.symbol}', '${trade.opened_at}')">RESTAURAR</button>
                </td>
            `;
            tbody.appendChild(row);
        });
    } catch (err) {
        console.error('Erro ao atualizar histórico:', err);
    }
}

// Inicia os processos
updatePortfolio();
updateScanner();
renderPinnedSignals();
setInterval(updatePortfolio, 30000); // 30s para carteira
setInterval(() => updateScanner(true), 10000); // Polling silencioso a cada 10s (Background Watcher)
setInterval(updateTime, 1000);

