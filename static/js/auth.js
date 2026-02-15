// ---------------------------------------------------------------------------
// Authentication (PIN + API Key)
// ---------------------------------------------------------------------------

import { state, dom, API } from './app.js';
import { connectWS, wsSend } from './websocket.js';
import { showFileBrowser } from './browser.js';

export function migrateStorageKeys() {
    const migrations = [
        { old: 'voice-claude-token', new: 'rain-token', storage: sessionStorage },
        { old: 'voice-claude-api-key', new: 'rain-api-key', storage: localStorage },
        { old: 'voice-claude-theme', new: 'rain-theme', storage: localStorage },
    ];
    migrations.forEach(({ old: oldKey, new: newKey, storage }) => {
        const val = storage.getItem(oldKey);
        if (val && !storage.getItem(newKey)) {
            storage.setItem(newKey, val);
            storage.removeItem(oldKey);
        }
    });
}

async function submitPin() {
    const pin = dom.pinInput.value.trim();
    if (!pin) return;
    dom.pinSubmitBtn.disabled = true;
    dom.pinError.style.display = 'none';
    try {
        const res = await fetch(`${API}/auth`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pin }),
        });
        const data = await res.json();
        if (data.token) {
            state.authToken = data.token;
            sessionStorage.setItem('rain-token', state.authToken);
            dom.pinPanel.classList.add('hidden');
            dom.apiKeyPanel.classList.remove('hidden');
            connectWS();
        } else {
            dom.pinError.style.display = '';
            dom.pinInput.value = '';
            dom.pinInput.focus();
        }
    } catch {
        dom.pinError.style.display = '';
    }
    dom.pinSubmitBtn.disabled = false;
}

export function initAuth() {
    // PIN handlers
    dom.pinSubmitBtn.addEventListener('click', submitPin);
    dom.pinInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') { e.preventDefault(); submitPin(); }
    });

    // API key: restore saved
    const savedKey = localStorage.getItem('rain-api-key');
    if (savedKey) {
        dom.apiKeyInput.value = savedKey;
        dom.savedKeyInfo.style.display = '';
    }

    dom.toggleKeyVis.addEventListener('click', () => {
        const isPassword = dom.apiKeyInput.type === 'password';
        dom.apiKeyInput.type = isPassword ? 'text' : 'password';
        dom.toggleKeyVis.textContent = isPassword ? 'Hide' : 'Show';
    });

    dom.connectApiBtn.addEventListener('click', () => {
        const key = dom.apiKeyInput.value.trim();
        if (!key) return;
        localStorage.setItem('rain-api-key', key);
        state.usingApiKey = true;
        wsSend({ type: 'set_api_key', key });
        showFileBrowser();
    });

    dom.skipApiBtn.addEventListener('click', () => {
        state.usingApiKey = false;
        showFileBrowser();
    });

    dom.clearKeyBtn.addEventListener('click', () => {
        localStorage.removeItem('rain-api-key');
        dom.apiKeyInput.value = '';
        dom.savedKeyInfo.style.display = 'none';
    });
}
