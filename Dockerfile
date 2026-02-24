# ---- Builder stage ----
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    portaudio19-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js (required by claude-agent-sdk / npx)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---- Runtime stage ----
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libportaudio2 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js in runtime too (needed for npx at runtime)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd --gid 1000 rain && \
    useradd --uid 1000 --gid rain --create-home rain

WORKDIR /app

# Copy installed Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application source
COPY server.py transcriber.py synthesizer.py tunnel.py ./
COPY permission_classifier.py rate_limiter.py database.py computer_use.py ./
COPY prompt_composer.py key_manager.py logging_config.py metrics.py shared_state.py ./
COPY telegram_bot.py telegram_config.py ./
COPY providers/ providers/
COPY tools/ tools/
COPY plugins/ plugins/
COPY memories/ memories/
COPY documents/ documents/
COPY alter_egos/ alter_egos/
COPY scheduled_tasks/ scheduled_tasks/
COPY subagents/ subagents/
COPY marketplace/ marketplace/
COPY routes/ routes/
COPY static/ static/
COPY pyproject.toml ./
COPY .mcp.json* ./

# Ensure data directory is writable by non-root user
RUN mkdir -p /home/rain/.rain-assistant && \
    chown -R rain:rain /home/rain/.rain-assistant /app

USER rain

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=10s \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "server.py"]
