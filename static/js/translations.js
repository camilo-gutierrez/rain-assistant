// ---------------------------------------------------------------------------
// i18n — Lightweight translation system (English / Spanish)
// ---------------------------------------------------------------------------

const translations = {
    en: {
        // Status bar
        'status.connecting': 'Connecting...',
        'status.connected': 'Connected',
        'status.disconnected': 'Disconnected',
        'status.ready': 'Ready',
        'status.transcribing': 'Transcribing...',
        'status.rainWorking': 'Rain is working...',
        'status.recordingTooShort': 'Recording too short',
        'status.noSpeechDetected': 'No speech detected',
        'status.transcriptionFailed': 'Transcription failed',
        'status.selectProjectFirst': 'Select a project directory first',
        'status.connectionError': 'Connection error',

        // Status bar buttons
        'btn.metricsToggle.title': 'Usage Metrics',
        'btn.settings.title': 'Settings',
        'btn.newAgent.title': 'New agent',

        // PIN panel
        'pin.title': 'Rain Assistant',
        'pin.instruction': 'Enter the PIN shown on your server console',
        'pin.submit': 'Enter',
        'pin.error': 'Incorrect PIN',
        'pin.tooManyAttempts': 'Too many attempts. Try again in {time}',
        'pin.incorrectRemaining': 'Incorrect PIN — {n} attempts remaining',
        'pin.incorrectRemainingOne': 'Incorrect PIN — 1 attempt remaining',

        // API key panel
        'apiKey.title': 'Rain Assistant',
        'apiKey.instruction': 'Enter your Anthropic API key to connect. You can get one at',
        'apiKey.show': 'Show',
        'apiKey.hide': 'Hide',
        'apiKey.savedInfo': 'Key saved from last session.',
        'apiKey.clear': 'Clear',
        'apiKey.connect': 'Connect',
        'apiKey.skip': 'Use without key (local mode)',

        // File browser
        'browser.title': 'Select Project Directory',
        'browser.loading': 'Loading...',
        'browser.selectBtn': 'Select This Directory',

        // Chat panel
        'chat.clearBtn': 'Clear',
        'chat.changeBtn': 'Change',
        'chat.inputPlaceholder': 'Type a message...',
        'chat.sendBtn': 'Send',
        'chat.holdToSpeak': 'Hold to Speak',
        'chat.recording': 'Recording... Release to Send',
        'chat.micUnavailable': 'Mic unavailable',
        'chat.stop': 'Stop',
        'chat.stopping': 'Stopping...',
        'chat.forceStop': 'Force Stop',
        'chat.forceStopped': 'Force stopped.',
        'chat.showFullOutput': 'Show full output',
        'chat.selectDirFirst': 'Please select a project directory first.',

        // Metrics panel
        'metrics.title': 'Usage Metrics',
        'metrics.refresh': 'Refresh',
        'metrics.close': 'Close',
        'metrics.loading': 'Loading metrics...',
        'metrics.noData': 'No metrics data available.',
        'metrics.totalSpent': 'Total Spent',
        'metrics.sessions': 'Sessions',
        'metrics.avgDuration': 'Avg. Duration',
        'metrics.totalTurns': 'Total Turns',
        'metrics.today': 'Today',
        'metrics.week': 'Week',
        'metrics.month': 'Month',
        'metrics.avgCost': 'Avg cost',
        'metrics.inputTokens': 'Input Tokens',
        'metrics.outputTokens': 'Output Tokens',
        'metrics.rateLimits': 'API Rate Limits (Real Time)',
        'metrics.model': 'Model',
        'metrics.updated': 'Updated',
        'metrics.usageByHour': 'Usage by Hour',
        'metrics.usageByDow': 'Usage by Day of Week',
        'metrics.dailySpend': 'Daily Spend (Last 30 Days)',
        'metrics.monthlySpend': 'Monthly Spend',
        'metrics.sessionsLabel': 'sessions',

        // Settings panel
        'settings.title': 'Settings',
        'settings.close': 'Close',
        'settings.language': 'Language',
        'settings.theme': 'Theme',
        'settings.theme.dark': 'Cyberpunk',
        'settings.theme.light': 'Light',
        'settings.theme.ocean': 'Ocean',
        'settings.voiceLang': 'Voice Recognition',

        // Months (for metrics)
        'month.0': 'Jan', 'month.1': 'Feb', 'month.2': 'Mar', 'month.3': 'Apr',
        'month.4': 'May', 'month.5': 'Jun', 'month.6': 'Jul', 'month.7': 'Aug',
        'month.8': 'Sep', 'month.9': 'Oct', 'month.10': 'Nov', 'month.11': 'Dec',
    },
    es: {
        // Status bar
        'status.connecting': 'Conectando...',
        'status.connected': 'Conectado',
        'status.disconnected': 'Desconectado',
        'status.ready': 'Listo',
        'status.transcribing': 'Transcribiendo...',
        'status.rainWorking': 'Rain está trabajando...',
        'status.recordingTooShort': 'Grabación muy corta',
        'status.noSpeechDetected': 'No se detectó voz',
        'status.transcriptionFailed': 'Error en transcripción',
        'status.selectProjectFirst': 'Selecciona un directorio primero',
        'status.connectionError': 'Error de conexión',

        // Status bar buttons
        'btn.metricsToggle.title': 'Métricas de uso',
        'btn.settings.title': 'Configuración',
        'btn.newAgent.title': 'Nuevo agente',

        // PIN panel
        'pin.title': 'Rain Assistant',
        'pin.instruction': 'Ingresa el PIN que aparece en la consola del servidor',
        'pin.submit': 'Entrar',
        'pin.error': 'PIN incorrecto',
        'pin.tooManyAttempts': 'Demasiados intentos. Intenta en {time}',
        'pin.incorrectRemaining': 'PIN incorrecto — {n} intentos restantes',
        'pin.incorrectRemainingOne': 'PIN incorrecto — 1 intento restante',

        // API key panel
        'apiKey.title': 'Rain Assistant',
        'apiKey.instruction': 'Ingresa tu API key de Anthropic para conectar. Obtén una en',
        'apiKey.show': 'Ver',
        'apiKey.hide': 'Ocultar',
        'apiKey.savedInfo': 'Key guardada de la sesión anterior.',
        'apiKey.clear': 'Borrar',
        'apiKey.connect': 'Conectar',
        'apiKey.skip': 'Usar sin key (modo local)',

        // File browser
        'browser.title': 'Seleccionar Directorio del Proyecto',
        'browser.loading': 'Cargando...',
        'browser.selectBtn': 'Seleccionar Este Directorio',

        // Chat panel
        'chat.clearBtn': 'Limpiar',
        'chat.changeBtn': 'Cambiar',
        'chat.inputPlaceholder': 'Escribe un mensaje...',
        'chat.sendBtn': 'Enviar',
        'chat.holdToSpeak': 'Mantén para Hablar',
        'chat.recording': 'Grabando... Suelta para Enviar',
        'chat.micUnavailable': 'Micrófono no disponible',
        'chat.stop': 'Detener',
        'chat.stopping': 'Deteniendo...',
        'chat.forceStop': 'Forzar Parada',
        'chat.forceStopped': 'Detenido forzosamente.',
        'chat.showFullOutput': 'Ver salida completa',
        'chat.selectDirFirst': 'Selecciona un directorio de proyecto primero.',

        // Metrics panel
        'metrics.title': 'Métricas de Uso',
        'metrics.refresh': 'Actualizar',
        'metrics.close': 'Cerrar',
        'metrics.loading': 'Cargando métricas...',
        'metrics.noData': 'No hay datos de métricas disponibles.',
        'metrics.totalSpent': 'Total Gastado',
        'metrics.sessions': 'Sesiones',
        'metrics.avgDuration': 'Duración Prom.',
        'metrics.totalTurns': 'Total Turnos',
        'metrics.today': 'Hoy',
        'metrics.week': 'Semana',
        'metrics.month': 'Mes',
        'metrics.avgCost': 'Costo prom',
        'metrics.inputTokens': 'Tokens Entrada',
        'metrics.outputTokens': 'Tokens Salida',
        'metrics.rateLimits': 'Límites de API (Tiempo Real)',
        'metrics.model': 'Modelo',
        'metrics.updated': 'Actualizado',
        'metrics.usageByHour': 'Uso por Hora',
        'metrics.usageByDow': 'Uso por Día de Semana',
        'metrics.dailySpend': 'Gasto Diario (Últimos 30 Días)',
        'metrics.monthlySpend': 'Gasto Mensual',
        'metrics.sessionsLabel': 'sesiones',

        // Settings panel
        'settings.title': 'Configuración',
        'settings.close': 'Cerrar',
        'settings.language': 'Idioma',
        'settings.theme': 'Tema',
        'settings.theme.dark': 'Cyberpunk',
        'settings.theme.light': 'Claro',
        'settings.theme.ocean': 'Océano',
        'settings.voiceLang': 'Reconocimiento de Voz',

        // Months (for metrics)
        'month.0': 'Ene', 'month.1': 'Feb', 'month.2': 'Mar', 'month.3': 'Abr',
        'month.4': 'May', 'month.5': 'Jun', 'month.6': 'Jul', 'month.7': 'Ago',
        'month.8': 'Sep', 'month.9': 'Oct', 'month.10': 'Nov', 'month.11': 'Dic',
    },
};

