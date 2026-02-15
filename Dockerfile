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

WORKDIR /app

# Copy installed Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application source
COPY server.py transcriber.py tunnel.py ./
COPY static/ static/

EXPOSE 8000

CMD ["python", "server.py"]
