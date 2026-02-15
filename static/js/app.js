// ---------------------------------------------------------------------------
// Shared state, DOM refs, constants, and bootstrap
// ---------------------------------------------------------------------------

export const state = {
    ws: null,
    reconnectTimer: null,
    authToken: sessionStorage.getItem('rain-token') || null,
    currentBrowsePath: '~',
    currentCwd: null,
    mediaRecorder: null,
    audioChunks: [],
    isRecording: false,
    isProcessing: false,
    interruptPending: false,
    currentAssistantEl: null,
    currentStreamText: '',
    usingApiKey: false,
    notificationsEnabled: false,
    swRegistration: null,
    tabFocused: true,
    unreadCount: 0,
};

export const API = window.location.origin + '/api';
export const WS_URL = (window.location.protocol === 'https:' ? 'wss://' : 'ws://') + window.location.host + '/ws';
export const ORIGINAL_TITLE = 'Rain Assistant';

// DOM references — populated by initDom()
export const dom = {};

function initDom() {
    dom.statusDot     = document.getElementById('connection-dot');
    dom.statusText    = document.getElementById('status-text');
    dom.pinPanel      = document.getElementById('pin-panel');
    dom.pinInput      = document.getElementById('pin-input');
    dom.pinSubmitBtn  = document.getElementById('pin-submit-btn');
    dom.pinError      = document.getElementById('pin-error');
    dom.apiKeyPanel   = document.getElementById('api-key-panel');
    dom.apiKeyInput   = document.getElementById('api-key-input');
    dom.toggleKeyVis  = document.getElementById('toggle-key-vis');
    dom.connectApiBtn = document.getElementById('connect-api-btn');
    dom.skipApiBtn    = document.getElementById('skip-api-btn');
    dom.savedKeyInfo  = document.getElementById('saved-key-info');
    dom.clearKeyBtn   = document.getElementById('clear-key-btn');
    dom.fileBrowser   = document.getElementById('file-browser');
    dom.chatPanel     = document.getElementById('chat-panel');
    dom.currentPathEl = document.getElementById('current-path');
    dom.fileList      = document.getElementById('file-list');
    dom.selectDirBtn  = document.getElementById('select-dir-btn');
    dom.projectNameEl = document.getElementById('project-name');
    dom.changeDirBtn  = document.getElementById('change-dir-btn');
    dom.clearHistBtn  = document.getElementById('clear-history-btn');
    dom.chatMessages  = document.getElementById('chat-messages');
    dom.recordBtn     = document.getElementById('record-btn');
    dom.interruptBtn  = document.getElementById('interrupt-btn');
    dom.textInput     = document.getElementById('text-input');
    dom.sendTextBtn   = document.getElementById('send-text-btn');
}

export function authHeaders() {
    return state.authToken ? { 'Authorization': 'Bearer ' + state.authToken } : {};
}

export function setStatus(statusState, text) {
    dom.statusDot.className = '';
    if (statusState === 'connected' || statusState === 'ready') {
        dom.statusDot.classList.add('connected');
    } else if (statusState === 'error') {
        dom.statusDot.classList.add('error');
    }
    dom.statusText.textContent = text;
}

// ---------------------------------------------------------------------------
// Bootstrap
// ---------------------------------------------------------------------------

import { migrateStorageKeys, initAuth } from './auth.js';
import { initTheme } from './theme.js';
import { initNotifications } from './notifications.js';
import { connectWS } from './websocket.js';
import { initRecorder } from './recorder.js';
import { initBrowser } from './browser.js';
import { initChat } from './chat.js';

function init() {
    migrateStorageKeys();
    initDom();
    initTheme();
    initAuth();
    initBrowser();
    initChat();
    initRecorder();
    initNotifications();

    if (state.authToken) {
        dom.pinPanel.classList.add('hidden');
        dom.apiKeyPanel.classList.remove('hidden');
        connectWS();
    }
}

document.addEventListener('DOMContentLoaded', init);
