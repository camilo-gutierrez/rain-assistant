// ---------------------------------------------------------------------------
// Chat rendering, markdown, WS message handling — multi-agent aware
// ---------------------------------------------------------------------------

import { state, dom, setStatus } from './app.js';
import { wsSend } from './websocket.js';
import { sendNotification } from './notifications.js';
import { loadHistory } from './history.js';
import {
    getAgentMessagesEl,
    getActiveAgent,
    setAgentStatus,
    incrementUnread,
    showTabBar,
} from './tabs.js';
import { updateModelInfo, updateRateLimits, updateUsageInfo } from './metrics.js';
import { t } from './translations.js';

// ---------------------------------------------------------------------------
// Markdown & HTML helpers
// ---------------------------------------------------------------------------

export function escapeHtml(str) {
    const d = document.createElement('div');
    d.textContent = str;
    return d.innerHTML;
}

export function renderMarkdown(text) {
    let html = escapeHtml(text);
    html = html.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre>$2</pre>');
    html = html.replace(/`([^`]+)`/g, '<code style="background:var(--surface2);padding:2px 5px;border-radius:4px;font-size:13px;font-family:\'JetBrains Mono\',monospace;">$1</code>');
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\n/g, '<br>');
    return html;
}

export function scrollToBottom() {
    dom.chatMessages.scrollTop = dom.chatMessages.scrollHeight;
}

// ---------------------------------------------------------------------------
// Message rendering (agent-scoped)
// ---------------------------------------------------------------------------

/**
 * Get the correct messages container for a given agent_id.
 * Falls back to the active agent if not found.
 */
function getTargetEl(agentId) {
    if (agentId) {
        const el = getAgentMessagesEl(agentId);
        if (el) return el;
    }
    const active = getActiveAgent();
    return active ? active.messagesEl : dom.chatMessages;
}

/**
 * Get the agent object, defaulting to active agent
 */
function getAgent(agentId) {
    if (agentId && state.agents.has(agentId)) {
        return state.agents.get(agentId);
    }
    return getActiveAgent();
}

export function ensureAssistantBubble(agentId) {
    const agent = getAgent(agentId);
    if (!agent) return;
    if (!agent.assistantEl) {
        agent.assistantEl = document.createElement('div');
        agent.assistantEl.className = 'msg assistant';
        agent.messagesEl.appendChild(agent.assistantEl);
        agent.streamText = '';
    }
}

export function finalizeAssistant(agentId) {
    const agent = getAgent(agentId);
    if (!agent) return;
    if (agent.assistantEl) {
        agent.assistantEl.innerHTML = renderMarkdown(agent.streamText);
        agent.assistantEl = null;
        agent.streamText = '';
    }
}

export function appendMsg(role, text, options = {}, agentId = null) {
    const targetEl = options._targetEl || getTargetEl(agentId);
    const div = document.createElement('div');
    div.className = 'msg ' + role;
    if (options.animate === false) div.classList.add('no-animate');
    if (role === 'assistant') {
        div.innerHTML = renderMarkdown(text);
    } else {
        div.textContent = text;
    }
    targetEl.appendChild(div);
    if (agentId === state.activeAgentId || !agentId) scrollToBottom();
}

export function appendToolUse(tool, input, options = {}, agentId = null) {
    const targetEl = options._targetEl || getTargetEl(agentId);
    const div = document.createElement('div');
    div.className = 'tool-block';
    if (options.animate === false) div.classList.add('no-animate');

    let summary = '';
    switch (tool) {
        case 'Read':    summary = input.file_path || ''; break;
        case 'Write':   summary = input.file_path || ''; break;
        case 'Edit':    summary = input.file_path || ''; break;
        case 'Bash':    summary = input.command || ''; break;
        case 'Glob':    summary = input.pattern || ''; break;
        case 'Grep':    summary = input.pattern || ''; break;
        default:        summary = JSON.stringify(input).slice(0, 100);
    }

    div.innerHTML =
        '<div class="tool-header">' + escapeHtml(tool) + '</div>' +
        '<div class="tool-detail">' + escapeHtml(summary) + '</div>';
    targetEl.appendChild(div);
    if (agentId === state.activeAgentId || !agentId) scrollToBottom();
}

export function appendToolResult(content, isError, options = {}, agentId = null) {
    const targetEl = options._targetEl || getTargetEl(agentId);
    const div = document.createElement('div');
    div.className = 'tool-result-block' + (isError ? ' error' : '');
    if (options.animate === false) div.classList.add('no-animate');

    const maxLen = 300;
    const truncated = content && content.length > maxLen;
    const display = truncated ? content.slice(0, maxLen) + '...' : (content || '');

    const pre = document.createElement('pre');
    pre.textContent = display;
    div.appendChild(pre);

    if (truncated) {
        const btn = document.createElement('button');
        btn.className = 'expand-btn';
        btn.textContent = t('chat.showFullOutput');
        btn.addEventListener('click', () => {
            pre.textContent = content;
            pre.style.maxHeight = 'none';
            btn.remove();
        });
        div.appendChild(btn);
    }

    targetEl.appendChild(div);
    if (agentId === state.activeAgentId || !agentId) scrollToBottom();
}

export function resetRecordBtn() {
    dom.recordBtn.textContent = t('chat.holdToSpeak');
    dom.recordBtn.className = '';
    dom.recordBtn.disabled = false;
}

/**
 * Complete reset of an agent's processing state (used for force-stop).
 */
function forceReset(agentId) {
    const agent = getAgent(agentId);
    finalizeAssistant(agentId);
    appendMsg('system', t('chat.forceStopped'), {}, agentId);

    if (agent) {
        agent.isProcessing = false;
        agent.interruptPending = false;
        if (agent.interruptTimer) {
            clearTimeout(agent.interruptTimer);
            agent.interruptTimer = null;
        }
    }

    // Only update global state and UI if this is the active agent
    const effectiveId = agentId || state.activeAgentId;
    if (effectiveId === state.activeAgentId) {
        resetRecordBtn();
        state.isProcessing = false;
        state.interruptPending = false;
        dom.sendTextBtn.disabled = false;
        dom.interruptBtn.classList.add('hidden');
        dom.interruptBtn.classList.remove('force', 'stopping');
        dom.interruptBtn.textContent = t('chat.stop');
        dom.interruptBtn.disabled = false;
        setStatus('connected', t('status.ready'));
    }

    setAgentStatus(effectiveId, 'idle');
}

/**
 * Mark an agent as "processing complete" and reset UI.
 */
function completeProcessing(agentId, statusType) {
    const agent = state.agents.get(agentId);
    if (agent) {
        agent.isProcessing = false;
        agent.interruptPending = false;
        if (agent.interruptTimer) {
            clearTimeout(agent.interruptTimer);
            agent.interruptTimer = null;
        }
    }

    const isActiveAgent = agentId === state.activeAgentId;
    if (isActiveAgent) {
        resetRecordBtn();
        state.isProcessing = false;
        state.interruptPending = false;
        dom.sendTextBtn.disabled = false;
        dom.interruptBtn.classList.add('hidden');
        dom.interruptBtn.classList.remove('force', 'stopping');
        dom.interruptBtn.textContent = t('chat.stop');
        dom.interruptBtn.disabled = false;
        setStatus('connected', t('status.ready'));
    }

    setAgentStatus(agentId, statusType);
}

// ---------------------------------------------------------------------------
// Send user message
// ---------------------------------------------------------------------------

function sendTextMessage() {
    const text = dom.textInput.value.trim();
    if (!text) return;

    const agent = getActiveAgent();
    if (!agent) return;
    if (agent.isProcessing) return;

    // Check that agent has a cwd (project selected)
    if (!agent.cwd) {
        appendMsg('system', t('chat.selectDirFirst'), {}, state.activeAgentId);
        return;
    }

    appendMsg('user', text, {}, state.activeAgentId);
    sendToRainViaWS(text);
    dom.textInput.value = '';
}

export function sendToRainViaWS(text) {
    const agent = getActiveAgent();
    if (!agent) return;

    // Prevent sending if agent has no cwd
    if (!agent.cwd) {
        appendMsg('system', t('chat.selectDirFirst'), {}, state.activeAgentId);
        return;
    }

    agent.isProcessing = true;
    state.isProcessing = true;
    dom.recordBtn.textContent = t('status.rainWorking');
    dom.recordBtn.classList.add('processing');
    dom.recordBtn.disabled = true;
    dom.sendTextBtn.disabled = true;
    dom.interruptBtn.classList.remove('hidden');
    setAgentStatus(state.activeAgentId, 'working');
    wsSend({ type: 'send_message', text, agent_id: state.activeAgentId });
}

// ---------------------------------------------------------------------------
// Handle server messages (multiplexed by agent_id)
// ---------------------------------------------------------------------------

export function handleServerMsg(msg) {
    const agentId = msg.agent_id || state.activeAgentId;
    const agent = state.agents.get(agentId);
    const isActiveAgent = agentId === state.activeAgentId;

    switch (msg.type) {
        case 'status':
            if (isActiveAgent || !msg.agent_id) {
                setStatus('connected', msg.text);
            }
            if (msg.cwd && agent) {
                agent.cwd = msg.cwd;
                if (isActiveAgent) {
                    dom.projectNameEl.textContent = msg.cwd.split(/[/\\]/).pop();
                }
                // Load history when we get the resolved cwd from server
                loadHistory(msg.cwd, agentId);
                showTabBar();
            }
            break;

        case 'assistant_text':
            // Defensive: skip if agent was destroyed
            if (!agent) break;
            ensureAssistantBubble(agentId);
            agent.streamText += msg.text;
            if (agent.assistantEl) {
                agent.assistantEl.innerHTML = renderMarkdown(agent.streamText);
            }
            if (isActiveAgent) scrollToBottom();
            incrementUnread(agentId);
            break;

        case 'stream_text':
            break;

        case 'tool_use':
            if (!agent) break;
            finalizeAssistant(agentId);
            appendToolUse(msg.tool, msg.input, {}, agentId);
            incrementUnread(agentId);
            break;

        case 'tool_result':
            if (!agent) break;
            appendToolResult(msg.content, msg.is_error, {}, agentId);
            incrementUnread(agentId);
            break;

        case 'model_info':
            updateModelInfo(msg.model);
            break;

        case 'rate_limits':
            updateRateLimits(msg.limits);
            break;

        case 'result':
            finalizeAssistant(agentId);
            if (msg.usage) updateUsageInfo(msg.usage);
            if (msg.cost != null || msg.duration_ms != null) {
                let info = '';
                if (msg.duration_ms) info += (msg.duration_ms / 1000).toFixed(1) + 's';
                if (msg.num_turns) info += ' | ' + msg.num_turns + ' turns';
                if (msg.cost) info += ' | $' + msg.cost.toFixed(4);
                if (info) appendMsg('system', info, {}, agentId);
            }
            sendNotification('Rain has finished', msg.text || 'Response complete');
            completeProcessing(agentId, 'done');
            break;

        case 'error':
            finalizeAssistant(agentId);
            appendMsg('system', 'Error: ' + msg.text, {}, agentId);
            sendNotification('Rain needs attention', 'Error: ' + (msg.text || 'Unknown error'));
            completeProcessing(agentId, 'error');

            if (isActiveAgent) {
                setStatus('error', msg.text);
            }
            break;

        case 'agent_destroyed':
            // Handled by tabs.js closeAgent
            break;
    }
}

// ---------------------------------------------------------------------------
// Init: wire up text input + interrupt (per-agent scoped)
// ---------------------------------------------------------------------------

export function initChat() {
    dom.sendTextBtn.addEventListener('click', sendTextMessage);
    dom.textInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendTextMessage();
        }
    });

    dom.interruptBtn.addEventListener('click', () => {
        const activeAgent = getActiveAgent();
        if (!activeAgent) return;

        // Force-stop: already in force mode
        if (dom.interruptBtn.classList.contains('force')) {
            forceReset(state.activeAgentId);
            return;
        }

        // Send interrupt to server for this specific agent
        wsSend({ type: 'interrupt', agent_id: state.activeAgentId });
        dom.interruptBtn.textContent = t('chat.stopping');
        dom.interruptBtn.classList.add('stopping');
        dom.interruptBtn.disabled = true;

        state.interruptPending = true;
        activeAgent.interruptPending = true;

        // Per-agent force-stop timeout: after 5s, show "Force Stop" button
        // Clear any previous timer for this agent
        if (activeAgent.interruptTimer) {
            clearTimeout(activeAgent.interruptTimer);
        }

        const targetAgentId = state.activeAgentId;
        activeAgent.interruptTimer = setTimeout(() => {
            // Re-check the agent still exists and is still processing
            const agentCheck = state.agents.get(targetAgentId);
            if (agentCheck && agentCheck.interruptPending && agentCheck.isProcessing) {
                // Only update UI if this agent is still the active one
                if (state.activeAgentId === targetAgentId) {
                    dom.interruptBtn.textContent = t('chat.forceStop');
                    dom.interruptBtn.disabled = false;
                    dom.interruptBtn.classList.remove('stopping');
                    dom.interruptBtn.classList.add('force');
                }
            }
            agentCheck && (agentCheck.interruptTimer = null);
        }, 5000);
    });
}
