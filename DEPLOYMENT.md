# Rain Assistant -- Production Deployment Guide

This guide covers deploying Rain Assistant in production environments. For local
development, see the [README](README.md).

---

## Table of Contents

- [Quick Start](#quick-start)
- [Prerequisites](#prerequisites)
- [Installation Methods](#installation-methods)
- [Configuration](#configuration)
- [Running in Production](#running-in-production)
- [Monitoring](#monitoring)
- [Security Checklist](#security-checklist)
- [Backup and Recovery](#backup-and-recovery)
- [Troubleshooting](#troubleshooting)

---

## Quick Start

The fastest path to a running production instance:

```bash
# 1. Install
pip install "rain-assistant[all]"

# 2. Run setup wizard (sets PIN, optional API key)
rain setup

# 3. Start the server bound to all interfaces, no browser
rain --host 0.0.0.0 --port 8000 --no-browser
```

Or with Docker:

```bash
git clone https://github.com/camilo-gutierrez/rain-assistant.git
cd rain-assistant
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env
docker compose up -d
```

---

## Prerequisites

| Dependency       | Version   | Notes                                                    |
|------------------|-----------|----------------------------------------------------------|
| Python           | 3.11+     | 3.11, 3.12, and 3.13 are tested in CI                   |
| Node.js          | 20+       | Required by `claude-agent-sdk` (npx) at runtime          |
| ffmpeg           | any       | Required for Whisper voice transcription                  |
| SQLite           | 3.35+     | Ships with Python; needed for WAL mode and `RETURNING`   |

**Optional:**

- **portaudio** (`libportaudio2`) -- only needed if using local microphone input
- **GPU / CUDA** -- accelerates Whisper transcription and wake-word detection

On Debian/Ubuntu:

```bash
sudo apt-get update && sudo apt-get install -y ffmpeg libportaudio2 curl
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo bash -
sudo apt-get install -y nodejs
```

---

## Installation Methods

### PyPI (recommended for servers)

```bash
# Core only (Claude provider, web UI, file tools)
pip install rain-assistant

# With Telegram bot support
pip install "rain-assistant[telegram]"

# Everything (telegram, computer-use, browser, scheduler, ollama, memory, voice)
pip install "rain-assistant[all]"
```

Available extras:

| Extra          | Packages added                                      |
|----------------|-----------------------------------------------------|
| `telegram`     | aiogram 3                                           |
| `computer-use` | anthropic, pyautogui, mss, Pillow, pyperclip        |
| `browser`      | playwright                                          |
| `scheduler`    | croniter                                            |
| `ollama`       | ollama                                              |
| `tunnel`       | pycloudflared                                       |
| `memory`       | sentence-transformers, pypdf                        |
| `voice`        | torch, openwakeword, onnxruntime                    |
| `all`          | All of the above                                    |

### Docker

The project includes a multi-stage Dockerfile (Python 3.11-slim, Node.js 20,
ffmpeg) and a `docker-compose.yml`.

```bash
git clone https://github.com/camilo-gutierrez/rain-assistant.git
cd rain-assistant

# Create .env with your API key
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY

docker compose up -d
```

The compose service:
- Exposes port **8000**
- Mounts `~/.rain-assistant` for persistent data (config, databases, plugins)
- Restarts automatically (`unless-stopped`)

To build and run manually:

```bash
docker build -t rain-assistant .
docker run -d \
  --name rain \
  -p 8000:8000 \
  -e ANTHROPIC_API_KEY=sk-ant-... \
  -v ~/.rain-assistant:/root/.rain-assistant \
  --restart unless-stopped \
  rain-assistant
```

### From Source

```bash
git clone https://github.com/camilo-gutierrez/rain-assistant.git
cd rain-assistant

# Install in editable mode with all extras and dev tools
pip install -e ".[all,dev]"

# Build frontend (requires Node.js 20+)
cd frontend && npm ci && npm run deploy && cd ..

# Run
python server.py --host 0.0.0.0 --no-browser
```

---

## Configuration

### Data directory

All persistent data lives under `~/.rain-assistant/`:

```
~/.rain-assistant/
  config.json            # PIN, API keys, Telegram config, CORS, plugin env
  conversations.db       # SQLite conversation history
  memories.db            # RAG embeddings and document chunks
  plugins/               # User-created YAML plugins
  logs/
    rain.log             # Rotating log (10 MB x 5 files)
    plugin_audit.log     # Plugin execution audit trail
  backups/               # Automated database backups
  history/               # Exported conversation JSON files
```

### config.json

Created automatically by `rain setup`. Key fields:

```jsonc
{
  // Authentication PIN (bcrypt hash -- set via setup wizard)
  "pin_hash": "$2b$12$...",

  // API keys (encrypted at rest via Fernet)
  "provider_keys": {
    "claude": "encrypted:...",
    "openai": "encrypted:...",
    "gemini": "encrypted:..."
  },

  // CORS origins for reverse proxy setups
  "cors_origins": [
    "https://rain.example.com"
  ],

  // Telegram bot configuration
  "telegram": {
    "bot_token": "123456:ABC-DEF...",
    "allowed_users": [123456789],
    "default_provider": "claude",
    "default_model": "auto",
    "default_cwd": "/home/deploy"
  },

  // Plugin environment variables (API keys for plugins)
  "plugin_env": {
    "WEATHER_API_KEY": "abc123"
  }
}
```

### Environment Variables

Copy `.env.example` to `.env` for Docker or systemd deployments:

| Variable              | Required | Description                                              |
|-----------------------|----------|----------------------------------------------------------|
| `ANTHROPIC_API_KEY`   | Yes*     | Claude API key (*or set via web UI / config.json)        |
| `OPENAI_API_KEY`      | No       | Required only if using the OpenAI provider               |
| `GOOGLE_API_KEY`      | No       | Required only if using the Gemini provider               |
| `RAIN_ENCRYPTION_KEY` | No       | Fernet key for encrypting stored secrets (recommended for containers where OS keyring is unavailable) |
| `RAIN_LOG_LEVEL`      | No       | `DEBUG`, `INFO` (default), `WARNING`, `ERROR`, `CRITICAL`|

Generate an encryption key:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### CLI Arguments

```
rain                        # Start server (auto-opens browser)
rain --host 0.0.0.0         # Bind to all interfaces
rain --port 9000            # Custom port (default: 8000)
rain --no-browser           # Don't auto-open browser
rain --telegram             # Start Telegram bot alongside web server
rain --telegram-only        # Telegram bot only (no web server)
rain doctor                 # Check dependencies and system health
rain setup                  # Re-run first-time setup wizard
rain --version              # Show version
```

---

## Running in Production

### systemd Service

Create `/etc/systemd/system/rain-assistant.service`:

```ini
[Unit]
Description=Rain Assistant
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=rain
Group=rain
WorkingDirectory=/home/rain

# Core settings
ExecStart=/usr/local/bin/rain --host 127.0.0.1 --port 8000 --no-browser
Restart=on-failure
RestartSec=5

# Environment
Environment=ANTHROPIC_API_KEY=sk-ant-...
Environment=RAIN_LOG_LEVEL=INFO
Environment=RAIN_ENCRYPTION_KEY=your-fernet-key-here

# Security hardening
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/home/rain/.rain-assistant
PrivateTmp=yes

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
# Create a dedicated user
sudo useradd -r -m -s /bin/bash rain
sudo -u rain pip install --user "rain-assistant[all]"
sudo -u rain rain setup

# Enable service
sudo systemctl daemon-reload
sudo systemctl enable rain-assistant
sudo systemctl start rain-assistant

# Check status
sudo systemctl status rain-assistant
sudo journalctl -u rain-assistant -f
```

### systemd with Telegram Bot

To run both the web server and Telegram bot, add the `--telegram` flag:

```ini
ExecStart=/usr/local/bin/rain --host 127.0.0.1 --port 8000 --no-browser --telegram
```

For a Telegram-only deployment (no web UI):

```ini
ExecStart=/usr/local/bin/rain --telegram-only
```

### Docker Compose (production)

Extended `docker-compose.yml` with all options:

```yaml
services:
  rain-assistant:
    build: .
    # Or use a pre-built image:
    # image: rain-assistant:latest
    ports:
      - "127.0.0.1:8000:8000"  # Bind to localhost only (nginx will proxy)
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - RAIN_ENCRYPTION_KEY=${RAIN_ENCRYPTION_KEY}
      - RAIN_LOG_LEVEL=INFO
    volumes:
      - rain-data:/root/.rain-assistant
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s

volumes:
  rain-data:
```

### Reverse Proxy (nginx)

Rain does not terminate TLS itself. Use a reverse proxy for HTTPS.

```nginx
upstream rain_backend {
    server 127.0.0.1:8000;
}

server {
    listen 443 ssl http2;
    server_name rain.example.com;

    ssl_certificate     /etc/letsencrypt/live/rain.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/rain.example.com/privkey.pem;

    # WebSocket support (required for chat)
    location /ws {
        proxy_pass http://rain_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400s;  # Keep WebSocket alive for 24h
        proxy_send_timeout 86400s;
    }

    # HTTP endpoints (API, static files, health checks)
    location / {
        proxy_pass http://rain_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # File upload size (for document ingestion)
        client_max_body_size 50M;
    }
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name rain.example.com;
    return 301 https://$host$request_uri;
}
```

After setting up the reverse proxy, add your domain to the CORS whitelist in
`~/.rain-assistant/config.json`:

```json
{
  "cors_origins": ["https://rain.example.com"]
}
```

### Cloudflare Tunnel (alternative to nginx)

Rain has built-in Cloudflare Tunnel support via the `tunnel` extra:

```bash
pip install "rain-assistant[tunnel]"
rain --host 127.0.0.1 --port 8000 --no-browser
```

If `pycloudflared` is installed, Rain automatically starts a tunnel and prints
the public URL on startup. No nginx or TLS configuration required.

---

## Monitoring

### Health Checks

Rain exposes two probe endpoints (no authentication required):

**Liveness -- `GET /health`**

Returns 200 when healthy, 503 when unhealthy. Response body:

```json
{
  "status": "healthy",
  "version": "1.0.7",
  "uptime_seconds": 3621.45,
  "checks": {
    "database": "ok",
    "disk_space_mb": 52481.3,
    "memory_usage_mb": 187.4
  }
}
```

**Readiness -- `GET /ready`**

Returns 200 when the server can accept traffic:

```json
{
  "status": "ready"
}
```

Use these with Docker healthchecks, Kubernetes probes, or external monitoring:

```bash
# Quick check from the command line
curl -s http://localhost:8000/health | python -m json.tool

# Nagios/monitoring one-liner
curl -sf http://localhost:8000/health || echo "CRITICAL: Rain is down"
```

### Logs

Logs are written to two destinations:

| Destination | Format | Level | Location |
|-------------|--------|-------|----------|
| stderr      | Colored, human-readable | Configurable via `RAIN_LOG_LEVEL` | Console / journalctl |
| File        | Structured `key=value` | DEBUG (captures everything) | `~/.rain-assistant/logs/rain.log` |

File log rotation: **10 MB per file, 5 backup files** (50 MB total max).

Example log line (file):

```
ts=2026-02-22T14:30:00.123Z level=INFO logger=rain.server msg="Server started on port 8000"
```

Plugin executions are additionally logged to `~/.rain-assistant/logs/plugin_audit.log`.

View live logs:

```bash
# systemd
journalctl -u rain-assistant -f

# Docker
docker compose logs -f rain-assistant

# Log file directly
tail -f ~/.rain-assistant/logs/rain.log
```

### System Health Check

Run the built-in doctor command to verify all dependencies:

```bash
rain doctor
```

---

## Security Checklist

### Authentication

- [ ] **Change the default PIN.** Run `rain setup` or manually update the
  `pin_hash` in `~/.rain-assistant/config.json`. The PIN is bcrypt-hashed.
- [ ] **Set a strong encryption key.** Set `RAIN_ENCRYPTION_KEY` as an
  environment variable (Fernet key) for container deployments where the OS
  keyring is unavailable. This encrypts stored API keys at rest.
- [ ] **Rate limiting is enabled by default.** Rain applies per-IP sliding-window
  rate limits across 6 endpoint categories. No configuration needed.

### Network

- [ ] **Never expose Rain directly to the internet.** Always use a reverse proxy
  (nginx, Caddy, Cloudflare Tunnel) for TLS termination.
- [ ] **Bind to localhost** (`--host 127.0.0.1`) when behind a reverse proxy.
  Only use `--host 0.0.0.0` if you understand the implications.
- [ ] **Restrict CORS origins.** Add only your domain(s) to `cors_origins` in
  `config.json`. The defaults are `localhost:8000` and `localhost:3000`.
- [ ] **Firewall rules.** Only allow inbound traffic on ports 443 (HTTPS) and
  optionally 80 (HTTP redirect). Block direct access to port 8000.

### File Permissions

```bash
# Data directory: owner-only
chmod 700 ~/.rain-assistant
chmod 600 ~/.rain-assistant/config.json
chmod 600 ~/.rain-assistant/conversations.db
chmod 600 ~/.rain-assistant/memories.db
```

Rain sets these permissions automatically on startup (`_secure_chmod`), but
verify them on shared systems.

### Telegram Bot

- [ ] **Restrict `allowed_users`** to specific Telegram user IDs. Never leave
  this list empty in production -- it would allow anyone to use the bot.
- [ ] **Keep the bot token secret.** It is stored in `config.json`, which should
  be readable only by the Rain process user.

### Plugin Security

- [ ] **Review plugin permission levels.** Plugins declare their own permission
  level (`green`, `yellow`, `red`). Audit custom plugins and ensure destructive
  ones are set to `yellow` or `red`.
- [ ] **Audit plugin environment variables.** Keys stored in `plugin_env` are
  accessible to all plugins of the corresponding execution type.
- [ ] **Plugin audit log** is written to `~/.rain-assistant/logs/plugin_audit.log`.
  Monitor it for unexpected executions.

---

## Backup and Recovery

### Database Backup

Rain includes a built-in backup system that uses SQLite's `sqlite3.backup()` API
(safe even during concurrent writes and WAL mode).

Back up programmatically:

```python
from database import backup_database, backup_all_databases

# Back up the main conversations database
backup_database()

# Back up all .db files under ~/.rain-assistant/
backup_all_databases()
```

Backups are stored in `~/.rain-assistant/backups/` with timestamps:

```
conversations_2026-02-22_143000.db
memories_2026-02-22_143000.db
```

By default, the 5 most recent backups per database are retained. Older ones are
automatically deleted.

### Manual Backup

```bash
# Simple file copy (stop the server first for consistency, or use sqlite3 .backup)
cp ~/.rain-assistant/conversations.db ~/backup/conversations_$(date +%Y%m%d).db
cp ~/.rain-assistant/memories.db ~/backup/memories_$(date +%Y%m%d).db
cp ~/.rain-assistant/config.json ~/backup/config_$(date +%Y%m%d).json

# Or use sqlite3 CLI (safe while server is running)
sqlite3 ~/.rain-assistant/conversations.db ".backup ~/backup/conversations.db"
```

### Scheduled Backup (cron)

```cron
# Daily at 3 AM -- back up all Rain databases
0 3 * * * python3 -c "from database import backup_all_databases; backup_all_databases()" 2>&1 | logger -t rain-backup
```

### Recovery

To restore from a backup, stop the server and replace the database file:

```bash
sudo systemctl stop rain-assistant
cp ~/.rain-assistant/backups/conversations_2026-02-22_143000.db \
   ~/.rain-assistant/conversations.db
chmod 600 ~/.rain-assistant/conversations.db
sudo systemctl start rain-assistant
```

---

## Installer Repo Sync (Private Repo Setup)

The main `rain-assistant` repo is **private**. Public install scripts live in a
separate repo: [rain-assistant-installer](https://github.com/camilo-gutierrez/rain-assistant-installer).

### How it works

```
rain-assistant (PRIVATE)              rain-assistant-installer (PUBLIC)
├── install.ps1 (master copy) ──sync──► install.ps1
├── install.sh  (master copy) ──sync──► install.sh
└── .github/workflows/                └── README.md
    └── sync-installers.yml
```

- Users run the one-liner from the **public** repo
- The scripts install `rain-assistant` from **PyPI** (always public)
- A GitHub Actions workflow auto-syncs changes from private → public

### Setting up the sync token

The `sync-installers.yml` workflow needs a `INSTALLER_REPO_TOKEN` secret to push
to the public repo.

1. **Create a Fine-Grained Personal Access Token:**
   - Go to GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens
   - Click "Generate new token"
   - **Token name:** `installer-repo-sync`
   - **Expiration:** 1 year (or custom)
   - **Repository access:** "Only select repositories" → select `rain-assistant-installer`
   - **Permissions:** Contents → Read and write
   - Click "Generate token" and copy it

2. **Add the token as a secret in the private repo:**
   - Go to `rain-assistant` repo → Settings → Secrets and variables → Actions
   - Click "New repository secret"
   - **Name:** `INSTALLER_REPO_TOKEN`
   - **Value:** paste the token from step 1
   - Click "Add secret"

3. **Verify:** Push a change to `install.ps1` or `install.sh` on `main` and
   check that the `Sync Install Scripts` workflow runs and updates the public repo.

### Manual sync (if needed)

```bash
# Clone both repos
git clone https://github.com/camilo-gutierrez/rain-assistant.git private
git clone https://github.com/camilo-gutierrez/rain-assistant-installer.git public

# Copy scripts and push
cp private/install.ps1 public/
cp private/install.sh public/
cd public
git add -A && git commit -m "sync: update install scripts" && git push
```

---

## Troubleshooting

### Server won't start -- port in use

```
ERROR: No hay puertos disponibles (8000-8009)
```

Another process is using the port. Either stop it or use a different port:

```bash
rain --port 9000

# Find what's using port 8000
lsof -i :8000        # Linux/macOS
netstat -ano | findstr 8000   # Windows
```

Rain automatically tries ports 8000--8009 before giving up.

### "nested session" error with Claude SDK

Rain clears the `CLAUDECODE` and `CLAUDE_CODE_ENTRYPOINT` environment variables
automatically. If you still see this error, ensure these variables are not set
in your shell profile or systemd environment.

### WebSocket disconnects behind reverse proxy

Ensure your nginx config includes the WebSocket upgrade headers and long
timeouts:

```nginx
proxy_http_version 1.1;
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection "upgrade";
proxy_read_timeout 86400s;
```

### OS keyring unavailable (containers / headless servers)

If you see warnings about keyring access, set `RAIN_ENCRYPTION_KEY` as an
environment variable. Rain falls back to: OS keyring > `RAIN_ENCRYPTION_KEY` >
config.json (with warning).

```bash
export RAIN_ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
```

### Database locked errors

SQLite can report "database is locked" under high concurrency. Rain uses WAL
mode by default which supports concurrent reads, but only one writer at a time.
If you see persistent lock errors:

1. Ensure only one Rain process accesses the database
2. Check that the filesystem supports file locking (NFS can be problematic)
3. Consider reducing concurrent agent sessions

### Whisper transcription fails

Ensure `ffmpeg` is installed and accessible in `PATH`:

```bash
ffmpeg -version
```

On first use, Whisper downloads the model (~150 MB for `base`). Ensure the
server has internet access during initial startup, or pre-download the model.

### Docker: permission denied on mounted volume

The container runs as root by default. If your `~/.rain-assistant` directory has
restrictive permissions:

```bash
# Fix ownership
sudo chown -R 0:0 ~/.rain-assistant

# Or run the container with your user's UID
docker run -u $(id -u):$(id -g) ...
```

### rain doctor reports missing dependencies

Run the built-in diagnostics:

```bash
rain doctor
```

This checks for Python version, Node.js, ffmpeg, and all optional dependencies.
Install any missing items reported.
