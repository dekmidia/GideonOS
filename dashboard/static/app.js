const API_URL = 'http://127.0.0.1:5000/api';

// --- ESTADO DE PROJEÇÕES ---
let globalProjectionData = { macro: null, local: null };
let currentProjectionMode = 'macro';
let activeOrderData = null;

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
            icon: '/static/img/logo.png' 
        }).onclick = () => {
            window.focus();
            openChart(symbol);
        };
    }
}

const notifiedSignals = new Set();
setInterval(() => notifiedSignals.clear(), 3600000);

function showPersistentAlert(sig) { return; }

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = 'toast';
    const icons = { success: '✅', error: '❌', info: 'ℹ️', gold: '🏆' };
    toast.innerHTML = `<span class="toast-icon">${icons[type] || '🔔'}</span><span>${message}</span>`;
    container.appendChild(toast);
    setTimeout(() => toast.classList.add('show'), 10);
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 400);
    }, 4000);
}

async function copyText(text, label) {
    try {
        await navigator.clipboard.writeText(text);
        showToast(`${label} copiado: ${text}`, 'success');
    } catch (err) { showToast('Erro ao copiar valor', 'error'); }
}

function getExplanation(status, side) {
    const isShort = side.toLowerCase() === 'short';
    const mapping = {
        'TUDO CERTO: SEGURAR': isShort ? 'Tudo sob controle. O preço deve continuar baixando.' : 'Tudo sob controle. O preço deve continuar subindo.',
        'PERIGOSO: SAIR AGORA': isShort ? 'Atenção! O preço deve subir agora. O risco de prejuízo ficou muito alto, melhor sair.' : 'Atenção! O preço deve cair agora. O risco de prejuízo ficou muito alto, melhor sair.',
        'LUCRO NO BOLSO?': isShort ? 'O preço já baixou bastante. Ele pode voltar a subir a qualquer hora, garanta seu lucro.' : 'O preço já subiu bastante. Ele pode voltar a cair a qualquer hora, garanta seu lucro.',
        'CALMA: VAI VOLTAR': isShort ? 'O preço subiu demais e está "cansado". Ele deve voltar a baixar em breve, espere.' : 'O preço caiu demais e está "cansado". Ele deve voltar a subir em breve, espere.',
        'PROTEÇÃO: NO ZERO': 'Você não perde mais nada aqui. O preço voltou para onde você entrou, proteja seu capital.'
    };
    return mapping[status] || 'Análise tática em processamento...';
}

function togglePin(sinalStr) {
    const sig = JSON.parse(decodeURIComponent(sinalStr));
    const index = pinnedSignals.findIndex(p => p.symbol === sig.symbol);
    if (index === -1) {
        pinnedSignals.push(sig);
        showToast(`${sig.symbol} fixado!`, 'success');
    } else {
        pinnedSignals.splice(index, 1);
        showToast(`${sig.symbol} removido!`, 'info');
    }
    localStorage.setItem('sentinel_pins', JSON.stringify(pinnedSignals));
    renderPinnedSignals();
    updateScanner(true); 
}

