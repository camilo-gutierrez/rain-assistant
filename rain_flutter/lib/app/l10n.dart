/// Localization strings for Rain Assistant (en/es).
class L10n {
  static const supported = ['en', 'es'];

  static String t(String key, String lang, [Map<String, String>? params]) {
    final map = lang == 'es' ? _es : _en;
    var value = map[key] ?? _en[key] ?? key;
    if (params != null) {
      for (final e in params.entries) {
        value = value.replaceAll('{${e.key}}', e.value);
      }
    }
    return value;
  }

  static const _en = <String, String>{
    // Status
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

    // PIN
    'pin.title': 'Rain Assistant',
    'pin.instruction': 'Enter the PIN shown on your server console',
    'pin.submit': 'Enter',
    'pin.error': 'Incorrect PIN',
    'pin.tooManyAttempts': 'Too many attempts. Try again in {time}',
    'pin.incorrectRemaining': 'Incorrect PIN — {n} attempts remaining',
    'pin.incorrectRemainingOne': 'Incorrect PIN — 1 attempt remaining',

    // API Key
    'apiKey.title': 'Rain Assistant',
    'apiKey.instructionGeneric':
        'Enter your {provider} API key to connect. Get one at',
    'apiKey.show': 'Show',
    'apiKey.hide': 'Hide',
    'apiKey.savedInfo': 'Key saved from last session.',
    'apiKey.clear': 'Clear',
    'apiKey.connect': 'Connect',
    'apiKey.skip': 'Use without key (local mode)',
    'apiKey.personalAccount': 'Use personal account',
    'apiKey.personalAccountDesc': 'Use your Claude Max/Pro subscription',
    'apiKey.personalAccountActive': 'Personal account detected',
    'apiKey.orEnterKey': 'Or enter an API key',
    'apiKey.checkingOAuth': 'Checking account...',

    // Provider
    'provider.model': 'Model',

    // File Browser
    'browser.title': 'Select Project Directory',
    'browser.loading': 'Loading...',
    'browser.empty': 'Empty directory',
    'browser.selectBtn': 'Select This Directory',

    // Chat
    'chat.inputPlaceholder': 'Type a message...',
    'chat.sendBtn': 'Send',
    'chat.recording': 'Recording... Release to Send',
    'chat.stop': 'Stop',
    'chat.stopping': 'Stopping...',
    'chat.forceStop': 'Force Stop',
    'chat.forceStopped': 'Force stopped.',
    'chat.showFullOutput': 'Show full output',
    'chat.selectDirFirst': 'Please select a project directory first.',
    'chat.sendError': 'Could not send — connection lost. Try again.',
    'chat.emptyState': 'Send a message to start',

    // Metrics
    'metrics.title': 'Usage Metrics',
    'metrics.refresh': 'Refresh',
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
    'metrics.usageByHour': 'Usage by Hour',
    'metrics.usageByDow': 'Usage by Day of Week',
    'metrics.dailySpend': 'Daily Spend (Last 30 Days)',
    'metrics.monthlySpend': 'Monthly Spend',
    'metrics.sessionsLabel': 'sessions',

    // Settings
    'settings.title': 'Settings',
    'settings.language': 'Language',
    'settings.theme': 'Theme',
    'settings.theme.dark': 'Dark',
    'settings.theme.light': 'Light',
    'settings.voiceLang': 'Voice Recognition',
    'settings.tts': 'Text-to-Speech',
    'settings.ttsEnabled': 'Enable TTS',
    'settings.ttsAutoPlay': 'Auto-play responses',
    'settings.ttsVoice': 'Voice',
    'settings.ttsVoice.esFemale': 'Spanish Female (Dalia)',
    'settings.ttsVoice.esMale': 'Spanish Male (Jorge)',
    'settings.ttsVoice.enFemale': 'English Female (Jenny)',
    'settings.ttsVoice.enMale': 'English Male (Guy)',
    'settings.provider': 'AI Provider',
    'settings.model': 'AI Model',
    'settings.logout': 'Logout',
    'settings.logoutConfirm': 'Are you sure you want to logout?',
    'settings.about': 'About',
    'settings.version': 'Version',

    // History
    'history.title': 'History',
    'history.loading': 'Loading...',
    'history.empty': 'No saved conversations',
    'history.count': '{n} of {max} conversations',
    'history.delete': 'Delete',
    'history.confirmDelete': 'Click again to confirm',
    'history.saveBtn': 'Save',
    'history.saving': 'Saving...',

    // Permissions
    'perm.requestTitle': 'Permission Required',
    'perm.levelYellow': 'Confirmation',
    'perm.levelRed': 'Dangerous Operation',
    'perm.approve': 'Approve',
    'perm.deny': 'Deny',
    'perm.enterPin': 'PIN',
    'perm.approved': 'Approved',
    'perm.denied': 'Denied',
    'perm.expired': 'Expired',
    'perm.details': 'Details',

    // Computer Use
    'cu.title': 'Computer Use',
    'cu.modeCoding': 'Coding',
    'cu.modeComputer': 'Computer',
    'cu.switchToCoding': 'Switch to Coding mode',
    'cu.switchToComputerUse': 'Switch to Computer Use mode',
    'cu.emergencyStop': 'EMERGENCY STOP',
    'cu.iteration': 'Step',
    'cu.liveDisplay': 'Live Display',
    'cu.resolution': 'Resolution',
    'cu.iterationProgress': 'Step {current}',
    'cu.noScreenshot': 'Waiting for screenshot...',
    'cu.tapToExpand': 'Tap to expand',

    // Model Switcher
    'modelSwitcher.keyConfigured': 'Key configured',
    'modelSwitcher.noKey': 'No API key',
    'modelSwitcher.appliesNext': 'Applies to next conversation',

    // Notifications
    'settings.notifications': 'Notifications',
    'settings.notifPermission': 'Permission requests',
    'settings.notifPermissionDesc':
        'Notify when Rain needs permission to run a tool',
    'settings.notifResult': 'Task completed',
    'settings.notifError': 'Errors',
    'settings.notifHaptic': 'Vibration',
    'settings.notifDialog': 'In-app alerts',
    'settings.notifDialogDesc':
        'Show dialog when permission is needed on another agent',

    // Toast
    'toast.connectionLost': 'Connection lost. Reconnecting...',
    'toast.connectionRestored': 'Connection restored',
    'toast.copySuccess': 'Copied to clipboard',
    'toast.saveSuccess': 'Conversation saved',
    'toast.saveFailed': 'Could not save conversation',
    'toast.clearSuccess': 'Conversation cleared',
    'toast.sendFailed': 'Could not send message',
    'toast.deletedConversation': 'Conversation deleted',

    // Agent
    'agent.new': 'New agent',
    'agent.delete': 'Delete agent',
    'agent.deleteConfirm': 'Delete "{name}"? Conversation will be lost.',
    'agent.cancel': 'Cancel',
    'agent.create': 'Create',
    'agent.nameHint': 'Agent name',
    'agent.selectDir': 'Select directory',
    'agent.useThis': 'Use this',

    // Agent Manager
    'agentMgr.title': 'Agent Manager',
    'agentMgr.count': '{n} of {max} agents',
    'agentMgr.empty': 'No agents running',
    'agentMgr.active': 'ACTIVE',
    'agentMgr.noDir': 'No directory selected',
    'agentMgr.rename': 'Rename',
    'agentMgr.statusIdle': 'Idle',
    'agentMgr.statusWorking': 'Working',
    'agentMgr.statusDone': 'Done',
    'agentMgr.statusError': 'Error',
    'agentMgr.switchTo': 'Switch to this agent',

    // Server URL Screen
    'serverUrl.subtitle': 'Connect to your Rain server',
    'serverUrl.label': 'Server URL',
    'serverUrl.hint': 'https://rain.example.com',
    'serverUrl.errorEmpty': 'Enter the server URL',
    'serverUrl.errorProtocol': 'URL must start with http:// or https://',
    'serverUrl.errorUnreachable': 'Could not connect to server',
    'serverUrl.helperText': 'Enter the URL where your Rain server is running.\nE.g.: http://192.168.1.100:8000',
    'serverUrl.connect': 'Connect',

    // PIN Screen
    'pinScreen.title': 'Enter your PIN',
    'pinScreen.errorEmpty': 'Enter the PIN',
    'pinScreen.errorAuth': 'Authentication error',
    'pinScreen.locked': 'Locked for {min} minutes',
    'pinScreen.attemptsRemaining': '{n} attempt(s) remaining',
    'pinScreen.submit': 'Enter',
    'pinScreen.changeServer': 'Change server',

    // Months
    'month.0': 'Jan', 'month.1': 'Feb', 'month.2': 'Mar',
    'month.3': 'Apr', 'month.4': 'May', 'month.5': 'Jun',
    'month.6': 'Jul', 'month.7': 'Aug', 'month.8': 'Sep',
    'month.9': 'Oct', 'month.10': 'Nov', 'month.11': 'Dec',

    // Voice Mode
    'settings.voiceMode': 'Voice Mode',
    'settings.voiceMode.pushToTalk': 'Push to Talk',
    'settings.voiceMode.vad': 'Auto-detect (VAD)',
    'settings.voiceMode.talkMode': 'Talk Mode',
    'settings.voiceMode.wakeWord': 'Wake Word',
    'settings.vadSensitivity': 'VAD Sensitivity',
    'settings.silenceTimeout': 'Silence Timeout',
    'voice.listening': 'Listening...',
    'voice.recording': 'Recording...',
    'voice.transcribing': 'Transcribing...',
    'voice.processing': 'Processing...',
    'voice.speaking': 'Rain is speaking...',
    'voice.wakeListening': 'Listening for "Hey Rain"...',
    'voice.startTalkMode': 'Talk Mode',
    'voice.endConversation': 'End Conversation',

    // Days of week
    'dow.Monday': 'Mon', 'dow.Tuesday': 'Tue', 'dow.Wednesday': 'Wed',
    'dow.Thursday': 'Thu', 'dow.Friday': 'Fri', 'dow.Saturday': 'Sat',
    'dow.Sunday': 'Sun',
  };

