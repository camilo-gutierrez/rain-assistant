// ---------------------------------------------------------------------------
// Message history persistence (load / clear)
// ---------------------------------------------------------------------------

import { state, API, authHeaders, dom } from './app.js';
import { appendMsg, appendToolUse, appendToolResult, scrollToBottom } from './chat.js';

export async function loadHistory(cwd) {
    try {
        const res = await fetch(
            `${API}/messages?cwd=${encodeURIComponent(cwd)}`,
            { headers: authHeaders() },
        );
        if (!res.ok) return;
        const data = await res.json();

        if (!data.messages || data.messages.length === 0) return;

        dom.chatMessages.innerHTML = '';

        for (const msg of data.messages) {
            renderHistoryMessage(msg);
        }
        scrollToBottom();
    } catch (err) {
        console.warn('Failed to load history:', err);
    }
}

function renderHistoryMessage(msg) {
    switch (msg.type) {
        case 'text':
            appendMsg('user', msg.content.text, { animate: false });
            break;

        case 'assistant_text':
            appendMsg('assistant', msg.content.text, { animate: false });
            break;

        case 'tool_use':
            appendToolUse(msg.content.tool, msg.content.input || {}, { animate: false });
            break;

        case 'tool_result':
            appendToolResult(msg.content.content, msg.content.is_error, { animate: false });
            break;

        case 'result': {
            const r = msg.content;
            if (r.cost != null || r.duration_ms != null) {
                let info = '';
                if (r.duration_ms) info += (r.duration_ms / 1000).toFixed(1) + 's';
                if (r.num_turns) info += ' | ' + r.num_turns + ' turns';
                if (r.cost) info += ' | $' + r.cost.toFixed(4);
                if (info) appendMsg('system', info, { animate: false });
            }
            break;
        }

        case 'error':
            appendMsg('system', 'Error: ' + msg.content.text, { animate: false });
            break;
    }
}

export async function clearHistory(cwd) {
    try {
        const res = await fetch(
            `${API}/messages?cwd=${encodeURIComponent(cwd)}`,
            { method: 'DELETE', headers: authHeaders() },
        );
        if (res.ok) {
            dom.chatMessages.innerHTML = '';
        }
    } catch (err) {
        console.warn('Failed to clear history:', err);
    }
}
