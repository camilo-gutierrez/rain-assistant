// ---------------------------------------------------------------------------
// WebSocket connection & messaging
// ---------------------------------------------------------------------------

import { state, dom, WS_URL, setStatus } from './app.js';
import { handleServerMsg } from './chat.js';

export function connectWS() {
    if (state.reconnectTimer) {
        clearTimeout(state.reconnectTimer);
        state.reconnectTimer = null;
    }

    const wsUrl = state.authToken
        ? WS_URL + '?token=' + encodeURIComponent(state.authToken)
        : WS_URL;
    state.ws = new WebSocket(wsUrl);

    state.ws.onopen = () => {
        setStatus('connected', 'Connected');
        dom.recordBtn.disabled = false;
    };

    state.ws.onmessage = (e) => {
        try { handleServerMsg(JSON.parse(e.data)); }
        catch (err) { console.error('WS parse error:', err); }
    };

    state.ws.onclose = (e) => {
        setStatus('disconnected', 'Disconnected');
        dom.recordBtn.disabled = true;
        if (e.code === 4001) {
            state.authToken = null;
            sessionStorage.removeItem('rain-token');
            dom.apiKeyPanel.classList.add('hidden');
            dom.fileBrowser.classList.add('hidden');
            dom.chatPanel.classList.add('hidden');
            dom.pinPanel.classList.remove('hidden');
            dom.pinError.style.display = '';
            return;
        }
        state.reconnectTimer = setTimeout(connectWS, 3000);
    };

    state.ws.onerror = () => state.ws.close();
}

export function wsSend(obj) {
    if (state.ws && state.ws.readyState === WebSocket.OPEN) {
        state.ws.send(JSON.stringify(obj));
    }
}
