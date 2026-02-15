// ---------------------------------------------------------------------------
// Message history persistence (load / clear) — per-agent aware
// ---------------------------------------------------------------------------

import { state, API, authHeaders, dom } from './app.js';
import { appendMsg, appendToolUse, appendToolResult, scrollToBottom } from './chat.js';

export async function loadHistory(cwd, agentId = 'default') {
    try {
        const params = new URLSearchParams({ cwd, agent_id: agentId });
        const res = await fetch(
            `${API}/messages?${params}`,
            { headers: authHeaders() },
        );
        if (!res.ok) return;
        const data = await res.json();

        if (!data.messages || data.messages.length === 0) return;

        // Get the agent's message container
        const agent = state.agents.get(agentId);
        const targetEl = agent ? agent.messagesEl : dom.chatMessages;

        // Clear the target container before loading history
        targetEl.innerHTML = '';

        for (const msg of data.messages) {
            renderHistoryMessage(msg, targetEl);
        }

        // Only scroll to bottom if this is the active agent (visible)
        if (agentId === state.activeAgentId) {
            scrollToBottom();
        }
    } catch (err) {
        console.warn('Failed to load history:', err);
    }
}

function renderHistoryMessage(msg, targetEl) {
    const opts = { animate: false, _targetEl: targetEl };

    switch (msg.type) {
        case 'text':
            appendMsg('user', msg.content.text, opts);
            break;

        case 'assistant_text':
            appendMsg('assistant', msg.content.text, opts);
            break;

        case 'tool_use':
            appendToolUse(msg.content.tool, msg.content.input || {}, opts);
            break;

        case 'tool_result':
            appendToolResult(msg.content.content, msg.content.is_error, opts);
            break;

        case 'result': {
            const r = msg.content;
            if (r.cost != null || r.duration_ms != null) {
                let info = '';
                if (r.duration_ms) info += (r.duration_ms / 1000).toFixed(1) + 's';
                if (r.num_turns) info += ' | ' + r.num_turns + ' turns';
                if (r.cost) info += ' | $' + r.cost.toFixed(4);
                if (info) appendMsg('system', info, opts);
            }
            break;
        }

        case 'error':
            appendMsg('system', 'Error: ' + msg.content.text, opts);
            break;
    }
}

export async function clearHistory(cwd, agentId = null) {
    try {
        const params = new URLSearchParams({ cwd });
        if (agentId) params.set('agent_id', agentId);
        const res = await fetch(
            `${API}/messages?${params}`,
            { method: 'DELETE', headers: authHeaders() },
        );
        if (res.ok) {
            // Clear the correct container
            if (agentId) {
                const agent = state.agents.get(agentId);
                if (agent) agent.messagesEl.innerHTML = '';
            } else {
                // Clear all agents' message containers
                for (const [, agent] of state.agents) {
                    agent.messagesEl.innerHTML = '';
                }
            }
        }
    } catch (err) {
        console.warn('Failed to clear history:', err);
    }
}
