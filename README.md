<div align="center">

# Rain Assistant

**AI-powered coding assistant with voice, plugins, web UI, and Telegram bot**

[![PyPI](https://img.shields.io/pypi/v/rain-assistant.svg)](https://pypi.org/project/rain-assistant/)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11+-green.svg)](https://python.org)
[![Next.js](https://img.shields.io/badge/Next.js-16-black.svg)](https://nextjs.org)

[Features](#features) | [Installation](#installation) | [Usage](#usage) | [Plugins](#plugin-system) | [Telegram Bot](#telegram-bot) | [Contributing](#contributing)

</div>

---

## Features

- **Multi-Provider AI** — Claude, OpenAI (GPT-4o), Google Gemini, and Ollama (local) through a unified interface
- **Voice Input/Output** — Whisper transcription + Edge TTS synthesis
- **Dynamic Plugin System** — Add capabilities by chatting: _"I want you to search Google"_ and Rain creates the plugin automatically
- **Telegram Bot** — Use Rain from Telegram with voice messages, inline permissions, and all the same tools
- **Computer Use** — Control your screen with Claude's Computer Use (beta)
- **Permission System** — Three-tier security: GREEN (auto), YELLOW (confirm), RED (PIN required)
- **File & Code Tools** — Read, write, edit files, run bash commands, search codebases
- **Conversation History** — Persistent sessions with SQLite, resume conversations
- **Modern Web UI** — Next.js 16 + Zustand + Tailwind CSS with 3 themes
- **MCP Integration** — Connect to Home Assistant, Gmail, and more via Model Context Protocol (graceful degradation if unavailable)
- **Marketplace** — Ready-to-use plugins: weather, translator, URL shortener, system info, JSON formatter
- **Rate Limiting** — Per-token sliding-window protection across 6 endpoint categories
- **Documents / RAG** — Ingest PDFs, Markdown, and text files for context-aware conversations

## Architecture

```
                     ┌─────────────────┐
                     │   Telegram Bot   │
                     │   (aiogram 3)    │
                     └────────┬────────┘
                              │
┌──────────────┐    ┌─────────▼─────────┐    ┌──────────────────┐
│  Next.js UI  │◄──►│  FastAPI Server   │◄──►│  SQLite Database │
│  (WebSocket) │    │  (Python 3.11+)   │    │  (conversations) │
└──────────────┘    └─────────┬─────────┘    └──────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │ Provider Factory   │
                    ├───────────────────┤
                    │ Claude (SDK+MCP)  │
                    │ OpenAI (GPT-4o)   │
                    │ Gemini (Flash)    │
                    │ Ollama (local)    │
                    └─────────┬─────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
     ┌────────▼──────┐ ┌─────▼──────┐ ┌──────▼───────┐
     │ Built-in Tools│ │  Plugins   │ │ Computer Use │
     │ (17 tools)    │ │ (YAML/HTTP)│ │ (PyAutoGUI)  │
     └───────────────┘ └────────────┘ └──────────────┘
```

## Installation

### One-liner (recommended — nothing pre-installed needed)

**Windows** (PowerShell):
```powershell
irm https://raw.githubusercontent.com/camilo-gutierrez/rain-assistant-installer/main/install.ps1 | iex
```

**Linux/macOS**:
```bash
curl -fsSL https://raw.githubusercontent.com/camilo-gutierrez/rain-assistant-installer/main/install.sh | bash
```

These scripts automatically download Python, ffmpeg, and everything needed. Zero dependencies required on a clean machine.

### pip (if you already have Python 3.11+)

```bash
pip install rain-assistant
```

### With optional extras

```bash
# Telegram bot support
pip install "rain-assistant[telegram]"

# Everything included (telegram, computer-use, browser, scheduler, ollama, memory, voice)
pip install "rain-assistant[all]"
```

### Docker

```bash
git clone https://github.com/camilo-gutierrez/rain-assistant.git
cd rain-assistant
docker compose up -d
```

### Update

**Windows** (one-liner install):
```powershell
%USERPROFILE%\.rain\python\python.exe -m pip install --upgrade --no-cache-dir rain-assistant
```

**macOS/Linux** (one-liner install):
```bash
~/.rain/venv/bin/pip install --upgrade rain-assistant
```

**pip** (system install):
```bash
pip install --upgrade rain-assistant
```

### Uninstall

**Windows**:
```powershell
powershell %USERPROFILE%\.rain\uninstall.ps1
```

**macOS/Linux**:
```bash
bash ~/.rain/uninstall.sh
```

### CLI Commands

```bash
rain                   # Start server (auto-opens browser)
rain doctor            # Check all dependencies
rain setup             # Re-run first-time wizard
rain --version         # Show version
rain --no-browser      # Start without opening browser
rain --port 9000       # Custom port
rain --host 127.0.0.1  # Bind to localhost only
rain --telegram        # Start with Telegram bot
rain --telegram-only   # Telegram bot only (no web server)
```

## Usage

### Web UI

1. Run `rain` — browser opens automatically
2. Enter the PIN shown in terminal (first launch only)
3. Enter your API key (or skip if configured during setup)
4. Select a project directory and start chatting

### Telegram Bot

1. Create a bot via [@BotFather](https://t.me/BotFather) on Telegram
2. Add the token to your config:

```json
// ~/.rain-assistant/config.json
{
  "telegram": {
    "bot_token": "123456:ABC-DEF...",
    "allowed_users": [YOUR_TELEGRAM_USER_ID],
    "default_provider": "claude",
    "default_model": "auto",
    "default_cwd": "~"
  }
}
```

3. Start with Telegram: `python server.py --telegram`
4. Or Telegram only: `python server.py --telegram-only`
5. Send `/start` to your bot and follow the setup instructions

**Bot Commands:**
| Command | Description |
|---------|-------------|
| `/start` | Initialize session |
| `/key <api-key>` | Set API key (message auto-deleted) |
| `/model <provider> [model]` | Switch provider (claude, openai, gemini) |
| `/cwd <path>` | Set working directory |
| `/clear` | Clear conversation |
| `/stop` | Interrupt current task |
| `/plugins` | List installed plugins |
| `/status` | Show current configuration |

## Plugin System

Rain has a dynamic plugin system that lets you add new capabilities without writing code.

### Create Plugins via Chat

Just tell Rain what you want:

> "I want you to be able to check the weather"

Rain will automatically create a YAML plugin file in `~/.rain-assistant/plugins/` and activate it.

### Plugin Format

Plugins are simple YAML files with three execution types:

**HTTP Plugin** (API calls):
```yaml
name: weather
description: Get current weather for a city
version: "1.0"
permission_level: green
parameters:
  - name: city
    type: string
    description: City name
    required: true
execution:
  type: http
  method: GET
  url: "https://api.weatherapi.com/v1/current.json"
  params:
    q: "{{city}}"
    key: "{{env.WEATHER_API_KEY}}"
  extract: "current.{temp_c, condition}"
```

**Bash Plugin** (shell commands):
```yaml
name: disk_usage
description: Check disk space usage
version: "1.0"
permission_level: yellow
parameters:
  - name: path
    type: string
    description: Directory to check
    default: "."
execution:
  type: bash
  command: "du -sh {{path}}"
```

**Python Plugin** (scripts):
```yaml
name: uuid_generator
description: Generate a random UUID
version: "1.0"
permission_level: green
parameters: []
execution:
  type: python
  script: "import uuid; print(uuid.uuid4())"
```

### Plugin Environment Variables

Store API keys securely for plugins:

> "Set the WEATHER_API_KEY to abc123"

Rain stores them in `~/.rain-assistant/config.json` under `plugin_env`. Plugins reference them as `{{env.KEY_NAME}}`.

### Managing Plugins

Plugins are managed via the `manage_plugins` tool (Rain can do this in chat):

- **Create**: Rain generates and saves the YAML
- **List**: Show all installed plugins
- **Enable/Disable**: Toggle plugins without deleting
- **Delete**: Remove a plugin
- **Show**: View a plugin's YAML definition

## Configuration

All configuration lives in `~/.rain-assistant/`:

```
~/.rain-assistant/
├── config.json          # PIN, API keys, Telegram config, plugin env vars
├── conversations.db     # SQLite message history
├── plugins/             # Plugin YAML files
│   ├── weather.yaml
│   └── my_api.yaml
└── history/             # Exported conversation JSON files
```

### Permission Levels

| Level | Icon | Behavior | Examples |
|-------|------|----------|----------|
| GREEN | Auto-approved | Read file, search, list directory |
| YELLOW | User confirms | Write file, edit, bash commands |
| RED | PIN required | `rm -rf`, `git push --force`, system commands |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

## License

[Apache License 2.0](LICENSE) — Copyright 2024-2026 Rain Assistant Contributors