function renderPinnedSignals() {
    const section = document.getElementById('pinned-section');
    const tbody = document.getElementById('pinned-body');
    if (!section || !tbody) return;
    if (pinnedSignals.length === 0) { section.classList.add('hidden'); return; }
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
            <td>${sig.timestamp || '--:--:--'}</td>
            <td onclick="openChart('${sig.symbol}')" style="cursor: pointer;"><strong>${sig.symbol}</strong><br><small>${sig.bb_upper}</small></td>
            <td class="copyable" onclick="copyText('${sig.price}', 'Preço')">${sig.price}</td>
            <td class="copyable" style="color:var(--neon-blue)">${sig.tp}</td>
            <td class="copyable" style="color:var(--loss-red)">${sig.sl}</td>
            <td style="text-align:center;">${sig.score}/10</td>
            <td style="text-align:center;"><span class="season-badge ${seasonClass}">${seasonEmoji} ${seasonScore}</span></td>
            <td><span class="status-tag ${statusClass}">${sig.status}</span></td>
            <td><button class="btn-pin active" onclick="togglePin('${encodeURIComponent(JSON.stringify(sig))}')">⭐</button> <button class="btn-action btn-entry" onclick="handleEntry('${sig.symbol}', '${sig.price}', '${side}', '${sig.tp}', '${sig.sl}')">ENTRAR</button> <button class="btn-action pulse-blue" onclick="openAnalysis('${sig.symbol}')">⚡</button></td>
        `;
        tbody.appendChild(row);
    });
}

function openChart(symbol) {
    const modal = document.getElementById('chart-modal');
    document.getElementById('modal-symbol').innerText = symbol;
    modal.style.display = 'flex';
    new TradingView.widget({
        "autosize": true, "symbol": `BINANCE:${symbol}`, "interval": "5", "theme": "dark", "style": "1", "locale": "br", "container_id": "tradingview-container",
        "studies": ["MAExp@tv-basicstudies","MAExp@tv-basicstudies","MAExp@tv-basicstudies","BollingerBands@tv-basicstudies","RSI@tv-basicstudies"]
    });
}

function closeModal() {
    document.getElementById('chart-modal').style.display = 'none';
    document.getElementById('tradingview-container').innerHTML = '';
}

document.getElementById('close-modal').onclick = closeModal;
document.getElementById('close-order-modal').onclick = closeOrderModal;
window.onclick = (e) => { 
    if (e.target == document.getElementById('chart-modal')) closeModal(); 
    if (e.target == document.getElementById('order-modal')) closeOrderModal();
};

async function handleEntry(symbol, price, side, tp, sl) {
    const isShort = side.toLowerCase() === 'short';
    const finalTp = tp || (isShort ? price * 0.95 : price * 1.05);
    const finalSl = sl || (isShort ? price * 1.10 : price * 0.90);
    activeOrderData = { symbol, price, side: side.toUpperCase(), tp: parseFloat(finalTp).toFixed(6), sl: parseFloat(finalSl).toFixed(6) };
    document.getElementById('order-symbol').innerText = symbol;
    document.getElementById('order-side').innerText = activeOrderData.side;
    document.getElementById('order-entry').innerText = price;
    document.getElementById('order-tp').innerText = activeOrderData.tp;
    document.getElementById('order-sl').innerText = activeOrderData.sl;
    document.getElementById('order-modal').style.display = 'flex';
}

function closeOrderModal() {
    document.getElementById('order-modal').style.display = 'none';
    activeOrderData = null;
}

document.getElementById('btn-confirm-order').onclick = async function() {
    if (!activeOrderData) return;
    const margin = document.getElementById('order-margin').value;
    const isScalp = document.getElementById('order-is-scalp')?.checked || false;
    this.disabled = true;
    this.innerText = 'EXECUTANDO...';
    
    try {
        const response = await fetch(`${API_URL}/bingx/order`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ...activeOrderData, margin: parseFloat(margin), is_scalp: isScalp })
        });
        const result = await response.json();
        if (result.status === 'success') {
            showToast('ORDEM EXECUTADA!', 'success');
            closeOrderModal();
            updatePortfolio();
            updateBots();
        } else {
            showToast(`ERRO: ${result.message}`, 'error');
        }
    } catch (err) {
        showToast('Erro ao conectar com o servidor', 'error');
    } finally {
        this.disabled = false;
        this.innerText = 'EXECUTAR NA BINGX';
    }
};

async function openAnalysis(symbol) {
    const drawer = document.getElementById('analysis-drawer');
    const grid = document.getElementById('analysis-grid');
    document.getElementById('drawer-symbol').innerText = `RAIO-X: ${symbol}`;
    grid.innerHTML = '<div style="grid-column: 1/-1; text-align: center;">Analisando...</div>';
    drawer.classList.add('open');
    try {
        const response = await fetch(`${API_URL}/analyze/${symbol}`);
        const data = await response.json();
        const btcClass = data.btc_status === 'ALTA' ? 'btc-alta' : (data.btc_status === 'BAIXA' ? 'btc-baixa' : 'btc-neutro');
        document.getElementById('drawer-symbol').innerHTML = `${symbol} <span class="btc-badge ${btcClass}">BTC: ${data.btc_status}</span>`;
        grid.innerHTML = '';
        ['1m', '5m', '15m', '30m', '1h', '4h'].forEach(tf => {
            const info = data.timeframes[tf]; if (!info) return;
            const block = document.createElement('div');
            block.className = 'tf-block';
            const color = info.trend === 'ALTA' ? 'var(--win-green)' : (info.trend === 'BAIXA' ? 'var(--loss-red)' : 'rgba(255,255,255,0.4)');
            block.innerHTML = `<span class="tf-label">${tf}</span><span style="color:${color}">${info.trend}</span><small>RSI:${info.rsi}</small><span class="vol-badge">${info.volume}</span>`;
            grid.appendChild(block);
        });
        document.getElementById('verdict-value').innerText = data.verdict;
        document.getElementById('verdict-reason').innerText = data.reason;
        document.getElementById('conf-fill').style.width = `${data.confidence || 0}%`;
        loadSeasonality(symbol);
        loadProjection(symbol);
    } catch (err) { grid.innerHTML = `Erro: ${err.message}`; }
}

async function loadProjection(symbol) {
    const container = document.getElementById('projection-container');
    try {
        const res = await fetch(`${API_URL}/projection/${symbol}`);
        const data = await res.json();
        
        if (data.error) throw new Error(data.error);

        container.innerHTML = `
            <div class="projection-header">
                <span>ABERTURA: <strong>${data.open}</strong></span>
                <span>ATR(14): <strong>${data.atr}</strong></span>
            </div>
            <div class="targets-wrapper">
                <div class="target-side bull">
                    <div class="side-label">ALVOS DE ALTA (BULL)</div>
                    ${data.bull_targets.map(t => `
                        <div class="target-row ${data.current > t.val ? 'hit' : ''}">
                            <span class="t-mult">${t.multiple}x</span>
                            <span class="t-val">${t.val}</span>
                            <span class="t-prob">${t.prob}%</span>
                        </div>
                    `).join('')}
                </div>
                <div class="target-side bear">
                    <div class="side-label">ALVOS DE BAIXA (BEAR)</div>
                    ${data.bear_targets.map(t => `
                        <div class="target-row ${data.current < t.val ? 'hit' : ''}">
                            <span class="t-mult">${t.multiple}x</span>
                            <span class="t-val">${t.val}</span>
                            <span class="t-prob">${t.prob}%</span>
                        </div>
                    `).join('')}
                </div>
            </div>
            <div class="projection-footer">
                * Probabilidades baseadas em desvios de volatilidade e bias do dia.
            </div>
        `;
    } catch (err) {
        container.innerHTML = `<div style="color:var(--loss-red); font-size: 0.7rem; text-align: center;">Erro: ${err.message}</div>`;
    }
}

async function updatePortfolio() {
    try {
        const res = await fetch(`${API_URL}/monitor`);
        const data = await res.json();
        const tbody = document.getElementById('portfolio-body');
        tbody.innerHTML = '';
        const positions = data.positions || [];
        positions.forEach(pos => {
            const pnlValue = parseFloat(pos.pnl) || 0;
            const row = document.createElement('tr');
            row.innerHTML = `<td><strong>${pos.symbol}</strong></td><td>${pos.opened_at}</td><td>${pos.entry}/${pos.current}</td><td>${pos.ttt}</td><td><span class="${pnlValue>=0?'green':'red'}">${pnlValue.toFixed(2)}%</span></td><td>${pos.tp}/${pos.sl}</td><td>${pos.status}</td><td><button class="btn-action pulse-blue" onclick="openAnalysis('${pos.symbol}')">IA</button></td>`;
            tbody.appendChild(row);
        });
        document.getElementById('global-trades').innerText = positions.length;
        document.getElementById('global-pnl').innerText = `${(data.total_pnl || 0).toFixed(2)}%`;
        document.getElementById('global-trend').innerText = data.macro || 'NEUTRO';
    } catch (err) {}
}

let scanAbortController = null;
let scannerSortOrder = 'desc';

async function updateScanner(isSilent = false) {
    try {
        const endpoint = isSilent ? 'latest_signals' : 'scanner';
        const options = scanAbortController ? { signal: scanAbortController.signal } : {};
        const response = await fetch(`${API_URL}/${endpoint}`, options);
        let signals = await response.json();
        if (isSilent && signals.length === 0) return;
        signals.sort((a,b) => scannerSortOrder === 'desc' ? b.score - a.score : a.score - b.score);
        const tbody = document.getElementById('scanner-body');
        if (!isSilent) tbody.innerHTML = '';
        signals.forEach(sig => {
            const side = sig.side || (sig.status.includes('SHORT') || sig.status.includes('LARANJA') ? 'Short' : 'Long');
            const statusClass = side === 'Short' ? 'alert-short' : (sig.status.includes('VETO') ? 'btc-neutro' : 'maduro');
            const isPinned = pinnedSignals.some(p => p.symbol === sig.symbol);
            const seasonScore = sig.season_score !== undefined ? sig.season_score : '--';
            const seasonClass = sig.season_trend === 'ALTA' ? 'season-up' : (sig.season_trend === 'BAIXA' ? 'season-down' : '');
            const seasonEmoji = sig.season_trend === 'ALTA' ? '📈' : (sig.season_trend === 'BAIXA' ? '📉' : '⚖️');
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${sig.timestamp}</td>
                <td onclick="openChart('${sig.symbol}')"><strong>${sig.symbol}</strong><br><small>${sig.bb_upper}</small></td>
                <td class="copyable" onclick="copyText('${sig.price}','Preço')">${sig.price}</td>
                <td style="color:var(--neon-blue)">${sig.tp}</td>
                <td style="color:var(--loss-red)">${sig.sl}</td>
                <td style="text-align:center">${sig.score}/10</td>
                <td style="text-align:center"><span class="season-badge ${seasonClass}">${seasonEmoji} ${seasonScore}</span></td>
                <td><span class="status-tag ${statusClass}">${sig.status}</span></td>
                <td><button class="btn-pin ${isPinned?'active':''}" onclick="togglePin('${encodeURIComponent(JSON.stringify(sig))}')">⭐</button> <button class="btn-action btn-entry" onclick="handleEntry('${sig.symbol}','${sig.price}','${side}','${sig.tp}','${sig.sl}')">ENTRAR</button> <button class="btn-action pulse-blue" onclick="openAnalysis('${sig.symbol}')">⚡</button></td>
            `;
            const existing = Array.from(tbody.children).find(r => r.cells[1].innerText.includes(sig.symbol));
            if (existing) existing.replaceWith(row); else tbody.appendChild(row);
        });
        document.getElementById('log-display').innerText = `[SCANNER] Atualizado em ${new Date().toLocaleTimeString()}`;
    } catch (err) { if (err.name !== 'AbortError' && !isSilent) showToast('Erro no scanner', 'error'); }
}

