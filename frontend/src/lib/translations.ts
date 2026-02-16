import type { Language } from "./types";

const translations: Record<Language, Record<string, string>> = {
  en: {
    // Status bar
    "status.connecting": "Connecting...",
    "status.connected": "Connected",
    "status.disconnected": "Disconnected",
    "status.ready": "Ready",
    "status.transcribing": "Transcribing...",
    "status.rainWorking": "Rain is working...",
    "status.recordingTooShort": "Recording too short",
    "status.noSpeechDetected": "No speech detected",
    "status.transcriptionFailed": "Transcription failed",
    "status.selectProjectFirst": "Select a project directory first",
    "status.connectionError": "Connection error",

    // Status bar buttons
    "btn.metricsToggle.title": "Usage Metrics",
    "btn.settings.title": "Settings",
    "btn.newAgent.title": "New agent",

    // PIN panel
    "pin.title": "Rain Assistant",
    "pin.instruction": "Enter the PIN shown on your server console",
    "pin.submit": "Enter",
    "pin.error": "Incorrect PIN",
    "pin.tooManyAttempts": "Too many attempts. Try again in {time}",
    "pin.incorrectRemaining": "Incorrect PIN — {n} attempts remaining",
    "pin.incorrectRemainingOne": "Incorrect PIN — 1 attempt remaining",

    // API key panel
    "apiKey.title": "Rain Assistant",
    "apiKey.instruction":
      "Enter your Anthropic API key to connect. You can get one at",
    "apiKey.show": "Show",
    "apiKey.hide": "Hide",
    "apiKey.savedInfo": "Key saved from last session.",
    "apiKey.clear": "Clear",
    "apiKey.connect": "Connect",
    "apiKey.skip": "Use without key (local mode)",

    // File browser
    "browser.title": "Select Project Directory",
    "browser.loading": "Loading...",
    "browser.selectBtn": "Select This Directory",

    // Chat panel
    "chat.clearBtn": "Clear",
    "chat.changeBtn": "Change",
    "chat.inputPlaceholder": "Type a message...",
    "chat.sendBtn": "Send",
    "chat.holdToSpeak": "Hold to Speak",
    "chat.recording": "Recording... Release to Send",
    "chat.micUnavailable": "Mic unavailable",
    "chat.stop": "Stop",
    "chat.stopping": "Stopping...",
    "chat.forceStop": "Force Stop",
    "chat.forceStopped": "Force stopped.",
    "chat.showFullOutput": "Show full output",
    "chat.selectDirFirst": "Please select a project directory first.",
    "chat.sendError": "Could not send — connection lost. Try again.",

    // Metrics panel
    "metrics.title": "Usage Metrics",
    "metrics.refresh": "Refresh",
    "metrics.close": "Close",
    "metrics.loading": "Loading metrics...",
    "metrics.noData": "No metrics data available.",
    "metrics.totalSpent": "Total Spent",
    "metrics.sessions": "Sessions",
    "metrics.avgDuration": "Avg. Duration",
    "metrics.totalTurns": "Total Turns",
    "metrics.today": "Today",
    "metrics.week": "Week",
    "metrics.month": "Month",
    "metrics.avgCost": "Avg cost",
    "metrics.inputTokens": "Input Tokens",
    "metrics.outputTokens": "Output Tokens",
    "metrics.rateLimits": "API Rate Limits (Real Time)",
    "metrics.model": "Model",
    "metrics.updated": "Updated",
    "metrics.usageByHour": "Usage by Hour",
    "metrics.usageByDow": "Usage by Day of Week",
    "metrics.dailySpend": "Daily Spend (Last 30 Days)",
    "metrics.monthlySpend": "Monthly Spend",
    "metrics.sessionsLabel": "sessions",

    // Settings panel
    "settings.title": "Settings",
    "settings.close": "Close",
    "settings.language": "Language",
    "settings.theme": "Theme",
    "settings.theme.dark": "Dark",
    "settings.theme.light": "Light",
    "settings.voiceLang": "Voice Recognition",

    // TTS settings
    "settings.tts": "Text-to-Speech",
    "settings.ttsEnabled": "Enable TTS",
    "settings.ttsAutoPlay": "Auto-play responses",
    "settings.ttsVoice": "Voice",
    "settings.ttsVoice.esFemale": "Spanish Female (Dalia)",
    "settings.ttsVoice.esMale": "Spanish Male (Jorge)",
    "settings.ttsVoice.enFemale": "English Female (Jenny)",
    "settings.ttsVoice.enMale": "English Male (Guy)",
    "tts.play": "Play",
    "tts.stop": "Stop",
    "tts.loading": "Loading audio...",

    // Sidebar
    "sidebar.newChat": "New conversation",
    "sidebar.emptyHint": "Your conversations will appear here",

    // History sidebar
    "btn.history.title": "Conversation History",
    "history.title": "History",
    "history.loading": "Loading...",
    "history.empty": "No saved conversations",
    "history.count": "{n} of {max} conversations",
    "history.delete": "Delete",
    "history.confirmDelete": "Click again to confirm",
    "history.saveBtn": "Save",
    "history.saving": "Saving...",

    // Permissions
    "perm.requestTitle": "Permission Required",
    "perm.levelYellow": "Confirmation",
    "perm.levelRed": "Dangerous Operation",
    "perm.approve": "Approve",
    "perm.deny": "Deny",
    "perm.enterPin": "PIN",
    "perm.processing": "Processing...",
    "perm.approved": "Approved",
    "perm.denied": "Denied",
    "perm.expired": "Expired",

    // Computer Use
    "cu.title": "Computer Use",
    "cu.modeCoding": "Coding",
    "cu.modeComputer": "Computer",
    "cu.switchToCoding": "Switch to Coding mode",
    "cu.switchToComputerUse": "Switch to Computer Use mode",
    "cu.emergencyStop": "EMERGENCY STOP",
    "cu.iteration": "Step",
    "cu.permLevel": "COMPUTER ACCESS",

    // MCP Tools
    "mcp.title": "MCP Tools",
    "mcp.hub": "Hub",
    "mcp.email": "Email",
    "mcp.browser": "Browser",
    "mcp.smarthome": "Smart Home",

    // Months
    "month.0": "Jan", "month.1": "Feb", "month.2": "Mar", "month.3": "Apr",
    "month.4": "May", "month.5": "Jun", "month.6": "Jul", "month.7": "Aug",
    "month.8": "Sep", "month.9": "Oct", "month.10": "Nov", "month.11": "Dec",
  },
  es: {
    // Status bar
    "status.connecting": "Conectando...",
    "status.connected": "Conectado",
    "status.disconnected": "Desconectado",
    "status.ready": "Listo",
    "status.transcribing": "Transcribiendo...",
    "status.rainWorking": "Rain est\u00e1 trabajando...",
    "status.recordingTooShort": "Grabaci\u00f3n muy corta",
    "status.noSpeechDetected": "No se detect\u00f3 voz",
    "status.transcriptionFailed": "Error en transcripci\u00f3n",
    "status.selectProjectFirst": "Selecciona un directorio primero",
    "status.connectionError": "Error de conexi\u00f3n",

    // Status bar buttons
    "btn.metricsToggle.title": "M\u00e9tricas de uso",
    "btn.settings.title": "Configuraci\u00f3n",
    "btn.newAgent.title": "Nuevo agente",

    // PIN panel
    "pin.title": "Rain Assistant",
    "pin.instruction": "Ingresa el PIN que aparece en la consola del servidor",
    "pin.submit": "Entrar",
    "pin.error": "PIN incorrecto",
    "pin.tooManyAttempts": "Demasiados intentos. Intenta en {time}",
    "pin.incorrectRemaining": "PIN incorrecto \u2014 {n} intentos restantes",
    "pin.incorrectRemainingOne": "PIN incorrecto \u2014 1 intento restante",

    // API key panel
    "apiKey.title": "Rain Assistant",
    "apiKey.instruction":
      "Ingresa tu API key de Anthropic para conectar. Obt\u00e9n una en",
    "apiKey.show": "Ver",
    "apiKey.hide": "Ocultar",
    "apiKey.savedInfo": "Key guardada de la sesi\u00f3n anterior.",
    "apiKey.clear": "Borrar",
    "apiKey.connect": "Conectar",
    "apiKey.skip": "Usar sin key (modo local)",

    // File browser
    "browser.title": "Seleccionar Directorio del Proyecto",
    "browser.loading": "Cargando...",
    "browser.selectBtn": "Seleccionar Este Directorio",

    // Chat panel
    "chat.clearBtn": "Limpiar",
    "chat.changeBtn": "Cambiar",
    "chat.inputPlaceholder": "Escribe un mensaje...",
    "chat.sendBtn": "Enviar",
    "chat.holdToSpeak": "Mant\u00e9n para Hablar",
    "chat.recording": "Grabando... Suelta para Enviar",
    "chat.micUnavailable": "Micr\u00f3fono no disponible",
    "chat.stop": "Detener",
    "chat.stopping": "Deteniendo...",
    "chat.forceStop": "Forzar Parada",
    "chat.forceStopped": "Detenido forzosamente.",
    "chat.showFullOutput": "Ver salida completa",
    "chat.selectDirFirst": "Selecciona un directorio de proyecto primero.",
    "chat.sendError": "No se pudo enviar — conexión perdida. Intenta de nuevo.",

    // Metrics panel
    "metrics.title": "M\u00e9tricas de Uso",
    "metrics.refresh": "Actualizar",
    "metrics.close": "Cerrar",
    "metrics.loading": "Cargando m\u00e9tricas...",
    "metrics.noData": "No hay datos de m\u00e9tricas disponibles.",
    "metrics.totalSpent": "Total Gastado",
    "metrics.sessions": "Sesiones",
    "metrics.avgDuration": "Duraci\u00f3n Prom.",
    "metrics.totalTurns": "Total Turnos",
    "metrics.today": "Hoy",
    "metrics.week": "Semana",
    "metrics.month": "Mes",
    "metrics.avgCost": "Costo prom",
    "metrics.inputTokens": "Tokens Entrada",
    "metrics.outputTokens": "Tokens Salida",
    "metrics.rateLimits": "L\u00edmites de API (Tiempo Real)",
    "metrics.model": "Modelo",
    "metrics.updated": "Actualizado",
    "metrics.usageByHour": "Uso por Hora",
    "metrics.usageByDow": "Uso por D\u00eda de Semana",
    "metrics.dailySpend": "Gasto Diario (\u00daltimos 30 D\u00edas)",
    "metrics.monthlySpend": "Gasto Mensual",
    "metrics.sessionsLabel": "sesiones",

    // Settings panel
    "settings.title": "Configuraci\u00f3n",
    "settings.close": "Cerrar",
    "settings.language": "Idioma",
    "settings.theme": "Tema",
    "settings.theme.dark": "Oscuro",
    "settings.theme.light": "Claro",
    "settings.voiceLang": "Reconocimiento de Voz",

    // TTS settings
    "settings.tts": "Texto a Voz",
    "settings.ttsEnabled": "Activar TTS",
    "settings.ttsAutoPlay": "Reproducir respuestas autom\u00e1ticamente",
    "settings.ttsVoice": "Voz",
    "settings.ttsVoice.esFemale": "Espa\u00f1ol Femenina (Dalia)",
    "settings.ttsVoice.esMale": "Espa\u00f1ol Masculina (Jorge)",
    "settings.ttsVoice.enFemale": "Ingl\u00e9s Femenina (Jenny)",
    "settings.ttsVoice.enMale": "Ingl\u00e9s Masculina (Guy)",
    "tts.play": "Reproducir",
    "tts.stop": "Detener",
    "tts.loading": "Cargando audio...",

    // Sidebar
    "sidebar.newChat": "Nueva conversaci\u00f3n",
    "sidebar.emptyHint": "Tus conversaciones aparecer\u00e1n aqu\u00ed",

    // History sidebar
    "btn.history.title": "Historial de Conversaciones",
    "history.title": "Historial",
    "history.loading": "Cargando...",
    "history.empty": "No hay conversaciones guardadas",
    "history.count": "{n} de {max} conversaciones",
    "history.delete": "Eliminar",
    "history.confirmDelete": "Click de nuevo para confirmar",
    "history.saveBtn": "Guardar",
    "history.saving": "Guardando...",

    // Permissions
    "perm.requestTitle": "Permiso Requerido",
    "perm.levelYellow": "Confirmación",
    "perm.levelRed": "Operación Peligrosa",
    "perm.approve": "Aprobar",
    "perm.deny": "Denegar",
    "perm.enterPin": "PIN",
    "perm.processing": "Procesando...",
    "perm.approved": "Aprobado",
    "perm.denied": "Denegado",
    "perm.expired": "Expirado",

    // Computer Use
    "cu.title": "Uso de Computadora",
    "cu.modeCoding": "Codigo",
    "cu.modeComputer": "Computadora",
    "cu.switchToCoding": "Cambiar a modo Codigo",
    "cu.switchToComputerUse": "Cambiar a modo Computer Use",
    "cu.emergencyStop": "PARADA DE EMERGENCIA",
    "cu.iteration": "Paso",
    "cu.permLevel": "ACCESO A COMPUTADORA",

    // MCP Tools
    "mcp.title": "Herramientas MCP",
    "mcp.hub": "Hub",
    "mcp.email": "Email",
    "mcp.browser": "Navegador",
    "mcp.smarthome": "Smart Home",

    // Months
    "month.0": "Ene", "month.1": "Feb", "month.2": "Mar", "month.3": "Abr",
    "month.4": "May", "month.5": "Jun", "month.6": "Jul", "month.7": "Ago",
    "month.8": "Sep", "month.9": "Oct", "month.10": "Nov", "month.11": "Dic",
  },
};

export function translate(
  lang: Language,
  key: string,
  params?: Record<string, string | number>
): string {
  let str = translations[lang]?.[key] ?? translations.es[key] ?? key;
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      str = str.replace(`{${k}}`, String(v));
    }
  }
  return str;
}
