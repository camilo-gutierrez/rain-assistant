// ---------------------------------------------------------------------------
// Metrics Dashboard — usage analytics, cost tracking & rate limits
// ---------------------------------------------------------------------------

import { state, API, authHeaders, dom } from './app.js';

let _metricsData = null;
let _lastFetch = 0;
let _metricsOpen = false;
const CACHE_TTL = 60_000; // 1 minute

// ---------------------------------------------------------------------------
// Rate-limit & model helpers (status-bar compact indicator)
// ---------------------------------------------------------------------------

function parseModelName(model) {
    if (!model) return '?';
    const m = model.toLowerCase();
    if (m.includes('opus'))   return 'Opus';
    if (m.includes('sonnet')) return 'Sonnet';
    if (m.includes('haiku'))  return 'Haiku';
    return model.split('-').slice(1, 3).join(' ');
}

function updateRateBar(type, remaining, limit) {
    const barEl  = document.getElementById(`rate-bar-${type}`);
    const pctEl  = document.getElementById(`rate-pct-${type}`);
    if (!barEl || !pctEl || remaining == null || limit == null || limit === 0) return;
    const pct = Math.round((remaining / limit) * 100);
    barEl.style.width = pct + '%';
    barEl.className = 'rate-bar-fill ' + (pct > 50 ? 'healthy' : pct > 20 ? 'warning' : 'critical');
    pctEl.textContent = pct + '%';
}

export function updateModelInfo(modelStr) {
    state.currentModel = modelStr;
    const badge = document.getElementById('rate-model-badge');
    if (badge) {
        badge.textContent = parseModelName(modelStr);
        document.getElementById('rate-limit-indicator')?.classList.remove('hidden');
    }
}

export function updateRateLimits(limits) {
    state.rateLimits = limits;
    updateRateBar('requests', limits['requests-remaining'], limits['requests-limit']);
    updateRateBar('input',   limits['input-tokens-remaining'], limits['input-tokens-limit']);
    updateRateBar('output',  limits['output-tokens-remaining'], limits['output-tokens-limit']);
    document.getElementById('rate-limit-indicator')?.classList.remove('hidden');
}