let _currentLang = 'es';

/**
 * Get current language code ('en' or 'es')
 */
export function getLang() {
    return _currentLang;
}

/**
 * Set language, persist to localStorage, and re-apply translations.
 */
export function setLang(lang) {
    if (!translations[lang]) lang = 'es';
    _currentLang = lang;
    localStorage.setItem('rain-lang', lang);
    document.documentElement.setAttribute('lang', lang);
    applyTranslations();
}

/**
 * Translate a key.  Optional params object for interpolation:
 *   t('pin.tooManyAttempts', { time: '5m 0s' })
 */
export function t(key, params) {
    let str = (translations[_currentLang] && translations[_currentLang][key])
           || (translations.es[key])
           || key;
    if (params) {
        for (const [k, v] of Object.entries(params)) {
            str = str.replace(`{${k}}`, v);
        }
    }
    return str;
}

/**
 * Scan all DOM elements with data-i18n* attributes and update their text.
 *   data-i18n="key"                → sets textContent
 *   data-i18n-placeholder="key"    → sets placeholder
 *   data-i18n-title="key"          → sets title attribute
 */
export function applyTranslations() {
    document.querySelectorAll('[data-i18n]').forEach(el => {
        el.textContent = t(el.dataset.i18n);
    });
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
        el.placeholder = t(el.dataset.i18nPlaceholder);
    });
    document.querySelectorAll('[data-i18n-title]').forEach(el => {
        el.title = t(el.dataset.i18nTitle);
    });
}

/**
 * Initialize: read saved language from localStorage and apply.
 */
export function initTranslations() {
    const saved = localStorage.getItem('rain-lang') || 'es';
    _currentLang = saved;
    document.documentElement.setAttribute('lang', _currentLang);
    applyTranslations();
}
