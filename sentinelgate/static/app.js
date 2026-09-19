// SentinelGate Modern Frontend Logic

const API_BASE = '/api';

// --- Initialization & Polling ---
document.addEventListener('DOMContentLoaded', () => {
    checkStatus();
    loadStats();
    loadPolicies();

    // Auto resize textarea
    const tx = document.getElementById('prompt-input');
    tx.setAttribute('style', 'height:' + (tx.scrollHeight) + 'px;overflow-y:hidden;');
    tx.addEventListener("input", OnInput, false);

    // Chat form submit
    document.getElementById('chat-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const input = document.getElementById('prompt-input');
        const text = input.value.trim();
        if (!text) return;

        input.value = '';
        input.style.height = '54px';

        appendUserMessage(text);
        await sendChatRequest(text);
        loadStats(); // Update metrics after request
    });

    // Policy form submit
    document.getElementById('new-policy-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const input = document.getElementById('policy-input');
        const text = input.value.trim();
        if(!text) return;

        const btn = e.target.querySelector('button');
        btn.disabled = true;
        btn.textContent = 'Creating...';

        try {
            await fetch(`${API_BASE}/policies`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({natural_language: text})
            });
            input.value = '';
            document.getElementById('new-policy-form').classList.add('hidden');
            loadPolicies();
        } catch(e) {
            console.error(e);
            alert("Failed to create policy");
        } finally {
            btn.disabled = false;
            btn.textContent = 'Create';
        }
    });
});

function OnInput() {
    this.style.height = 'auto';
    this.style.height = (this.scrollHeight) + 'px';
}

// --- Tabs ---
function switchTab(tabId) {
    // Hide all
    document.querySelectorAll('.view-panel').forEach(p => {
        p.classList.add('hidden');
        p.classList.remove('opacity-100');
        p.classList.add('opacity-0');
    });
    document.querySelectorAll('.tab-btn').forEach(b => {
        b.classList.remove('text-sg-cyan', 'border-sg-cyan');
        b.classList.add('text-slate-400', 'border-transparent');
    });

    // Show active
    const view = document.getElementById(`view-${tabId}`);
    view.classList.remove('hidden');
    // slight delay for animation
    setTimeout(() => {
        view.classList.remove('opacity-0');
        view.classList.add('opacity-100');
    }, 50);

    const btn = document.getElementById(`tab-${tabId}`);
    btn.classList.remove('text-slate-400', 'border-transparent');
    btn.classList.add('text-sg-cyan', 'border-sg-cyan');

    if (tabId === 'audit') loadLogs();
    if (tabId === 'policies') loadPolicies();
}

// --- API Calls ---

async function checkStatus() {
    try {
        const res = await fetch(`${API_BASE}/status`);
        const data = await res.json();

        const dot = document.getElementById('status-dot');
        const text = document.getElementById('status-text');

        dot.classList.remove('animate-pulse', 'bg-sg-yellow', 'bg-sg-red', 'bg-sg-green');

        if (data.demo_mode) {
            dot.classList.add('bg-sg-yellow');
            text.textContent = 'Offline Demo';
            text.classList.add('text-sg-yellow');
        } else if (data.lobster_running) {
            dot.classList.add('bg-sg-green');
            text.textContent = 'Protected';
            text.classList.add('text-sg-green');
        } else {
            dot.classList.add('bg-sg-red');
            text.textContent = 'Fallback Mode';
            text.classList.add('text-sg-red');
        }
    } catch(e) {
        console.error("Status check failed", e);
    }
}

async function loadStats() {
    try {
        const res = await fetch(`${API_BASE}/stats`);
        const data = await res.json();
        document.getElementById('metric-policies').textContent = data.active_policies;
        document.getElementById('metric-requests').textContent = data.stats.total;
        document.getElementById('metric-blocked').textContent = data.blocked_today;
    } catch(e) {
        console.error("Stats load failed", e);
    }
}

async function clearAuditLog() {
    if(!confirm("Are you sure you want to delete all audit logs?")) return;
    try {
        await fetch(`${API_BASE}/logs/clear`, {method: 'POST'});
        loadStats();
        if(!document.getElementById('view-audit').classList.contains('hidden')) {
            loadLogs();
        }
        document.getElementById('chat-history').innerHTML = `
        <div class="flex justify-center mt-10">
            <span class="text-xs text-slate-500 uppercase tracking-widest font-bold bg-white/5 px-4 py-1 rounded-full border border-white/10">Session Reset</span>
        </div>`;
    } catch(e) {
        console.error(e);
    }
}