export function updateUsageInfo(usage) {
    state.lastUsage = usage;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatUSD(val) {
    if (val == null || val === 0) return '$0.00';
    if (val < 0.01) return '$' + val.toFixed(4);
    return '$' + val.toFixed(2);
}

function formatDuration(ms) {
    if (ms == null || ms === 0) return '0s';
    const s = Math.floor(ms / 1000);
    if (s < 60) return s + 's';
    const m = Math.floor(s / 60);
    const rem = s % 60;
    return m + 'm ' + rem + 's';
}

function formatShortDate(dateStr) {
    // "2026-02-10" → "Feb 10"
    const parts = dateStr.split('-');
    const months = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
                    'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];
    return months[parseInt(parts[1], 10) - 1] + ' ' + parseInt(parts[2], 10);
}

function formatMonth(monthStr) {
    // "2026-02" → "Feb 2026"
    const parts = monthStr.split('-');
    const months = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
                    'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];
    return months[parseInt(parts[1], 10) - 1] + ' ' + parts[0];
}

// ---------------------------------------------------------------------------
// Fetch
// ---------------------------------------------------------------------------

async function fetchMetrics(forceRefresh = false) {
    const now = Date.now();
    if (!forceRefresh && _metricsData && (now - _lastFetch) < CACHE_TTL) {
        return _metricsData;
    }
    try {
        const res = await fetch(API + '/metrics', { headers: authHeaders() });
        if (!res.ok) throw new Error('Failed to fetch metrics');
        _metricsData = await res.json();
        _lastFetch = Date.now();
        return _metricsData;
    } catch (e) {
        console.error('Metrics fetch error:', e);
        return null;
    }
}

// ---------------------------------------------------------------------------
// Render
// ---------------------------------------------------------------------------

function formatNumber(n) {
    if (n == null) return '—';
    if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
    if (n >= 1_000)     return (n / 1_000).toFixed(0) + 'K';
    return String(n);
}

function renderRateLimitGauge(label, remaining, limit, resetTime) {
    if (remaining == null || limit == null) return '';
    const pct = limit > 0 ? Math.round((remaining / limit) * 100) : 0;
    const cls = pct > 50 ? 'healthy' : pct > 20 ? 'warning' : 'critical';
    let resetStr = '';
    if (resetTime) {
        try { resetStr = new Date(resetTime).toLocaleTimeString(); } catch (_) {}
    }
    return `
        <div class="rl-gauge">
            <div class="rl-gauge-label">${label}</div>
            <div class="rl-gauge-bar-track">
                <div class="rl-gauge-fill ${cls}" style="width:${pct}%"></div>
            </div>
            <div class="rl-gauge-stats">
                <span class="rl-gauge-pct">${pct}%</span>
                <span class="rl-gauge-detail">${formatNumber(remaining)} / ${formatNumber(limit)}</span>
            </div>
            ${resetStr ? `<div class="rl-gauge-reset">Reset: ${resetStr}</div>` : ''}
        </div>`;
}

function renderRateLimitSection(container) {
    const rl = state.rateLimits;
    if (!rl) return;
    const section = document.createElement('div');
    section.className = 'metrics-chart-section rl-section';
    section.innerHTML = `
        <div class="metrics-chart-title">API Rate Limits (Tiempo Real)</div>
        <div class="rl-dashboard">
            ${renderRateLimitGauge('Requests/min', rl['requests-remaining'], rl['requests-limit'], rl['requests-reset'])}
            ${renderRateLimitGauge('Input Tokens/min', rl['input-tokens-remaining'], rl['input-tokens-limit'], rl['input-tokens-reset'])}
            ${renderRateLimitGauge('Output Tokens/min', rl['output-tokens-remaining'], rl['output-tokens-limit'], rl['output-tokens-reset'])}
        </div>
        <div class="rl-meta">
            Modelo: <strong>${parseModelName(state.currentModel)}</strong>
            &nbsp;|&nbsp; Actualizado: ${new Date().toLocaleTimeString()}
        </div>`;
    container.appendChild(section);
}

function renderTokenUsageCards(container, data) {
    const t = data.totals;
    if (!t.all_time.total_input_tokens && !t.all_time.total_output_tokens) return;
    const section = document.createElement('div');
    section.className = 'metrics-cards';
    section.innerHTML = `
        <div class="metric-card">
            <div class="metric-value" style="color:var(--cyan);text-shadow:0 0 12px rgba(0,212,255,0.3)">${formatNumber(t.all_time.total_input_tokens)}</div>
            <div class="metric-label">Input Tokens</div>
        </div>
        <div class="metric-card">
            <div class="metric-value" style="color:var(--magenta);text-shadow:0 0 12px rgba(255,0,170,0.3)">${formatNumber(t.all_time.total_output_tokens)}</div>
            <div class="metric-label">Output Tokens</div>
        </div>`;
    container.appendChild(section);
}

function renderMetrics(data) {
    const container = document.getElementById('metrics-content');
    if (!data) {
        container.innerHTML = '<div id="metrics-loading">No metrics data available.</div>';
        return;
    }

    const t = data.totals;
    container.innerHTML = '';

    // Rate limit section at the top
    renderRateLimitSection(container);

    // --- Summary Cards ---
    const cards = document.createElement('div');
    cards.className = 'metrics-cards';

    cards.innerHTML = `
        <div class="metric-card">
            <div class="metric-value cost">${formatUSD(t.all_time.cost)}</div>
            <div class="metric-label">Total Gastado</div>
            <div class="metric-sub">
                Hoy: ${formatUSD(t.today.cost)}<br>
                Semana: ${formatUSD(t.this_week.cost)}<br>
                Mes: ${formatUSD(t.this_month.cost)}
            </div>
        </div>
        <div class="metric-card">
            <div class="metric-value sessions">${t.all_time.sessions}</div>
            <div class="metric-label">Sesiones</div>
            <div class="metric-sub">
                Hoy: ${t.today.sessions}<br>
                Semana: ${t.this_week.sessions}<br>
                Mes: ${t.this_month.sessions}
            </div>
        </div>
        <div class="metric-card">
            <div class="metric-value duration">${formatDuration(t.all_time.avg_duration_ms)}</div>
            <div class="metric-label">Duraci&oacute;n Prom.</div>
            <div class="metric-sub">
                Costo prom: ${formatUSD(t.all_time.avg_cost)}
            </div>
        </div>
        <div class="metric-card">
            <div class="metric-value">${t.all_time.total_turns}</div>
            <div class="metric-label">Total Turnos</div>
            <div class="metric-sub">
                &nbsp;
            </div>
        </div>
    `;
    container.appendChild(cards);

    // --- Token usage cards ---
    renderTokenUsageCards(container, data);

    // --- Charts ---
    renderBarChart(data.by_hour, container, {
        title: 'Uso por Hora',
        labelKey: 'hour',
        formatLabel: h => (h % 3 === 0) ? h + 'h' : '',
        valueKey: 'cost',
        tooltipFn: d => `${d.hour}:00 — ${formatUSD(d.cost)} | ${d.sessions} sesiones`,
    });

    renderBarChart(data.by_dow, container, {
        title: 'Uso por D\u00eda de Semana',
        labelKey: 'name',
        valueKey: 'cost',
        tooltipFn: d => `${d.name} — ${formatUSD(d.cost)} | ${d.sessions} sesiones`,
    });

    if (data.by_day.length > 0) {
        renderBarChart(data.by_day, container, {
            title: 'Gasto Diario (\u00daltimos 30 D\u00edas)',
            labelKey: 'day',
            formatLabel: (v, i, total) => (i % Math.max(1, Math.floor(total / 6)) === 0) ? formatShortDate(v) : '',
            valueKey: 'cost',
            tooltipFn: d => `${formatShortDate(d.day)} — ${formatUSD(d.cost)} | ${d.sessions} ses.`,
        });
    }

    if (data.by_month.length > 0) {
        renderBarChart(data.by_month, container, {
            title: 'Gasto Mensual',
            labelKey: 'month',
            formatLabel: v => formatMonth(v),
            valueKey: 'cost',
            tooltipFn: d => `${formatMonth(d.month)} — ${formatUSD(d.cost)} | ${d.sessions} ses.`,
        });
    }
}

function renderBarChart(items, parentContainer, options) {
    const section = document.createElement('div');
    section.className = 'metrics-chart-section';

    const title = document.createElement('div');
    title.className = 'metrics-chart-title';
    title.textContent = options.title;
    section.appendChild(title);

    const chart = document.createElement('div');
    chart.className = 'chart-container';

    const maxVal = Math.max(...items.map(d => d[options.valueKey] || 0), 0.0001);

    items.forEach((d, i) => {
        const group = document.createElement('div');
        group.className = 'chart-bar-group';

        const bar = document.createElement('div');
        bar.className = 'chart-bar';
        const pct = (d[options.valueKey] / maxVal) * 100;
        bar.style.height = Math.max(pct, 1) + '%';

        if (options.tooltipFn) {
            const tip = document.createElement('span');
            tip.className = 'chart-tooltip';
            tip.textContent = options.tooltipFn(d);
            bar.appendChild(tip);
        }

        group.appendChild(bar);

        const label = document.createElement('span');
        label.className = 'chart-label';
        const labelKey = options.labelKey;
        const rawVal = d[labelKey];
        if (options.formatLabel) {
            label.textContent = options.formatLabel(rawVal, i, items.length);
        } else {
            label.textContent = rawVal;
        }
        group.appendChild(label);

        chart.appendChild(group);
    });

    section.appendChild(chart);
    parentContainer.appendChild(section);
}

// ---------------------------------------------------------------------------
// Toggle
// ---------------------------------------------------------------------------

export function toggleMetrics() {
    _metricsOpen = !_metricsOpen;
    if (_metricsOpen) {
        // Hide other panels, show metrics
        dom.chatPanel.classList.add('hidden');
        dom.fileBrowser.classList.add('hidden');
        dom.metricsPanel.classList.remove('hidden');
        const content = document.getElementById('metrics-content');
        content.innerHTML = '<div id="metrics-loading">Cargando m\u00e9tricas...</div>';
        fetchMetrics().then(data => {
            if (data) renderMetrics(data);
        });
    } else {
        dom.metricsPanel.classList.add('hidden');
        // Restore previous panel
        const agent = state.agents.get(state.activeAgentId);
        if (agent && agent.cwd) {
            dom.chatPanel.classList.remove('hidden');
        } else {
            dom.fileBrowser.classList.remove('hidden');
        }
    }
}

export function closeMetrics() {
    if (_metricsOpen) toggleMetrics();
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------

export function initMetrics() {
    dom.metricsToggle = document.getElementById('metrics-toggle');
    dom.metricsPanel  = document.getElementById('metrics-panel');

    dom.metricsToggle.addEventListener('click', toggleMetrics);

    document.getElementById('metrics-close-btn').addEventListener('click', toggleMetrics);
    document.getElementById('metrics-refresh-btn').addEventListener('click', () => {
        const content = document.getElementById('metrics-content');
        content.innerHTML = '<div id="metrics-loading">Cargando m\u00e9tricas...</div>';
        fetchMetrics(true).then(data => {
            if (data) renderMetrics(data);
        });
    });
}
