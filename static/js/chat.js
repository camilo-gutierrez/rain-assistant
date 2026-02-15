// ---------------------------------------------------------------------------
// Chat rendering, markdown, WS message handling
// ---------------------------------------------------------------------------

import { state, dom, setStatus } from './app.js';
import { wsSend } from './websocket.js';
import { sendNotification } from './notifications.js';
import { loadHistory } from './history.js';

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
// Message rendering
// ---------------------------------------------------------------------------

export function ensureAssistantBubble() {
    if (!state.currentAssistantEl) {
        state.currentAssistantEl = document.createElement('div');
        state.currentAssistantEl.className = 'msg assistant';
        dom.chatMessages.appendChild(state.currentAssistantEl);
        state.currentStreamText = '';
    }
}

export function finalizeAssistant() {
    if (state.currentAssistantEl) {
        state.currentAssistantEl.innerHTML = renderMarkdown(state.currentStreamText);
        state.currentAssistantEl = null;
        state.currentStreamText = '';
    }
}

export function appendMsg(role, text, options = {}) {
    const div = document.createElement('div');
    div.className = 'msg ' + role;
    if (options.animate === false) div.classList.add('no-animate');
    if (role === 'assistant') {
        div.innerHTML = renderMarkdown(text);
    } else {
        div.textContent = text;
    }
    dom.chatMessages.appendChild(div);
    scrollToBottom();
}

export function appendToolUse(tool, input, options = {}) {
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
    dom.chatMessages.appendChild(div);
    scrollToBottom();
}

export function appendToolResult(content, isError, options = {}) {
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
        btn.textContent = 'Show full output';
        btn.addEventListener('click', () => {
            pre.textContent = content;
            pre.style.maxHeight = 'none';
            btn.remove();
        });
        div.appendChild(btn);
    }

    dom.chatMessages.appendChild(div);
    scrollToBottom();
}

export function resetRecordBtn() {
    dom.recordBtn.textContent = 'Hold to Speak';
    dom.recordBtn.className = '';
    dom.recordBtn.disabled = false;
}

function forceReset() {
    finalizeAssistant();
    appendMsg('system', 'Force stopped.');
    resetRecordBtn();
    state.isProcessing = false;
    state.interruptPending = false;
    dom.sendTextBtn.disabled = false;
    dom.interruptBtn.classList.add('hidden');
    dom.interruptBtn.classList.remove('force', 'stopping');
    dom.interruptBtn.textContent = 'Stop';
    dom.interruptBtn.disabled = false;
    setStatus('connected', 'Ready');
}

// ---------------------------------------------------------------------------
// Send user message
// ---------------------------------------------------------------------------

function sendTextMessage() {
    const text = dom.textInput.value.trim();
    if (!text || state.isProcessing) return;
    appendMsg('user', text);
    sendToRainViaWS(text);
    dom.textInput.value = '';
}

export function sendToRainViaWS(text) {
    state.isProcessing = true;
    dom.recordBtn.textContent = 'Rain is working...';
    dom.recordBtn.classList.add('processing');
    dom.recordBtn.disabled = true;
    dom.sendTextBtn.disabled = true;
    dom.interruptBtn.classList.remove('hidden');
    wsSend({ type: 'send_message', text });
}

// ---------------------------------------------------------------------------
// Handle server messages
// ---------------------------------------------------------------------------

export function handleServerMsg(msg) {
    switch (msg.type) {
        case 'status':
            setStatus('connected', msg.text);
            if (msg.cwd) {
                dom.projectNameEl.textContent = msg.cwd.split(/[/\\]/).pop();
                // Load history when we get the resolved cwd from server
                if (state.currentCwd !== msg.cwd) {
                    state.currentCwd = msg.cwd;
                    loadHistory(msg.cwd);
                }
            }
            break;

        case 'assistant_text':
            ensureAssistantBubble();
            state.currentStreamText += msg.text;
            state.currentAssistantEl.innerHTML = renderMarkdown(state.currentStreamText);
            scrollToBottom();
            break;

        case 'stream_text':
            break;

        case 'tool_use':
            finalizeAssistant();
            appendToolUse(msg.tool, msg.input);
            break;

        case 'tool_result':
            appendToolResult(msg.content, msg.is_error);
            break;

        case 'result':
            finalizeAssistant();
            if (msg.cost != null || msg.duration_ms != null) {
                let info = '';
                if (msg.duration_ms) info += (msg.duration_ms / 1000).toFixed(1) + 's';
                if (msg.num_turns) info += ' | ' + msg.num_turns + ' turns';
                if (msg.cost) info += ' | $' + msg.cost.toFixed(4);
                if (info) appendMsg('system', info);
            }
            sendNotification('Rain has finished', msg.text || 'Response complete');
            resetRecordBtn();
            state.isProcessing = false;
            state.interruptPending = false;
            dom.sendTextBtn.disabled = false;
            dom.interruptBtn.classList.add('hidden');
            dom.interruptBtn.classList.remove('force', 'stopping');
            dom.interruptBtn.textContent = 'Stop';
            dom.interruptBtn.disabled = false;
            setStatus('connected', 'Ready');
            break;

        case 'error':
            finalizeAssistant();
            appendMsg('system', 'Error: ' + msg.text);
            sendNotification('Rain needs attention', 'Error: ' + (msg.text || 'Unknown error'));
            resetRecordBtn();
            state.isProcessing = false;
            state.interruptPending = false;
            dom.sendTextBtn.disabled = false;
            dom.interruptBtn.classList.add('hidden');
            dom.interruptBtn.classList.remove('force', 'stopping');
            dom.interruptBtn.textContent = 'Stop';
            dom.interruptBtn.disabled = false;
            setStatus('error', msg.text);
            break;
    }
}

// ---------------------------------------------------------------------------
// Init: wire up text input + interrupt
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
        if (dom.interruptBtn.classList.contains('force')) {
            forceReset();
            return;
        }
        wsSend({ type: 'interrupt' });
        dom.interruptBtn.textContent = 'Stopping...';
        dom.interruptBtn.classList.add('stopping');
        dom.interruptBtn.disabled = true;
        state.interruptPending = true;

        setTimeout(() => {
            if (state.interruptPending && state.isProcessing) {
                dom.interruptBtn.textContent = 'Force Stop';
                dom.interruptBtn.disabled = false;
                dom.interruptBtn.classList.remove('stopping');
                dom.interruptBtn.classList.add('force');
            }
        }, 5000);
    });
}
