// ---------------------------------------------------------------------------
// Settings Panel — language, theme, voice recognition language
// ---------------------------------------------------------------------------

import { state, dom } from './app.js';
import { setLang, getLang, applyTranslations } from './translations.js';
import { setTheme, getTheme } from './theme.js';
import { wsSend } from './websocket.js';
import { closeMetrics } from './metrics.js';

let _settingsOpen = false;

// ---------------------------------------------------------------------------
// Toggle / Close
// ---------------------------------------------------------------------------

export function toggleSettings() {
    _settingsOpen = !_settingsOpen;
    if (_settingsOpen) {
        // Close metrics if open
        closeMetrics();

        // Hide other panels, show settings
        dom.chatPanel.classList.add('hidden');
        dom.fileBrowser.classList.add('hidden');
        dom.metricsPanel.classList.add('hidden');
        dom.settingsPanel.classList.remove('hidden');

        // Sync selectors with current state
        document.getElementById('settings-language').value = getLang();
        document.getElementById('settings-voice-lang').value =
            localStorage.getItem('rain-voice-lang') || 'es';

        // Sync theme buttons
        const currentTheme = getTheme();
        document.querySelectorAll('.theme-option').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.themeValue === currentTheme);
        });
    } else {
        dom.settingsPanel.classList.add('hidden');
        // Restore previous panel
        const agent = state.agents.get(state.activeAgentId);
        if (agent && agent.cwd) {
            dom.chatPanel.classList.remove('hidden');
        } else {
            dom.fileBrowser.classList.remove('hidden');
        }
    }
}

export function closeSettings() {
    if (_settingsOpen) toggleSettings();
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------

export function initSettings() {
    dom.settingsPanel  = document.getElementById('settings-panel');
    dom.settingsToggle = document.getElementById('settings-toggle');

    // Toggle button
    dom.settingsToggle.addEventListener('click', toggleSettings);

    // Close button
    document.getElementById('settings-close-btn').addEventListener('click', toggleSettings);

    // --- Language selector ---
    const langSelect = document.getElementById('settings-language');
    langSelect.value = getLang();
    langSelect.addEventListener('change', () => {
        setLang(langSelect.value);
    });

    // --- Theme selector (buttons) ---
    document.querySelectorAll('.theme-option').forEach(btn => {
        btn.addEventListener('click', () => {
            const theme = btn.dataset.themeValue;
            setTheme(theme);
        });
    });

    // --- Voice recognition language ---
    const voiceLangSelect = document.getElementById('settings-voice-lang');
    const savedVoiceLang = localStorage.getItem('rain-voice-lang') || 'es';
    voiceLangSelect.value = savedVoiceLang;

    voiceLangSelect.addEventListener('change', () => {
        const lang = voiceLangSelect.value;
        localStorage.setItem('rain-voice-lang', lang);
        // Tell the server to update the transcriber language
        wsSend({ type: 'set_transcription_lang', lang });
    });
}
