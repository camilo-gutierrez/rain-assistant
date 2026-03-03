<div align="center">

<img src="https://raw.githubusercontent.com/camilo-gutierrez/rain-assistant/main/assets/logo.png" alt="Rain Assistant" width="120">

# Rain Assistant

**El asistente AI que TU controlas — tu voz, tus datos, tus reglas.**

Programa, depura y navega tus proyectos hablando. 100% self-hosted. Cero datos en la nube.

[![PyPI](https://img.shields.io/pypi/v/rain-assistant.svg)](https://pypi.org/project/rain-assistant/)
[![License](https://img.shields.io/badge/License-AGPL_3.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11+-green.svg)](https://python.org)
[![Next.js](https://img.shields.io/badge/Next.js-16-black.svg)](https://nextjs.org)
[![Discord](https://img.shields.io/badge/Discord-Join-7289da.svg)](https://discord.gg/rain-assistant)

[Demo](https://rain-assistant.com) | [Docs](https://docs.rain-assistant.com) | [Discord](https://discord.gg/rain-assistant) | [Rain Pro](https://rain-assistant.com/#pricing)

<img src="https://raw.githubusercontent.com/camilo-gutierrez/rain-assistant/main/assets/screenshot.png" alt="Rain Assistant Screenshot" width="800">

</div>

---

## Por que Rain?

La mayoria de asistentes AI te obligan a usar SU nube, SU modelo, SUS reglas. Rain es diferente:

- **Tu eliges el modelo** — Claude, GPT-4o, Gemini, o Ollama (100% local)
- **Tus datos son tuyos** — Todo corre en tu maquina. Conversaciones cifradas con Fernet
- **Tu voz, tu codigo** — Habla y Rain programa. Sin tocar el teclado
- **Extensible** — Sistema de permisos, herramientas, y una arquitectura que puedes modificar

---

## Que incluye (Community Edition)

| Feature | Descripcion |
|---------|-------------|
| **4 AI Providers** | Claude (SDK), OpenAI (GPT-4o), Google Gemini, Ollama (local) |
| **Control por voz** | Whisper AI transcribe tu voz en tiempo real (ES/EN) |
| **Text-to-speech** | Edge TTS con multiples voces |
| **17 herramientas** | read_file, write_file, edit_file, bash, search, list_dir, browser... |
| **Permisos 3 niveles** | GREEN (auto), YELLOW (confirmar), RED (PIN requerido) |
| **Web UI moderna** | Next.js 16 + Zustand + Tailwind CSS, 3 temas |
| **Historial** | Conversaciones persistentes en SQLite cifrado |
| **Acceso remoto** | Cloudflare Tunnel integrado — accede desde cualquier dispositivo |
| **Docker** | Deploy con un solo comando |
| **Rate limiting** | Proteccion por endpoint con sliding window |

> Quieres mas? [Rain Pro](https://rain-assistant.com/#pricing) agrega plugins, RAG, Computer Use, Telegram bot, app movil, y mas.

---

## Instalacion

### Rapida (recomendada — nada pre-instalado necesario)

**Windows** (PowerShell):
```powershell
irm https://raw.githubusercontent.com/camilo-gutierrez/rain-assistant-installer/main/install.ps1 | iex
```

**Linux/macOS**:
```bash
curl -fsSL https://raw.githubusercontent.com/camilo-gutierrez/rain-assistant-installer/main/install.sh | bash
```

### pip (si ya tienes Python 3.11+)

```bash
pip install rain-assistant
```

### Docker

```bash
git clone https://github.com/camilo-gutierrez/rain-assistant.git
cd rain-assistant
docker compose up -d
```

---

## Uso rapido

```bash
rain                      # Inicia servidor (abre navegador automaticamente)
rain --port 9000          # Puerto personalizado
rain --host 127.0.0.1     # Solo localhost
rain --no-browser         # Sin abrir navegador
rain doctor               # Verificar dependencias
rain setup                # Asistente de configuracion
rain --version            # Ver version
```

1. Ejecuta `rain` — el navegador se abre automaticamente
2. Ingresa el PIN que aparece en la terminal
3. Configura tu API key (Claude, OpenAI, Gemini, u Ollama)
4. Selecciona un directorio de proyecto
5. Habla o escribe — Rain programa por ti

---

## Arquitectura

```
                     ┌─────────────────┐
                     │   Tu Navegador  │
                     │   (Web UI)      │
                     └────────┬────────┘
                              │ WebSocket
┌──────────────┐    ┌─────────▼─────────┐    ┌──────────────────┐
│  Next.js UI  │◄──►│  FastAPI Server   │◄──►│  SQLite Database │
│  (3 temas)   │    │  (Python 3.11+)   │    │  (cifrado)       │
└──────────────┘    └─────────┬─────────┘    └──────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │ Provider Factory   │
                    ├────────────────────┤
                    │ Claude  (Agent SDK)│
                    │ OpenAI  (GPT-4o)  │
                    │ Gemini  (Flash)   │
                    │ Ollama  (local)   │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │  17 Built-in Tools │
                    │  + Permission Sys  │
                    └───────────────────┘
```

---

## Sistema de permisos

Rain tiene un sistema de seguridad de 3 niveles que clasifica cada accion:

| Nivel | Comportamiento | Ejemplos |
|-------|---------------|----------|
| GREEN | Auto-aprobado | Leer archivos, buscar, listar directorios |
| YELLOW | Requiere confirmacion | Escribir archivos, editar, comandos bash |
| RED | Requiere PIN | `rm -rf`, `git push --force`, comandos de sistema |

---

## Comparacion de planes

| Feature | Community (Free) | Pro ($15/mes) | Enterprise ($39/mes) |
|---------|:---:|:---:|:---:|
| 4 AI Providers | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Voice I/O | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| 17 Tools | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Web UI | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Permisos 3 niveles | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Historial cifrado | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Acceso remoto | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Docker support | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Plugins (YAML) | :x: | :white_check_mark: | :white_check_mark: |
| RAG / Documentos | :x: | :white_check_mark: | :white_check_mark: |
| Memorias semanticas | :x: | :white_check_mark: | :white_check_mark: |
| Alter Egos | :x: | :white_check_mark: | :white_check_mark: |
| Telegram Bot | :x: | :white_check_mark: | :white_check_mark: |
| App movil | :x: | :white_check_mark: | :white_check_mark: |
| Computer Use | :x: | :x: | :white_check_mark: |
| Directors (autonomos) | :x: | :x: | :white_check_mark: |
| Sub-agentes | :x: | :x: | :white_check_mark: |
| Licencia comercial | :x: | :x: | :white_check_mark: |
| Soporte prioritario | :x: | :x: | :white_check_mark: |

[Ver planes completos](https://rain-assistant.com/#pricing)

---

## Configuracion

Todo vive en `~/.rain-assistant/`:

```
~/.rain-assistant/
├── config.json          # PIN, API keys, configuracion general
├── conversations.db     # Historial de conversaciones (cifrado)
└── history/             # Exports de conversaciones en JSON
```

### Variables de entorno

```bash
RAIN_PORT=8000              # Puerto del servidor
RAIN_HOST=0.0.0.0           # Host de escucha
RAIN_DEFAULT_PROVIDER=claude # Provider por defecto
```

---

## Desarrollo

```bash
# Clonar el repositorio
git clone https://github.com/camilo-gutierrez/rain-assistant.git
cd rain-assistant

# Instalar dependencias de desarrollo
pip install -e ".[dev]"

# Ejecutar tests
pytest tests/

# Frontend (en otra terminal)
cd frontend
npm install
npm run dev
```

---

## Contribuir

Las contribuciones son bienvenidas! Consulta [CONTRIBUTING.md](CONTRIBUTING.md) para las guias de desarrollo.

Areas donde puedes contribuir:
- Nuevos AI providers
- Mejoras en la Web UI
- Traduccion (actualmente EN/ES)
- Documentacion
- Bug reports y feature requests

---

## Comunidad

- **Discord**: [Unete a la comunidad](https://discord.gg/rain-assistant)
- **GitHub Issues**: [Reportar bugs](https://github.com/camilo-gutierrez/rain-assistant/issues)
- **Twitter**: [@rain_assistant](https://twitter.com/rain_assistant)

---

## Licencia

Rain Assistant Community Edition se distribuye bajo la [GNU Affero General Public License v3.0](LICENSE).

Esto significa que puedes usar, modificar y distribuir Rain libremente, pero si lo ofreces como servicio (SaaS), debes publicar tus modificaciones bajo la misma licencia.

Para uso comercial sin estas restricciones, consulta [Rain Pro/Enterprise](https://rain-assistant.com/#pricing).

---

<div align="center">

**Rain Assistant** — Hecho con :purple_heart: por [Camilo Gutierrez](https://github.com/camilo-gutierrez)

[Website](https://rain-assistant.com) | [Docs](https://docs.rain-assistant.com) | [Discord](https://discord.gg/rain-assistant) | [Twitter](https://twitter.com/rain_assistant)

</div>
