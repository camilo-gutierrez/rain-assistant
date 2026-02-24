# Changelog

All notable changes to Rain Assistant will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.7] - 2026-02-22

### Added
- Per-user data isolation across memories, documents, alter egos, and scheduled tasks with automatic migration
- Multi-device authentication with configurable device limits, registration, revocation, and replacement flow
- Device management UI in the PIN panel and settings panel
- Device fingerprinting utilities (`frontend/src/lib/device.ts`) and user ID sanitization (`utils/sanitize.py`)

### Fixed
- Resolve double-fetch and race conditions in file browser navigation that caused visible flickering on directory changes
- Handle unknown Claude SDK event types (e.g., `rate_limit_event`) gracefully instead of crashing the response stream

### Security
- Fix 35 security vulnerabilities: path traversal protection, XSS sanitization, API key redaction in error responses, JSON DoS protection, file permission hardening, IP spoofing prevention, and strict input validation
- Harden plugin executor with improved sandboxing
- Strengthen Telegram bot with device registration enforcement, rate limiting, and permission nonces

## [1.0.2] - 2026-02-22

### Added
- Zero-dependency install scripts: `install.ps1` (Windows) and `install.sh` (macOS/Linux) automatically download portable Python 3.12 and ffmpeg with no prerequisites
- Package published to PyPI as `rain-assistant` -- installable via `pip install rain-assistant`
- Auto-detect available port when default port 8000 is busy (tries ports 8000-8009)

### Changed
- Install scripts now install from PyPI instead of GitHub archives
- Installation documentation updated to recommend PyPI one-liner as the primary method

### Fixed
- Port detection rewritten to use `connect` instead of `bind`, correctly detecting `0.0.0.0` conflicts on Windows
- Install scripts now work from GitHub zip archives without requiring git
- Remove deprecated license classifier for setuptools 77+ compatibility (SPDX-only requirement)

## [1.0.1] - 2026-02-21

### Changed
- Harden stability, security, and packaging configuration for MVP launch readiness

### Fixed
- Packaging fixes and dependency cleanup for reliable `pip install` from source

## [1.0.0] - 2026-02-19

### Added
- **RAG / Documents system**: parser (`.txt`, `.md`, `.pdf`), paragraph-based chunker, SQLite storage, and `manage_documents` meta-tool for ingesting, searching, listing, and removing documents
- **Subagents module** for delegating tasks to specialized sub-agents
- **Voice mode** with talk overlay, live transcription indicator, and voice message hooks
- **Marketplace** panel and plugin marketplace infrastructure
- **Scheduled tasks** system for recurring automated actions
- **Ollama provider** for local LLM support
- **Key manager** for centralized API key handling across all providers
- **Browser operations** tool (`browser_ops.py`) for web automation
- **Embeddings module** for the memories system (semantic search)
- WebSocket and documents test suites (36 + 35 tests)
- New frontend components: `LiveTranscription`, `SubAgentIndicator`, `TalkModeOverlay`, `VoiceModeIndicator`
- Flutter app: extracted widgets, notification service, voice mode service, lifecycle observer, i18n expansion

## [0.9.0] - 2026-02-18

### Added
- **Multi-provider architecture**: support for Claude, OpenAI, and Gemini via a factory pattern (`providers/`)
- **Plugin system**: YAML-based plugins in `~/.rain-assistant/plugins/` with three execution types (`http`, `bash`, `python`), template syntax, permission levels, and the `manage_plugins` meta-tool for chat-driven creation and management
- **Telegram bot** (`telegram_bot.py`): full-featured bot using aiogram 3 with per-user sessions, voice message transcription, inline keyboard permission approval, and commands (`/start`, `/key`, `/model`, `/cwd`, `/clear`, `/stop`, `/plugins`, `/status`)
- **Alter egos** personality system for customizable assistant personas
- **Persistent memories** system with `manage_memories` meta-tool
- **Model switcher** UI for changing providers and models at runtime
- **Toast notification** system in the frontend
- **Prompt composer** for assembling system prompts with context injection
- Flutter app scaffold (initial mobile client)
- CI/CD workflows, `CONTRIBUTING.md`, and `LICENSE` (Apache 2.0)