async function manualScan() {
    const btnScan = document.getElementById('btn-scan');
    const btnStop = document.getElementById('btn-stop');
    const progressContainer = document.getElementById('progress-container');
    const progressBar = document.getElementById('progress-bar');
    if (scanAbortController) scanAbortController.abort();
    scanAbortController = new AbortController();
    btnScan.classList.add('hidden');
    btnStop.classList.remove('hidden');
    progressContainer.classList.remove('progress-hidden');
    progressBar.style.width = '0%';
    const pollInterval = setInterval(() => updateScanner(true), 3000);
    let progress = 0;
    const progressInterval = setInterval(() => { if (progress < 95) { progress += (95 - progress) * 0.05; progressBar.style.width = `${progress}%`; } }, 1000);
    try {
        await updateScanner(false);
        progressBar.style.width = '100%';
        showToast('Scanner finalizado!', 'success');
    } catch (err) { if (err.name === 'AbortError') showToast('Scanner parado.', 'info'); }
    finally { clearInterval(pollInterval); clearInterval(progressInterval); stopScan(); }
}

function stopScan() {
    if (scanAbortController) { scanAbortController.abort(); scanAbortController = null; }
    document.getElementById('btn-scan').classList.remove('hidden');
    document.getElementById('btn-stop').classList.add('hidden');
    setTimeout(() => document.getElementById('progress-container').classList.add('progress-hidden'), 1500);
}