  static const _es = <String, String>{
    // Status
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

    // PIN
    'pin.title': 'Rain Assistant',
    'pin.instruction': 'Ingresa el PIN que aparece en la consola del servidor',
    'pin.submit': 'Entrar',
    'pin.error': 'PIN incorrecto',
    'pin.tooManyAttempts': 'Demasiados intentos. Intenta en {time}',
    'pin.incorrectRemaining': 'PIN incorrecto — {n} intentos restantes',
    'pin.incorrectRemainingOne': 'PIN incorrecto — 1 intento restante',

    // API Key
    'apiKey.title': 'Rain Assistant',
    'apiKey.instructionGeneric':
        'Ingresa tu API key de {provider} para conectar. Obtén una en',
    'apiKey.show': 'Ver',
    'apiKey.hide': 'Ocultar',
    'apiKey.savedInfo': 'Key guardada de la sesión anterior.',
    'apiKey.clear': 'Borrar',
    'apiKey.connect': 'Conectar',
    'apiKey.skip': 'Usar sin key (modo local)',
    'apiKey.personalAccount': 'Usar cuenta personal',
    'apiKey.personalAccountDesc': 'Usa tu suscripción Claude Max/Pro',
    'apiKey.personalAccountActive': 'Cuenta personal detectada',
    'apiKey.orEnterKey': 'O ingresa una API key',
    'apiKey.checkingOAuth': 'Verificando cuenta...',

    // Provider
    'provider.model': 'Modelo',

    // File Browser
    'browser.title': 'Seleccionar Directorio del Proyecto',
    'browser.loading': 'Cargando...',
    'browser.empty': 'Directorio vacío',
    'browser.selectBtn': 'Seleccionar Este Directorio',

    // Chat
    'chat.inputPlaceholder': 'Escribe un mensaje...',
    'chat.sendBtn': 'Enviar',
    'chat.recording': 'Grabando... Suelta para Enviar',
    'chat.stop': 'Detener',
    'chat.stopping': 'Deteniendo...',
    'chat.forceStop': 'Forzar Parada',
    'chat.forceStopped': 'Detenido forzosamente.',
    'chat.showFullOutput': 'Ver salida completa',
    'chat.selectDirFirst': 'Selecciona un directorio de proyecto primero.',
    'chat.sendError': 'No se pudo enviar — conexión perdida. Intenta de nuevo.',
    'chat.emptyState': 'Envía un mensaje para comenzar',

    // Metrics
    'metrics.title': 'Métricas de Uso',
    'metrics.refresh': 'Actualizar',
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
    'metrics.usageByHour': 'Uso por Hora',
    'metrics.usageByDow': 'Uso por Día de Semana',
    'metrics.dailySpend': 'Gasto Diario (Últimos 30 Días)',
    'metrics.monthlySpend': 'Gasto Mensual',
    'metrics.sessionsLabel': 'sesiones',

    // Settings
    'settings.title': 'Configuración',
    'settings.language': 'Idioma',
    'settings.theme': 'Tema',
    'settings.theme.dark': 'Oscuro',
    'settings.theme.light': 'Claro',
    'settings.voiceLang': 'Reconocimiento de Voz',
    'settings.tts': 'Texto a Voz',
    'settings.ttsEnabled': 'Activar TTS',
    'settings.ttsAutoPlay': 'Reproducir respuestas automáticamente',
    'settings.ttsVoice': 'Voz',
    'settings.ttsVoice.esFemale': 'Español Femenina (Dalia)',
    'settings.ttsVoice.esMale': 'Español Masculina (Jorge)',
    'settings.ttsVoice.enFemale': 'Inglés Femenina (Jenny)',
    'settings.ttsVoice.enMale': 'Inglés Masculina (Guy)',
    'settings.provider': 'Proveedor IA',
    'settings.model': 'Modelo IA',
    'settings.logout': 'Cerrar Sesión',
    'settings.logoutConfirm': '¿Seguro que quieres cerrar sesión?',
    'settings.about': 'Acerca de',
    'settings.version': 'Versión',

    // History
    'history.title': 'Historial',
    'history.loading': 'Cargando...',
    'history.empty': 'No hay conversaciones guardadas',
    'history.count': '{n} de {max} conversaciones',
    'history.delete': 'Eliminar',
    'history.confirmDelete': 'Click de nuevo para confirmar',
    'history.saveBtn': 'Guardar',
    'history.saving': 'Guardando...',

    // Permissions
    'perm.requestTitle': 'Permiso Requerido',
    'perm.levelYellow': 'Confirmación',
    'perm.levelRed': 'Operación Peligrosa',
    'perm.approve': 'Aprobar',
    'perm.deny': 'Denegar',
    'perm.enterPin': 'PIN',
    'perm.approved': 'Aprobado',
    'perm.denied': 'Denegado',
    'perm.expired': 'Expirado',
    'perm.details': 'Detalles',

    // Computer Use
    'cu.title': 'Uso de Computadora',
    'cu.modeCoding': 'Código',
    'cu.modeComputer': 'Computadora',
    'cu.switchToCoding': 'Cambiar a modo Código',
    'cu.switchToComputerUse': 'Cambiar a modo Computer Use',
    'cu.emergencyStop': 'PARADA DE EMERGENCIA',
    'cu.iteration': 'Paso',
    'cu.liveDisplay': 'Pantalla en vivo',
    'cu.resolution': 'Resolución',
    'cu.iterationProgress': 'Paso {current}',
    'cu.noScreenshot': 'Esperando captura...',
    'cu.tapToExpand': 'Toca para expandir',

    // Model Switcher
    'modelSwitcher.keyConfigured': 'Key configurada',
    'modelSwitcher.noKey': 'Sin API key',
    'modelSwitcher.appliesNext': 'Se aplica a la siguiente conversación',

    // Notificaciones
    'settings.notifications': 'Notificaciones',
    'settings.notifPermission': 'Solicitudes de permiso',
    'settings.notifPermissionDesc':
        'Notificar cuando Rain necesite permiso para ejecutar una herramienta',
    'settings.notifResult': 'Tarea completada',
    'settings.notifError': 'Errores',
    'settings.notifHaptic': 'Vibración',
    'settings.notifDialog': 'Alertas en la app',
    'settings.notifDialogDesc':
        'Mostrar diálogo cuando se necesite permiso en otro agente',

    // Toast
    'toast.connectionLost': 'Conexión perdida. Reconectando...',
    'toast.connectionRestored': 'Conexión restaurada',
    'toast.copySuccess': 'Copiado al portapapeles',
    'toast.saveSuccess': 'Conversación guardada',
    'toast.saveFailed': 'No se pudo guardar la conversación',
    'toast.clearSuccess': 'Conversación limpiada',
    'toast.sendFailed': 'No se pudo enviar el mensaje',
    'toast.deletedConversation': 'Conversación eliminada',

    // Agent
    'agent.new': 'Nuevo agente',
    'agent.delete': 'Eliminar agente',
    'agent.deleteConfirm': '¿Eliminar "{name}"? Se perderá la conversación.',
    'agent.cancel': 'Cancelar',
    'agent.create': 'Crear',
    'agent.nameHint': 'Nombre del agente',
    'agent.selectDir': 'Seleccionar directorio',
    'agent.useThis': 'Usar este',

    // Agent Manager
    'agentMgr.title': 'Administrador de Agentes',
    'agentMgr.count': '{n} de {max} agentes',
    'agentMgr.empty': 'No hay agentes ejecutándose',
    'agentMgr.active': 'ACTIVO',
    'agentMgr.noDir': 'Sin directorio seleccionado',
    'agentMgr.rename': 'Renombrar',
    'agentMgr.statusIdle': 'Inactivo',
    'agentMgr.statusWorking': 'Trabajando',
    'agentMgr.statusDone': 'Listo',
    'agentMgr.statusError': 'Error',
    'agentMgr.switchTo': 'Cambiar a este agente',

    // Server URL Screen
    'serverUrl.subtitle': 'Conecta con tu servidor Rain',
    'serverUrl.label': 'URL del servidor',
    'serverUrl.hint': 'https://rain.ejemplo.com',
    'serverUrl.errorEmpty': 'Ingresa la URL del servidor',
    'serverUrl.errorProtocol': 'La URL debe comenzar con http:// o https://',
    'serverUrl.errorUnreachable': 'No se pudo conectar al servidor',
    'serverUrl.helperText': 'Ingresa la URL donde corre tu servidor Rain.\nEj: http://192.168.1.100:8000',
    'serverUrl.connect': 'Conectar',

    // PIN Screen
    'pinScreen.title': 'Ingresa tu PIN',
    'pinScreen.errorEmpty': 'Ingresa el PIN',
    'pinScreen.errorAuth': 'Error de autenticación',
    'pinScreen.locked': 'Bloqueado por {min} minutos',
    'pinScreen.attemptsRemaining': '{n} intento(s) restante(s)',
    'pinScreen.submit': 'Ingresar',
    'pinScreen.changeServer': 'Cambiar servidor',

    // Months
    'month.0': 'Ene', 'month.1': 'Feb', 'month.2': 'Mar',
    'month.3': 'Abr', 'month.4': 'May', 'month.5': 'Jun',
    'month.6': 'Jul', 'month.7': 'Ago', 'month.8': 'Sep',
    'month.9': 'Oct', 'month.10': 'Nov', 'month.11': 'Dic',

    // Voice Mode
    'settings.voiceMode': 'Modo de Voz',
    'settings.voiceMode.pushToTalk': 'Mantener para Hablar',
    'settings.voiceMode.vad': 'Auto-detectar (VAD)',
    'settings.voiceMode.talkMode': 'Modo Conversación',
    'settings.voiceMode.wakeWord': 'Palabra Clave',
    'settings.vadSensitivity': 'Sensibilidad VAD',
    'settings.silenceTimeout': 'Tiempo de Silencio',
    'voice.listening': 'Escuchando...',
    'voice.recording': 'Grabando...',
    'voice.transcribing': 'Transcribiendo...',
    'voice.processing': 'Procesando...',
    'voice.speaking': 'Rain está hablando...',
    'voice.wakeListening': 'Escuchando "Hey Rain"...',
    'voice.startTalkMode': 'Modo Conversación',
    'voice.endConversation': 'Terminar Conversación',

    // Days of week
    'dow.Monday': 'Lun', 'dow.Tuesday': 'Mar', 'dow.Wednesday': 'Mié',
    'dow.Thursday': 'Jue', 'dow.Friday': 'Vie', 'dow.Saturday': 'Sáb',
    'dow.Sunday': 'Dom',
  };
}
