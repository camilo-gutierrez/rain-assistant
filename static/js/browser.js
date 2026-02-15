// ---------------------------------------------------------------------------
// File Browser
// ---------------------------------------------------------------------------

import { state, dom, API, authHeaders, setStatus } from './app.js';
import { wsSend } from './websocket.js';
import { clearHistory } from './history.js';

export function showFileBrowser() {
    dom.apiKeyPanel.classList.add('hidden');
    dom.fileBrowser.classList.remove('hidden');
    loadDir('~');
}

async function loadDir(path) {
    try {
        const res = await fetch(`${API}/browse?path=${encodeURIComponent(path)}`, { headers: authHeaders() });
        const data = await res.json();

        if (data.error) {
            setStatus('error', data.error);
            return;
        }

        state.currentBrowsePath = data.current;
        dom.currentPathEl.textContent = data.current;
        dom.fileList.innerHTML = '';

        for (const entry of data.entries) {
            const div = document.createElement('div');
            div.className = 'file-entry ' + (entry.is_dir ? 'directory' : 'file');

            const icon = document.createElement('span');
            icon.className = 'icon';
            icon.textContent = entry.name === '..' ? '\u2B06' : entry.is_dir ? '\uD83D\uDCC1' : '\uD83D\uDCC4';

            const name = document.createElement('span');
            name.className = 'name';
            name.textContent = entry.name;

            div.appendChild(icon);
            div.appendChild(name);

            if (!entry.is_dir && entry.size > 0) {
                const size = document.createElement('span');
                size.className = 'size';
                size.textContent = formatSize(entry.size);
                div.appendChild(size);
            }

            if (entry.is_dir) {
                div.addEventListener('click', () => loadDir(entry.path));
            }

            dom.fileList.appendChild(div);
        }
    } catch {
        setStatus('error', 'Failed to load directory');
    }
}

function formatSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / 1048576).toFixed(1) + ' MB';
}

export function initBrowser() {
    dom.selectDirBtn.addEventListener('click', () => {
        // Send set_cwd — history will load when the server responds with resolved cwd
        wsSend({ type: 'set_cwd', path: state.currentBrowsePath });
        dom.fileBrowser.classList.add('hidden');
        dom.chatPanel.classList.remove('hidden');
        dom.projectNameEl.textContent = state.currentBrowsePath.split(/[/\\]/).pop();
    });

    dom.changeDirBtn.addEventListener('click', () => {
        dom.chatPanel.classList.add('hidden');
        dom.fileBrowser.classList.remove('hidden');
        loadDir(state.currentBrowsePath);
    });

    dom.clearHistBtn.addEventListener('click', async () => {
        if (!state.currentCwd) return;
        await clearHistory(state.currentCwd);
        // Reset the Claude session too
        wsSend({ type: 'set_cwd', path: state.currentCwd });
    });
}