async function loadSeasonality(symbol) {
    const infoText = document.getElementById('season-info-text');
    try {
        const res = await fetch(`${API_URL}/seasonality/${symbol}`);
        const data = await res.json();
        drawSeasonalChart(data.projection);
        if (infoText) infoText.innerHTML = `Estatística: <span class="${data.trend==='ALTA'?'green':'red'}"><strong>${data.trend}</strong></span> (Score:${data.score})`;
    } catch (err) {}
}

function drawSeasonalChart(projection) {
    const canvas = document.getElementById('seasonal-canvas'); if (!canvas) return;
    const ctx = canvas.getContext('2d'); const width = canvas.width = canvas.parentElement.clientWidth; const height = canvas.height = canvas.parentElement.clientHeight;
    ctx.clearRect(0,0,width,height);
    
    // Na miniatura do Raio-X, usamos a amplitude total para preencher o espaço
    const v = projection.map(p => p.multiplier); 
    const min = Math.min(...v); 
    const max = Math.max(...v); 
    const r = max - min || 1;
    
    ctx.beginPath(); ctx.lineWidth = 2; ctx.strokeStyle = '#FF8C00';
    projection.forEach((p, i) => {
        const x = (i / (projection.length - 1)) * width;
        const y = height - 10 - ((p.multiplier - min) / r) * (height - 20);
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        if (i === 15) { 
            ctx.save(); ctx.setLineDash([5,5]); ctx.strokeStyle='rgba(255,255,255,0.3)'; 
            ctx.beginPath(); ctx.moveTo(x,0); ctx.lineTo(x,height); ctx.stroke(); ctx.restore(); 
        }
    });
    ctx.stroke();
}

