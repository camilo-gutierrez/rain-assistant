// ---------------------------------------------------------------------------
// Tab manager — Multi-agent tab bar with status dots and badges
// ---------------------------------------------------------------------------

import { state, dom } from './app.js';
import { wsSend } from './websocket.js';
import { loadHistory } from './history.js';
import { t } from './translations.js';

let _tabCounter = 0;

// Agent states: 'idle' | 'working' | 'done' | 'error'
// Each agent entry: { id, cwd, label, status, unread, messagesEl, scrollPos,
//                     streamText, assistantEl, isProcessing, interruptPending,
//                     currentBrowsePath, interruptTimer }

/**
 * Get or create the default agent
 */
export function ensureDefaultAgent() {
    if (state.agents.size === 0) {
        createAgent('default');
    }
    if (!state.activeAgentId) {
        state.activeAgentId = 'default';
    }
}

/**
 * Create a new agent tab.
 * Returns the agentId.
 */
export function createAgent(agentId = null) {
    const isDefault = agentId === 'default';
    if (!agentId) {
        _tabCounter++;
        agentId = 'agent-' + _tabCounter;
    }

    // Label: "Agent 1" for default, "Agent N" for subsequent ones
    const label = isDefault ? 'Agent 1' : 'Agent ' + (_tabCounter + 1);

    const agent = {
        id: agentId,
        cwd: null,
        currentBrowsePath: '~',   // Per-agent browse path (independent per tab)
        label,
        status: 'idle',           // idle | working | done | error
        unread: 0,
        messagesEl: document.createElement('div'),
        scrollPos: 0,
        streamText: '',
        assistantEl: null,
        isProcessing: false,
        interruptPending: false,
        interruptTimer: null,      // Track per-agent force-stop timeout
    };

    agent.messagesEl.className = 'agent-messages';

    state.agents.set(agentId, agent);
    renderTabs();

    return agentId;
}

/**
 * Switch to a specific agent tab
 */
export function switchToAgent(agentId) {
    const agent = state.agents.get(agentId);
    if (!agent) return;

    const prevAgent = state.agents.get(state.activeAgentId);

    // Save scroll position of current agent
    if (prevAgent && dom.chatMessages) {
        prevAgent.scrollPos = dom.chatMessages.scrollTop;
    }

    state.activeAgentId = agentId;

    // Clear unread for this agent
    agent.unread = 0;

    // Swap message container
    dom.chatMessages.innerHTML = '';
    dom.chatMessages.appendChild(agent.messagesEl);

    // Restore scroll position
    dom.chatMessages.scrollTop = agent.scrollPos;

    // Update project name in header
    if (agent.cwd) {
        dom.projectNameEl.textContent = agent.cwd.split(/[/\\]/).pop();
    } else {
        dom.projectNameEl.textContent = agent.label;
    }

    // Sync processing state with current agent
    syncProcessingUI(agent);

    // Sync global state with the active agent's state
    state.isProcessing = agent.isProcessing;
    state.interruptPending = agent.interruptPending;

    renderTabs();
}

/**
 * Close an agent tab
 */
export function closeAgent(agentId) {
    if (state.agents.size <= 1) return; // Can't close last tab

    const agent = state.agents.get(agentId);
    if (!agent) return;

    // Clear any pending timers
    if (agent.interruptTimer) {
        clearTimeout(agent.interruptTimer);
        agent.interruptTimer = null;
    }

    // Tell server to destroy this agent
    wsSend({ type: 'destroy_agent', agent_id: agentId });

    state.agents.delete(agentId);

    // If we closed the active tab, switch to another
    if (state.activeAgentId === agentId) {
        const firstId = state.agents.keys().next().value;
        switchToAgent(firstId);
    } else {
        renderTabs();
    }
}

/**
 * Update an agent's status dot
 */
export function setAgentStatus(agentId, status) {
    const agent = state.agents.get(agentId);
    if (!agent) return;
    agent.status = status;
    renderTabs();

    // Flash "done" status briefly, then revert to idle
    if (status === 'done') {
        setTimeout(() => {
            // Re-check agent still exists (could have been destroyed)
            const a = state.agents.get(agentId);
            if (a && a.status === 'done') {
                a.status = 'idle';
                renderTabs();
            }
        }, 3000);
    }
}

/**
 * Increment unread count for a non-active agent
 */
export function incrementUnread(agentId) {
    if (agentId === state.activeAgentId) return;
    const agent = state.agents.get(agentId);
    if (!agent) return;
    agent.unread++;
    renderTabs();
}

/**
 * Get the messages container for a specific agent
 */
export function getAgentMessagesEl(agentId) {
    const agent = state.agents.get(agentId);
    return agent ? agent.messagesEl : null;
}

/**
 * Get the active agent
 */
export function getActiveAgent() {
    return state.agents.get(state.activeAgentId);
}