## [0.8.0] - 2026-02-16

### Added
- **MCP tools integration**: sidebar section with hub, email, browser, and smart home tools; backend loads server config from `.mcp.json`
- **Computer use**: screen capture, mouse/keyboard control (`computer_use.py`), and dedicated frontend panel
- **Permission system**: security-aware action classifier (`permission_classifier.py`) with GREEN/YELLOW/RED/COMPUTER levels and `SecurityBanner`/`PermissionRequestBlock` components
- **Rate limiter** (`rate_limiter.py`) for API request throttling
- **Mobile-responsive UI**: `MobileBottomNav`, `DrawerOverlay`, `SidebarNav` components
- Install scripts: `install.ps1`, `install.sh`, and `release.bat`

### Changed
- Audio recorder refactored to lazy-acquire microphone per recording and auto-release when idle
- Major UI overhaul across all panels and chat components for improved UX
- Themes, translations, stores, and hooks updated across the entire frontend

## [0.7.0] - 2026-02-15

### Added
- **Text-to-speech** synthesis via Azure Edge TTS (`synthesizer.py`, `useTTS` hook) with voice selection and auto-play settings
- **Conversation history** sidebar with save, load, and delete (max 5 conversations) backed by REST endpoints and file-based storage
- **Session resumption**: track `sessionId` per agent for Claude session continuity on reconnect
- Per-agent panel state memory (remembers active panel when switching tabs)
- TTS play button on assistant messages

### Changed
- Conversation history auto-saves on each assistant result message

### Fixed
- Prevent history reload from overwriting locally held messages
- Return boolean from `send()` and display error messages on WebSocket disconnect

## [0.6.0] - 2026-02-15

### Added
- **Multi-agent tabs** with full per-agent state isolation (independent project directory, message history, processing state, and file browser path)
- **Settings panel** with theme selector (Dark, Light, Ocean), transcription language toggle (EN/ES), and internationalization support
- **Next.js + Zustand + Tailwind frontend**: complete rewrite from vanilla JS (~4200 lines) to Next.js 16, Zustand 5, Tailwind CSS 4, and TypeScript

### Fixed
- Global `isProcessing` conflicts between agents
- Missing `agent_id` routing in voice recorder
- Force-stop timeout not scoped per agent
- `clearHistory` using wrong working directory
- WebSocket reconnection not re-registering agents

## [0.5.0] - 2026-02-15

### Added
- **Message persistence** with SQLite database module and REST endpoints (`GET`/`DELETE /api/messages`)
- **Service worker** for offline and PWA support
- Static file serving improvements

### Changed
- Monolithic `index.html` refactored into modular JavaScript and CSS files
- Streamed assistant responses now saved to database

## [0.1.0] - 2026-02-14

### Added
- Initial release of Voice Claude (Rain Assistant)
- Voice-controlled Claude AI assistant with dual interface:
  - Local tkinter GUI with push-to-talk (`main.py`)
  - Remote FastAPI web server with Cloudflare Tunnel (`server.py`)
- Cross-platform support (Windows, macOS, Linux) via Docker and native build scripts
- Whisper-based speech transcription
- WebSocket streaming for real-time responses

[Unreleased]: https://github.com/camilo-gutierrez/rain-assistant/compare/v1.0.7...HEAD
[1.0.7]: https://github.com/camilo-gutierrez/rain-assistant/compare/v1.0.2...v1.0.7
[1.0.2]: https://github.com/camilo-gutierrez/rain-assistant/compare/v1.0.1...v1.0.2
[1.0.1]: https://github.com/camilo-gutierrez/rain-assistant/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/camilo-gutierrez/rain-assistant/compare/v0.9.0...v1.0.0
[0.9.0]: https://github.com/camilo-gutierrez/rain-assistant/compare/v0.8.0...v0.9.0
[0.8.0]: https://github.com/camilo-gutierrez/rain-assistant/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/camilo-gutierrez/rain-assistant/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/camilo-gutierrez/rain-assistant/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/camilo-gutierrez/rain-assistant/compare/v0.1.0...v0.5.0
[0.1.0]: https://github.com/camilo-gutierrez/rain-assistant/releases/tag/v0.1.0