document.getElementById('btn-toggle-season-chart').onclick = async function() {
    const symbol = document.getElementById('modal-symbol').innerText;
    const canvas = document.getElementById('seasonal-overlay-canvas');
    const statsBox = document.getElementById('seasonality-stats-box');
    const modeSelector = document.getElementById('projection-mode-selector');
    
    if (canvas.style.display === 'block') { 
        canvas.style.display = 'none'; 
        if (statsBox) statsBox.classList.add('hidden');
        if (modeSelector) modeSelector.classList.add('hidden');
        this.innerText = '🗺️ ATIVAR PROJEÇÕES'; 
        return; 
    }
    
    this.innerText = '⌛...';
    try {
        const [resSea, resPrice, resProj] = await Promise.all([
            fetch(`${API_URL}/seasonality/${symbol}`),
            fetch(`${API_URL}/analyze/${symbol}`),
            fetch(`${API_URL}/projection/${symbol}`)
        ]);
        
        if (!resSea.ok || !resPrice.ok || !resProj.ok) {
            throw new Error(`Servidor respondeu com erro (${resSea.status}/${resPrice.status}/${resProj.status})`);
        }
        
        const dataSea = await resSea.json();
        const priceData = await resPrice.json();
        const projectionData = await resProj.json();

        globalProjectionData.macro = dataSea;
        globalProjectionData.local = projectionData;
        globalProjectionData.priceInfo = priceData;
        
        canvas.style.display = 'block';
        if (modeSelector) modeSelector.classList.remove('hidden');
        
        updateProjectionView();
        this.innerText = '🗺️ DESATIVAR';
    } catch (err) { 
        console.error(err);
        showToast('Erro ao carregar projeções', 'error'); 
        this.innerText = '🗺️ TENTAR NOVAMENTE';
    }
};

function updateProjectionView() {
    const canvas = document.getElementById('seasonal-overlay-canvas');
    const statsBox = document.getElementById('seasonality-stats-box');
    const headerText = document.getElementById('stats-header-text');
    
    if (!globalProjectionData.macro || !globalProjectionData.local) return;

    if (currentProjectionMode === 'macro') {
        headerText.innerText = "ESTRADA (SAZONALIDADE)";
        document.getElementById('stats-conf').innerText = `${globalProjectionData.priceInfo.confidence}%`;
        document.getElementById('stats-roi').innerText = `${((globalProjectionData.macro.projection[globalProjectionData.macro.projection.length-1].multiplier - 1) * 100).toFixed(2)}%`;
        document.getElementById('stats-trend').innerText = globalProjectionData.macro.trend;
        document.getElementById('stats-status').innerText = globalProjectionData.macro.score > 0 ? "MARÉ ALTA" : "MARÉ BAIXA";
        document.getElementById('stats-status').style.color = globalProjectionData.macro.score > 0 ? 'var(--win-green)' : 'var(--loss-red)';
        
        drawSeasonalOnOverlay(globalProjectionData.macro.projection);
    } else {
        headerText.innerText = "TRÁFEGO (TECNICO/ATR)";
        const p = globalProjectionData.local;
        document.getElementById('stats-conf').innerText = `${p.bias}`;
        document.getElementById('stats-roi').innerText = `ATR: ${p.atr}`;
        document.getElementById('stats-trend').innerText = p.bias === 'BULL' ? 'LONG' : 'SHORT';
        document.getElementById('stats-status').innerText = "CALCULADO";
        document.getElementById('stats-status').style.color = 'var(--neon-blue)';
        
        drawTradePathOnOverlay(p.trade_path, p.bias);
    }
}

