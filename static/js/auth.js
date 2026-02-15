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

let _lockoutTimer = null;

function startLockoutCountdown(seconds) {
    dom.pinInput.disabled = true;
    dom.pinSubmitBtn.disabled = true;
    dom.pinInput.value = '';

    clearInterval(_lockoutTimer);

    function updateCountdown(remaining) {
        const mins = Math.floor(remaining / 60);
        const secs = remaining % 60;
        const timeStr = mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
        dom.pinError.textContent = `Too many attempts. Try again in ${timeStr}`;
        dom.pinError.style.display = '';
    }

    let remaining = seconds;
    updateCountdown(remaining);

    _lockoutTimer = setInterval(() => {
        remaining--;
        if (remaining <= 0) {
            clearInterval(_lockoutTimer);
            dom.pinError.textContent = 'Incorrect PIN';
            dom.pinError.style.display = 'none';
            dom.pinInput.disabled = false;
            dom.pinSubmitBtn.disabled = false;
            dom.pinInput.focus();
        } else {
            updateCountdown(remaining);
        }
    }, 1000);
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
            return;
        }

        // Locked out (429)
        if (data.locked) {
            startLockoutCountdown(data.remaining_seconds || 300);
            return;
        }

        // Wrong PIN — show remaining attempts
        dom.pinError.style.display = '';
        if (typeof data.remaining_attempts === 'number') {
            dom.pinError.textContent = data.remaining_attempts === 1
                ? 'Incorrect PIN — 1 attempt remaining'
                : `Incorrect PIN — ${data.remaining_attempts} attempts remaining`;
        } else {
            dom.pinError.textContent = 'Incorrect PIN';
        }
        dom.pinInput.value = '';
        dom.pinInput.focus();
    } catch {
        dom.pinError.textContent = 'Connection error';
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