/**
 * Sync the processing UI (buttons, etc.) with the agent's state.
 * This is called when switching tabs and when agent processing state changes.
 */
export function syncProcessingUI(agent) {
    if (!agent) agent = getActiveAgent();
    if (!agent) return;

    // Only update UI if this is the active agent
    if (agent.id !== state.activeAgentId) return;

    if (agent.isProcessing) {
        dom.recordBtn.textContent = t('status.rainWorking');
        dom.recordBtn.classList.add('processing');
        dom.recordBtn.disabled = true;
        dom.sendTextBtn.disabled = true;
        dom.interruptBtn.classList.remove('hidden');

        // Restore interrupt button state based on agent's pending status
        if (agent.interruptPending) {
            dom.interruptBtn.textContent = t('chat.forceStop');
            dom.interruptBtn.disabled = false;
            dom.interruptBtn.classList.remove('stopping');
            dom.interruptBtn.classList.add('force');
        } else {
            dom.interruptBtn.textContent = t('chat.stop');
            dom.interruptBtn.disabled = false;
            dom.interruptBtn.classList.remove('force', 'stopping');
        }
    } else {
        dom.recordBtn.textContent = t('chat.holdToSpeak');
        dom.recordBtn.className = '';
        dom.recordBtn.disabled = false;
        dom.sendTextBtn.disabled = false;
        dom.interruptBtn.classList.add('hidden');
        dom.interruptBtn.classList.remove('force', 'stopping');
        dom.interruptBtn.textContent = t('chat.stop');
        dom.interruptBtn.disabled = false;
    }
}

/**
 * Render the tab bar
 */
function renderTabs() {
    const tabList = dom.tabList;
    if (!tabList) return;
    tabList.innerHTML = '';

    for (const [id, agent] of state.agents) {
        const tab = document.createElement('div');
        tab.className = 'tab' + (id === state.activeAgentId ? ' active' : '');
        tab.dataset.agentId = id;

        // Status dot
        const dot = document.createElement('span');
        dot.className = 'tab-dot ' + agent.status;
        tab.appendChild(dot);

        // Label
        const label = document.createElement('span');
        label.className = 'tab-label';
        label.textContent = agent.cwd
            ? agent.cwd.split(/[/\\]/).pop()
            : agent.label;
        tab.appendChild(label);

        // Unread badge
        if (agent.unread > 0 && id !== state.activeAgentId) {
            const badge = document.createElement('span');
            badge.className = 'tab-badge';
            badge.textContent = agent.unread > 99 ? '99+' : agent.unread;
            tab.appendChild(badge);
        }

        // Close button (only if more than one tab)
        if (state.agents.size > 1) {
            const close = document.createElement('span');
            close.className = 'tab-close';
            close.textContent = '\u00d7';
            close.addEventListener('click', (e) => {
                e.stopPropagation();
                closeAgent(id);
            });
            tab.appendChild(close);
        }

        tab.addEventListener('click', () => switchToAgent(id));
        tabList.appendChild(tab);
    }
}

/**
 * Show the tab bar
 */
export function showTabBar() {
    dom.tabBar.classList.remove('hidden');
}

/**
 * Re-initialize agents on the server after WebSocket reconnection.
 * For each agent that already has a cwd, send a set_cwd to re-register.
 */
export function reinitAgentsOnServer() {
    for (const [agentId, agent] of state.agents) {
        if (agent.cwd) {
            wsSend({ type: 'set_cwd', path: agent.cwd, agent_id: agentId });
        }
        // Reset processing state since server lost context
        if (agent.isProcessing) {
            agent.isProcessing = false;
            agent.interruptPending = false;
            if (agent.interruptTimer) {
                clearTimeout(agent.interruptTimer);
                agent.interruptTimer = null;
            }
            setAgentStatus(agentId, 'idle');
        }
    }
    // Sync UI for the currently active agent
    syncProcessingUI(getActiveAgent());
}

/**
 * Handle "+" button — opens file browser for a new agent
 */
export function initTabs() {
    dom.tabBar = document.getElementById('tab-bar');
    dom.tabList = document.getElementById('tab-list');
    dom.newAgentBtn = document.getElementById('new-agent-btn');

    dom.newAgentBtn.addEventListener('click', () => {
        // Create a new agent and open the file browser for it
        const newId = createAgent();
        switchToAgent(newId);

        // Show file browser for the new agent
        dom.chatPanel.classList.add('hidden');
        dom.fileBrowser.classList.remove('hidden');

        // Use the NEW agent's browse path (starts at '~'), not the previous agent's
        const newAgent = state.agents.get(newId);
        const startPath = newAgent ? newAgent.currentBrowsePath : '~';

        // Import dynamically to avoid circular dependency
        import('./browser.js').then(({ loadDir }) => {
            loadDir(startPath);
        });
    });

    ensureDefaultAgent();
}