document.getElementById('btn-mode-macro').onclick = () => {
    currentProjectionMode = 'macro';
    document.getElementById('btn-mode-macro').classList.add('active');
    document.getElementById('btn-mode-local').classList.remove('active');
    updateProjectionView();
};

document.getElementById('btn-mode-local').onclick = () => {
    currentProjectionMode = 'local';
    document.getElementById('btn-mode-local').classList.add('active');
    document.getElementById('btn-mode-macro').classList.remove('active');
    updateProjectionView();
};

function drawSeasonalOnOverlay(p) {
    const c = document.getElementById('seasonal-overlay-canvas'); 
    const ctx = c.getContext('2d');
    const w = c.width = c.parentElement.clientWidth; 
    const h = c.height = c.parentElement.clientHeight;
    ctx.clearRect(0,0,w,h);

    const m = p.map(x => x.multiplier);
    const minM = Math.min(...m);
    const maxM = Math.max(...m);
    const rangeM = (maxM - minM) || 0.001;

    // Estilo Ghost Path
    ctx.beginPath(); 
    ctx.lineWidth = 5; 
    ctx.strokeStyle = 'rgba(255, 140, 0, 0.45)'; 
    ctx.setLineDash([12, 6]);

    p.forEach((x, i) => {
        // X: Posicionamos o ponto 15 (AGORA) em 60% da largura da tela (onde as velas costumam terminar)
        let xCoord;
        const nowX = w * 0.6;
        if (i <= 15) {
            xCoord = (i / 15) * nowX;
        } else {
            xCoord = nowX + ((i - 15) / (p.length - 1 - 15)) * (w - nowX);
        }
        
        // Y: Centralizado verticalmente h*0.45 para alinhar com o corpo do TradingView
        const yOffset = (x.multiplier - 1.0) / rangeM * (h * 0.4);
        const yCoord = (h * 0.45) - yOffset;
        
        if (i === 0) ctx.moveTo(xCoord, yCoord); 
        else ctx.lineTo(xCoord, yCoord);

        // Marca o "Hoje" (Agora) com uma linha de referência
        if (i === 15) {
            ctx.save();
            ctx.setLineDash([]);
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.3)';
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.moveTo(xCoord, 0); ctx.lineTo(xCoord, h); ctx.stroke();
            
            // Texto indicativo
            ctx.fillStyle = 'rgba(255, 255, 255, 0.8)';
            ctx.font = 'bold 12px Orbitron, sans-serif';
            ctx.fillText("AGORA", xCoord + 5, 20);
            ctx.restore();
        }
    });
    ctx.stroke();

    // Efeito de brilho neon
    ctx.shadowBlur = 15;
    ctx.shadowColor = 'rgba(255, 140, 0, 0.7)';
    
    // Adiciona labels de ROI projetado no final da linha
    const lastP = p[p.length - 1];
    const finalROI = ((lastP.multiplier - 1) * 100).toFixed(2);
    const lastX = w - 160;
    const lastY = (h * 0.45) - ((lastP.multiplier - 1.0) / rangeM * (h * 0.4));
    
    ctx.shadowBlur = 0;
    ctx.fillStyle = finalROI >= 0 ? 'var(--win-green)' : 'var(--loss-red)';
    ctx.font = 'bold 12px Orbitron, sans-serif';
    ctx.fillText(`PROJ. 30D (MACRO): ${finalROI}%`, lastX, lastY - 10);
}

