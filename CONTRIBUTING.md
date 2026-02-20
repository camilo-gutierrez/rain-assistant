# Contributing to Rain Assistant

Thanks for your interest in contributing! Here's how to get started.

## Development Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- ffmpeg (for voice features)

### Backend

```bash
git clone https://github.com/camilo-gutierrez/rain-assistant.git
cd rain-assistant
pip install -r requirements.txt
python server.py
```

### Frontend

```bash
cd frontend
npm install
npm run dev    # Dev server on :3000 (proxied to backend on :8000)
```

### Build & Deploy Frontend

```bash
cd frontend
npm run deploy  # Builds static export and copies to ../static/
```

## Project Structure

```
rain-assistant/
├── server.py              # FastAPI server (REST + WebSocket)
├── providers/             # AI provider implementations
│   ├── base.py            # BaseProvider abstract class
│   ├── claude_provider.py # Claude Agent SDK
│   ├── openai_provider.py # OpenAI function calling
│   ├── gemini_provider.py # Google Gemini
│   └── ollama_provider.py # Ollama (local models)
├── tools/                 # Built-in tool system
│   ├── definitions.py     # Tool schemas (OpenAI format)
│   ├── executor.py        # Tool execution + permissions
│   ├── file_ops.py        # File read/write/edit
│   ├── bash_ops.py        # Shell execution
│   └── search_ops.py      # File/content search
├── plugins/               # Dynamic plugin system
│   ├── schema.py          # Plugin data model
│   ├── loader.py          # YAML loading
│   ├── converter.py       # Format conversion
│   ├── executor.py        # HTTP/bash/python execution
│   └── meta_tool.py       # manage_plugins tool
├── telegram_bot.py        # Telegram bot (aiogram 3)
├── telegram_config.py     # Telegram configuration
├── permission_classifier.py # GREEN/YELLOW/RED classification
├── database.py            # SQLite persistence
├── transcriber.py         # Whisper voice transcription
├── synthesizer.py         # Edge TTS synthesis
├── computer_use.py        # Computer Use (PyAutoGUI)
└── frontend/              # Next.js 16 + Zustand + Tailwind
    └── src/
        ├── app/           # Pages and layout
        ├── components/    # React components
        ├── stores/        # Zustand state management
        ├── hooks/         # Custom hooks
        └── lib/           # Types, constants, translations
```

## Code Style

### Python
- Follow PEP 8
- Use type hints
- Use f-strings
- Run `ruff check .` before committing

### TypeScript/React
- ESLint config in `frontend/.eslintrc.json`
- Run `npm run lint` before committing
- Use functional components with hooks

## Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes
4. Run linters (`ruff check .` and `cd frontend && npm run lint`)
5. Write a clear PR description explaining **why**, not just what
6. Submit your PR

## Adding a New AI Provider

1. Create `providers/my_provider.py`
2. Subclass `BaseProvider` from `providers/base.py`
3. Implement: `initialize`, `send_message`, `stream_response`, `interrupt`, `disconnect`
4. Register in `providers/__init__.py` → `get_provider()` factory
5. Add pricing to your provider's `MODEL_PRICING` dict
6. **Wrap tool execution in try-except** — a failing tool must not crash the stream:
   ```python
   try:
       result = await self._tool_executor.execute(name, args)
   except Exception as e:
       result = {"content": f"Tool execution error: {e}", "is_error": True}
   ```
7. **Wrap streaming in try-except** — network/API errors should yield an error event, not crash:
   ```python
   try:
       async for chunk in stream:
           ...
   except Exception as e:
       yield NormalizedEvent("error", {"text": f"Stream error: {e}"})
   ```

## Adding a New Plugin

Create a YAML file in `~/.rain-assistant/plugins/`:

```yaml
name: my_plugin
description: What it does
version: "1.0"
permission_level: yellow  # green, yellow, or red
parameters:
  - name: input
    type: string
    description: The input parameter
    required: true
execution:
  type: http  # or bash, python
  method: GET
  url: "https://api.example.com/endpoint"
  params:
    q: "{{input}}"
```

## Testing

### Running Tests

```bash
pytest tests/ -v
```

### Rate Limiter in Tests

The rate limiter is a global singleton. Always call `rl.reset()` in test fixtures to avoid state bleed between tests:

```python
from rate_limiter import rate_limiter as rl
rl.reset()  # Clear all state
rl.reset("specific-token")  # Clear only one token's state
```

Never access `rl._windows` directly — use the public `reset()` API.

## License

By contributing, you agree that your contributions will be licensed under the Apache License 2.0.
