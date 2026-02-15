// ---------------------------------------------------------------------------
// File Browser — multi-agent aware
// ---------------------------------------------------------------------------

import { state, dom, API, authHeaders, setStatus } from './app.js';
import { wsSend } from './websocket.js';
import { clearHistory } from './history.js';
import { getActiveAgent, showTabBar } from './tabs.js';

export function showFileBrowser() {
    dom.apiKeyPanel.classList.add('hidden');
    if (dom.settingsPanel) dom.settingsPanel.classList.add('hidden');
    dom.fileBrowser.classList.remove('hidden');
    const agent = getActiveAgent();
    const startPath = agent ? agent.currentBrowsePath : '~';
    loadDir(startPath);
}

export async function loadDir(path) {
    try {
        const res = await fetch(`${API}/browse?path=${encodeURIComponent(path)}`, { headers: authHeaders() });
        const data = await res.json();

        if (data.error) {
            setStatus('error', data.error);
            return;
        }

        // Update per-agent browse path (not global)
        const activeAgent = getActiveAgent();
        if (activeAgent) {
            activeAgent.currentBrowsePath = data.current;
        }
        state.currentBrowsePath = data.current; // Keep global in sync for fallback
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
        // Use the active agent's browse path
        const agent = getActiveAgent();
        const browsePath = agent ? agent.currentBrowsePath : state.currentBrowsePath;

        // Send set_cwd with agent_id — history loads when server responds with resolved cwd
        wsSend({ type: 'set_cwd', path: browsePath, agent_id: state.activeAgentId });
        dom.fileBrowser.classList.add('hidden');
        dom.chatPanel.classList.remove('hidden');
        dom.projectNameEl.textContent = browsePath.split(/[/\\]/).pop();
        showTabBar();
    });

    dom.changeDirBtn.addEventListener('click', () => {
        // Use the active agent's browse path (not global)
        const agent = getActiveAgent();
        const browsePath = agent ? (agent.cwd || agent.currentBrowsePath) : state.currentBrowsePath;

        dom.chatPanel.classList.add('hidden');
        dom.fileBrowser.classList.remove('hidden');
        loadDir(browsePath);
    });

    dom.clearHistBtn.addEventListener('click', async () => {
        // Use the active agent's cwd (not global state.currentCwd)
        const agent = getActiveAgent();
        const cwd = agent ? agent.cwd : null;
        if (!cwd) return;

        await clearHistory(cwd, state.activeAgentId);
        // Reset the Claude session too
        wsSend({ type: 'set_cwd', path: cwd, agent_id: state.activeAgentId });
    });
}