async function loadPolicies() {
    try {
        const res = await fetch(`${API_BASE}/policies`);
        const policies = await res.json();

        const tbody = document.getElementById('policies-table');
        tbody.innerHTML = '';

        policies.forEach(p => {
            const tr = document.createElement('tr');
            const keywords = p.enforcement_keywords.map(k => `<span class="inline-block bg-sg-cyan/10 text-sg-cyan border border-sg-cyan/20 px-2 py-0.5 rounded text-xs mr-1 mb-1">${k}</span>`).join('');

            tr.innerHTML = `
                <td class="px-6 py-4">
                    <button onclick="togglePolicy('${p.id}', ${!p.active})" class="w-10 h-5 rounded-full relative transition-colors ${p.active ? 'bg-sg-green' : 'bg-slate-700'}">
                        <span class="absolute top-0.5 left-0.5 bg-white w-4 h-4 rounded-full transition-transform ${p.active ? 'translate-x-5' : ''}"></span>
                    </button>
                </td>
                <td class="px-6 py-4 whitespace-normal">
                    <p class="font-medium text-white">${p.name || 'Custom Policy'}</p>
                    <p class="text-xs text-slate-400 mt-1">${p.natural_language}</p>
                </td>
                <td class="px-6 py-4 whitespace-normal max-w-xs">${keywords || '<span class="text-slate-500 italic text-xs">No keywords extracted</span>'}</td>
                <td class="px-6 py-4 text-right">
                    <button onclick="deletePolicy('${p.id}')" class="text-slate-500 hover:text-sg-red transition-colors"><span class="material-icons text-sm">delete</span></button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch(e) {
        console.error(e);
    }
}

async function togglePolicy(id, newState) {
    await fetch(`${API_BASE}/policies/${id}`, {
        method: 'PATCH',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({active: newState})
    });
    loadPolicies();
    loadStats();
}

async function deletePolicy(id) {
    if(!confirm("Delete this policy?")) return;
    await fetch(`${API_BASE}/policies/${id}`, {method: 'DELETE'});
    loadPolicies();
    loadStats();
}

async function loadLogs() {
    try {
        const res = await fetch(`${API_BASE}/logs?limit=50`);
        const logs = await res.json();

        const tbody = document.getElementById('logs-table');
        tbody.innerHTML = '';

        logs.forEach(l => {
            const tr = document.createElement('tr');
            const isBlock = l.decision === 'BLOCK';

            const date = new Date(l.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit'});

            let riskClass = 'text-sg-green bg-sg-green/10 border-sg-green/30';
            if (l.risk_score >= 0.7) riskClass = 'text-sg-red bg-sg-red/10 border-sg-red/30 sg-glow-red';
            else if (l.risk_score >= 0.4) riskClass = 'text-sg-yellow bg-sg-yellow/10 border-sg-yellow/30';

            tr.innerHTML = `
                <td class="px-6 py-4 text-slate-400 text-xs font-mono">${date}</td>
                <td class="px-6 py-4">
                    <span class="text-xs font-bold px-2 py-1 rounded border ${isBlock ? 'text-sg-red border-sg-red/50 bg-sg-red/10' : 'text-sg-green border-sg-green/50 bg-sg-green/10'}">${l.decision}</span>
                </td>
                <td class="px-6 py-4">
                    <span class="text-xs font-mono font-bold px-2 py-1 rounded border ${riskClass}">${l.risk_score.toFixed(2)}</span>
                </td>
                <td class="px-6 py-4">
                    <span class="text-xs text-slate-300 bg-white/5 border border-white/10 px-2 py-1 rounded">${l.intent_label.replace(/_/g, ' ')}</span>
                </td>
                <td class="px-6 py-4 truncate max-w-md text-slate-400 text-xs">${l.prompt_preview}</td>
            `;
            tbody.appendChild(tr);
        });
    } catch(e) {
        console.error(e);
    }
}

// --- Chat UI ---
function appendUserMessage(text) {
    const history = document.getElementById('chat-history');
    const el = document.createElement('div');
    el.className = 'flex justify-end';
    el.innerHTML = `
        <div class="max-w-2xl bg-gradient-to-br from-blue-900 to-blue-700 border border-blue-500/30 rounded-2xl rounded-tr-sm p-4 text-sm shadow-xl text-white">
            ${escapeHtml(text)}
        </div>
    `;
    history.appendChild(el);
    history.scrollTop = history.scrollHeight;
}

function appendSystemLoading() {
    const history = document.getElementById('chat-history');
    const id = 'loading-' + Date.now();
    const el = document.createElement('div');
    el.id = id;
    el.className = 'flex justify-start';
    el.innerHTML = `
        <div class="max-w-2xl bg-white/5 border border-white/10 rounded-2xl rounded-tl-sm p-4 text-sm shadow-xl flex items-center space-x-3 text-slate-400">
            <div class="w-3 h-3 border-2 border-sg-cyan border-t-transparent rounded-full animate-spin"></div>
            <span>Inspecting payload...</span>
        </div>
    `;
    history.appendChild(el);
    history.scrollTop = history.scrollHeight;
    return id;
}

async function sendChatRequest(text) {
    const loadId = appendSystemLoading();

    try {
        const res = await fetch(`${API_BASE}/chat`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({prompt: text})
        });
        const data = await res.json();

        document.getElementById(loadId).remove();
        appendResultCard(data);
    } catch(e) {
        document.getElementById(loadId).remove();
        console.error(e);
    }
}

function appendResultCard(data) {
    const history = document.getElementById('chat-history');
    const el = document.createElement('div');
    el.className = 'flex justify-start w-full';

    const isBlock = data.decision === 'BLOCK';
    const accentColor = isBlock ? 'sg-red' : 'sg-green';
    const bgClass = isBlock ? 'bg-sg-red/5 border-sg-red/30' : 'bg-sg-green/5 border-sg-green/30';

    let reasonHtml = '';
    if (isBlock) {
        reasonHtml = `
            <div class="mt-4 p-3 bg-black/40 rounded-lg border border-sg-red/20 text-xs">
                <span class="font-bold text-sg-red block mb-1">Block Reason:</span>
                <span class="text-slate-300">${escapeHtml(data.block_reason)}</span>
            </div>
        `;
    }

    let responseHtml = '';
    if (!isBlock && data.response) {
        responseHtml = `
            <div class="mt-4 p-4 bg-black/40 rounded-lg border border-white/10 text-sm text-slate-300">
                ${escapeHtml(data.response).replace(/\n/g, '<br>')}
            </div>
        `;
    }

    let citationsHtml = '';
    if (data.compliance_citation) {
        citationsHtml = `<span class="inline-block bg-sg-red/10 text-sg-red border border-sg-red/30 px-2 py-1 rounded text-[0.65rem] font-bold uppercase tracking-wider ml-2"><span class="material-icons text-[10px] mr-1 align-middle">gavel</span>${data.compliance_citation}</span>`;
    }

    el.innerHTML = `
        <div class="w-full max-w-3xl ${bgClass} border rounded-2xl p-5 shadow-xl transition-all">
            <div class="flex justify-between items-start mb-2">
                <div class="flex items-center space-x-3">
                    <span class="text-[0.7rem] font-bold px-2.5 py-1 rounded border border-${accentColor}/50 bg-${accentColor}/20 text-${accentColor} uppercase tracking-widest">${data.decision}</span>
                    <span class="text-xs text-slate-400 bg-black/30 px-2 py-1 rounded font-mono">${data.intent_label.replace(/_/g, ' ')}</span>
                    ${citationsHtml}
                </div>
                <div class="text-right">
                    <div class="text-3xl font-mono font-black text-${accentColor} leading-none ${isBlock ? 'sg-glow-red' : ''}">${data.risk_score.toFixed(2)}</div>
                    <div class="text-[0.6rem] text-slate-500 uppercase tracking-widest mt-1">Risk Score</div>
                </div>
            </div>

            <div class="text-xs text-slate-400 flex items-center space-x-4 mt-2 mb-2">
                <span class="flex items-center"><span class="material-icons text-[14px] mr-1">timer</span> ${data.processing_time_ms}ms total</span>
                <span class="flex items-center"><span class="material-icons text-[14px] mr-1">search</span> ${data.inspection_ms}ms inspect</span>
            </div>

            ${reasonHtml}
            ${responseHtml}
        </div>
    `;

    history.appendChild(el);
    history.scrollTop = history.scrollHeight;
}

function escapeHtml(unsafe) {
    return (unsafe || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}