function drawTradePathOnOverlay(path, bias) {
    const c = document.getElementById('seasonal-overlay-canvas'); 
    const ctx = c.getContext('2d');
    const w = c.width = c.parentElement.clientWidth; 
    const h = c.height = c.parentElement.clientHeight;
    ctx.clearRect(0,0,w,h);

    const values = path.map(x => x.val);
    const minV = Math.min(...values);
    const maxV = Math.max(...values);
    const rangeV = (maxV - minV) || 1;

    ctx.beginPath(); 
    ctx.lineWidth = 4; 
    ctx.strokeStyle = bias === 'BULL' ? '#00eaff' : '#ff4d00'; // Azul Neon ou Laranja Neon
    ctx.setLineDash([10, 5]);

    const nowX = w * 0.6;
    path.forEach((p, i) => {
        const x = nowX + (i / (path.length - 1)) * (w - nowX - 20);
        // Centralizado no h*0.45 (preço atual) e variando proporcionalmente ao ATR
        const y = (h * 0.45) - ((p.val - path[0].val) / rangeV) * (h * 0.3);
        
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);

        if (i === 0) {
            // Marca o Ponto de Entrada (Agora)
            ctx.save();
            ctx.setLineDash([]);
            ctx.fillStyle = '#fff';
            ctx.beginPath(); ctx.arc(x, y, 5, 0, Math.PI*2); ctx.fill();
            ctx.font = 'bold 10px Inter';
            ctx.fillText("ENTRADA", x + 10, y + 5);
            ctx.restore();
        }
    });
    ctx.stroke();

    // Brilho Neon
    ctx.shadowBlur = 20;
    ctx.shadowColor = bias === 'BULL' ? 'rgba(0, 234, 255, 0.6)' : 'rgba(255, 77, 0, 0.6)';
    ctx.stroke();
}

updateTime();
setInterval(() => { updatePortfolio(); updateScanner(true); updateBots(); }, 30000);
function updateTime() { document.getElementById('time-display').innerText = new Date().toLocaleTimeString(); }
setInterval(updateTime, 1000);

// --- SCALP BOTS ---
async function updateBots() {
    try {
        const res = await fetch(`${API_URL}/bot/status`);
        const bots = await res.json();
        const section = document.getElementById('scalp-bots-section');
        const tbody = document.getElementById('scalp-bots-body');
        
        if (bots.length === 0) {
            if(section) section.classList.add('hidden');
            return;
        }
        
        if(section) section.classList.remove('hidden');
        if(tbody) {
            tbody.innerHTML = '';
            bots.forEach(b => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td><strong>${b.symbol}</strong><br><small style="color:var(--text-dim)">TP: ${(b.tp_pct*100).toFixed(1)}% | SL: ${(b.sl_pct*100).toFixed(1)}%</small></td>
                    <td><span class="status-tag ${b.side === 'SHORT' ? 'alert-short' : 'maduro'}">${b.side}</span></td>
                    <td>${b.margin} USDT</td>
                    <td>${b.status === 'OPEN' ? '<span style="color:var(--win-green); font-weight: bold;">EM OPERAÇÃO</span>' : '<span style="color:var(--neon-orange); font-weight: bold;">AGUARDANDO ALVO</span>'}</td>
                    <td><button class="btn-action pulse-red" style="padding: 6px 12px; background:var(--loss-red);" onclick="stopBot('${b.id}')">🛑 PARAR BOT</button></td>
                `;
                tbody.appendChild(row);
            });
        }
    } catch (err) {
        console.error("Erro ao atualizar bots:", err);
    }
}

async function stopBot(botId) {
    if(!confirm("Deseja realmente parar este robô automático?\\n\\nNOTA: As posições OBTIDAS na BingX NÃO SERÃO FECHADAS, apenas o LOOP de re-entradas será interrompido.")) return;
    try {
        const res = await fetch(`${API_URL}/bot/stop/${botId}`, {method: 'POST'});
        const data = await res.json();
        if(data.status === 'success') {
            showToast(data.message, 'success');
            updateBots();
        }
    } catch (e) {
        showToast("Erro ao parar bot", "error");
    }
}

// Inicializa no carregamento
setTimeout(() => updateBots(), 2000);
