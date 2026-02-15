// ---------------------------------------------------------------------------
// WebSocket connection & messaging — multiplexed with agent_id
// ---------------------------------------------------------------------------

import { state, dom, WS_URL, setStatus } from './app.js';
import { handleServerMsg } from './chat.js';
import { reinitAgentsOnServer } from './tabs.js';

let _consecutiveFails = 0;

function _resetToPin() {
    state.authToken = null;
    sessionStorage.removeItem('rain-token');
    dom.apiKeyPanel.classList.add('hidden');
    dom.fileBrowser.classList.add('hidden');
    dom.chatPanel.classList.add('hidden');
    if (dom.settingsPanel) dom.settingsPanel.classList.add('hidden');
    if (dom.metricsPanel) dom.metricsPanel.classList.add('hidden');
    dom.pinPanel.classList.remove('hidden');
    dom.pinError.style.display = '';
}

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
        _consecutiveFails = 0;              // reset on successful connect
        setStatus('connected', 'Connected');
        dom.recordBtn.disabled = false;

        // Re-register all agents that had a working directory on the server.
        // This handles reconnection after a temporary disconnect so agents
        // don't need to re-select their projects.
        reinitAgentsOnServer();
    };

    state.ws.onmessage = (e) => {
        try { handleServerMsg(JSON.parse(e.data)); }
        catch (err) { console.error('WS parse error:', err); }
    };

    state.ws.onclose = (e) => {
        setStatus('disconnected', 'Disconnected');
        dom.recordBtn.disabled = true;

        // Server explicitly rejected the token
        if (e.code === 4001) {
            _consecutiveFails = 0;
            _resetToPin();
            return;
        }

        // If the connection never opened (failed before onopen), track it
        _consecutiveFails++;
        if (_consecutiveFails >= 3) {
            // Likely a bad token — force re-auth
            console.warn('Too many consecutive WS failures, requesting re-auth');
            _consecutiveFails = 0;
            _resetToPin();
            return;
        }

        state.reconnectTimer = setTimeout(connectWS, 3000);
    };

    state.ws.onerror = () => state.ws.close();
}

/**
 * Send a message through the WebSocket, automatically injecting agent_id.
 * If obj doesn't include agent_id, uses the active agent.
 */
export function wsSend(obj) {
    if (state.ws && state.ws.readyState === WebSocket.OPEN) {
        if (!obj.agent_id && state.activeAgentId) {
            obj.agent_id = state.activeAgentId;
        }
        state.ws.send(JSON.stringify(obj));
    }
}
