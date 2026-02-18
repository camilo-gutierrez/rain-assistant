"""Telegram bot interface for Rain Assistant.

Runs alongside or independently from the FastAPI web server.
Reuses the same provider system, tool executor, and permission model.

Usage:
    python server.py --telegram          # Web + Telegram
    python server.py --telegram-only     # Telegram only
    python telegram_bot.py              # Standalone
"""

import asyncio
import json
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Any

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from providers import get_provider, NormalizedEvent
from permission_classifier import PermissionLevel, classify, get_danger_reason
from telegram_config import (
    get_bot_token,
    get_allowed_users,
    get_default_provider,
    get_default_model,
    get_default_cwd,
)
from prompt_composer import compose_system_prompt
from alter_egos.storage import (
    load_all_egos, load_ego, get_active_ego_id, set_active_ego_id,
)
from memories.storage import load_memories

logger = logging.getLogger("rain.telegram")

# Telegram limits
MAX_MESSAGE_LENGTH = 4096
EDIT_INTERVAL = 1.5  # seconds between message edits (rate limit)
PERMISSION_TIMEOUT = 120  # seconds to wait for permission response

router = Router()

# Per-user sessions
sessions: dict[int, "TelegramSession"] = {}


class TelegramSession:
    """Tracks state for a single Telegram user's conversation."""

    def __init__(self, user_id: int):
        self.user_id = user_id
        self.provider = None
        self.provider_name = get_default_provider()
        self.model = get_default_model()
        self.cwd = get_default_cwd()
        self.api_key: str = ""
        self.processing = False
        self.pending_permission: dict | None = None
        self._bot: Bot | None = None
        self.ego_id: str = get_active_ego_id()

    async def initialize_provider(self) -> str | None:
        """Initialize the AI provider. Returns error message or None."""
        if not self.api_key:
            return "No API key set. Use /key <your-api-key> to set it."

        try:
            self.provider = get_provider(self.provider_name)
            await self.provider.initialize(
                api_key=self.api_key,
                model=self.model,
                cwd=self.cwd,
                system_prompt=compose_system_prompt(self.ego_id),
                can_use_tool=self._permission_callback,
            )
            return None
        except Exception as e:
            self.provider = None
            return f"Failed to initialize provider: {e}"

    async def _permission_callback(
        self, tool_name: str, _tool_name2: str, tool_input: dict
    ) -> bool:
        """Handle permission requests via Telegram inline keyboard."""
        if not self._bot:
            return False

        # Map tool names for the classifier
        tool_map = {
            "read_file": "Read", "write_file": "Write", "edit_file": "Edit",
            "bash": "Bash", "list_directory": "Glob", "search_files": "Glob",
            "grep_search": "Grep",
        }
        classifier_name = tool_map.get(tool_name, tool_name)
        level = classify(classifier_name, tool_input)

        if level == PermissionLevel.GREEN:
            return True

        # Build permission message
        input_preview = json.dumps(tool_input, indent=2, ensure_ascii=False)
        if len(input_preview) > 500:
            input_preview = input_preview[:500] + "\n..."

        level_emoji = {"yellow": "🟡", "red": "🔴"}.get(level.value, "⚠️")
        text = (
            f"{level_emoji} **Permission required** ({level.value.upper()})\n\n"
            f"**Tool:** `{tool_name}`\n"
            f"**Input:**\n```\n{input_preview}\n```"
        )

        if level == PermissionLevel.RED:
            reason = get_danger_reason(classifier_name, tool_input)
            text += f"\n\n⚠️ {reason}\nReply with your PIN to approve, or tap Deny."

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Approve", callback_data=f"perm_yes_{self.user_id}"
                ),
                InlineKeyboardButton(
                    text="❌ Deny", callback_data=f"perm_no_{self.user_id}"
                ),
            ]
        ])

        try:
            msg = await self._bot.send_message(
                self.user_id, text, reply_markup=keyboard, parse_mode="Markdown"
            )
        except Exception:
            # Fallback without markdown
            msg = await self._bot.send_message(
                self.user_id, text, reply_markup=keyboard
            )

        # Wait for response
        event = asyncio.Event()
        self.pending_permission = {
            "event": event,
            "approved": False,
            "level": level,
            "message_id": msg.message_id,
        }

        try:
            await asyncio.wait_for(event.wait(), timeout=PERMISSION_TIMEOUT)
        except asyncio.TimeoutError:
            self.pending_permission = None
            await self._bot.send_message(self.user_id, "⏰ Permission timed out. Denied.")
            return False

        approved = self.pending_permission.get("approved", False)
        self.pending_permission = None
        return approved


def _split_message(text: str, max_len: int = MAX_MESSAGE_LENGTH) -> list[str]:
    """Split a long message into chunks respecting Telegram's limit."""
    if len(text) <= max_len:
        return [text]

    chunks = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break

        # Try to split at newline
        split_at = text.rfind("\n", 0, max_len)
        if split_at == -1 or split_at < max_len // 2:
            split_at = max_len

        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")

    return chunks


def _is_authorized(user_id: int) -> bool:
    """Check if a user is authorized to use the bot."""
    allowed = get_allowed_users()
    return not allowed or user_id in allowed


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    if not _is_authorized(message.from_user.id):
        await message.reply("⛔ You are not authorized to use this bot.")
        return

    user_id = message.from_user.id
    sessions[user_id] = TelegramSession(user_id)

    await message.reply(
        "👋 **Welcome to Rain Assistant!**\n\n"
        "I'm Rain, your AI coding assistant.\n\n"
        "**Setup:**\n"
        "1. `/key <api-key>` — Set your API key\n"
        "2. `/cwd <path>` — Set project directory\n"
        "3. Send me a message!\n\n"
        "**Commands:**\n"
        "• `/model <provider> [model]` — Change AI (claude, openai, gemini)\n"
        "• `/ego [id]` — Switch personality (alter ego)\n"
        "• `/memories` — Show stored memories\n"
        "• `/clear` — Clear conversation\n"
        "• `/stop` — Interrupt current task\n"
        "• `/plugins` — List installed plugins\n"
        "• `/status` — Show current config",
        parse_mode="Markdown",
    )


@router.message(Command("key"))
async def cmd_key(message: Message) -> None:
    if not _is_authorized(message.from_user.id):
        return

    user_id = message.from_user.id
    if user_id not in sessions:
        sessions[user_id] = TelegramSession(user_id)

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("Usage: `/key <your-api-key>`", parse_mode="Markdown")
        return

    api_key = parts[1].strip()
    sessions[user_id].api_key = api_key

    # Delete the message containing the API key for security
    try:
        await message.delete()
    except Exception:
        pass

    err = await sessions[user_id].initialize_provider()
    if err:
        await message.answer(f"⚠️ {err}")
    else:
        await message.answer(
            f"✅ API key set. Provider: **{sessions[user_id].provider_name}**",
            parse_mode="Markdown",
        )


@router.message(Command("model"))
async def cmd_model(message: Message) -> None:
    if not _is_authorized(message.from_user.id):
        return

    user_id = message.from_user.id
    if user_id not in sessions:
        sessions[user_id] = TelegramSession(user_id)

    parts = message.text.split()
    if len(parts) < 2:
        await message.reply(
            "Usage: `/model <provider> [model]`\n"
            "Providers: `claude`, `openai`, `gemini`\n"
            "Example: `/model openai gpt-4o`",
            parse_mode="Markdown",
        )
        return

    session = sessions[user_id]
    session.provider_name = parts[1].lower()
    session.model = parts[2] if len(parts) > 2 else "auto"

    if session.api_key:
        if session.provider:
            await session.provider.disconnect()
        err = await session.initialize_provider()
        if err:
            await message.reply(f"⚠️ {err}")
            return

    await message.reply(
        f"✅ Provider: **{session.provider_name}**, Model: **{session.model}**",
        parse_mode="Markdown",
    )


@router.message(Command("cwd"))
async def cmd_cwd(message: Message) -> None:
    if not _is_authorized(message.from_user.id):
        return

    user_id = message.from_user.id
    if user_id not in sessions:
        sessions[user_id] = TelegramSession(user_id)

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply(
            f"Current directory: `{sessions[user_id].cwd}`\n"
            "Usage: `/cwd /path/to/project`",
            parse_mode="Markdown",
        )
        return

    path = parts[1].strip()
    expanded = str(Path(path).expanduser().resolve())

    if not Path(expanded).is_dir():
        await message.reply(f"⚠️ Directory not found: `{expanded}`", parse_mode="Markdown")
        return

    sessions[user_id].cwd = expanded

    # Re-initialize provider with new cwd
    session = sessions[user_id]
    if session.provider and session.api_key:
        await session.provider.disconnect()
        await session.initialize_provider()

    await message.reply(f"✅ Working directory: `{expanded}`", parse_mode="Markdown")


@router.message(Command("clear"))
async def cmd_clear(message: Message) -> None:
    if not _is_authorized(message.from_user.id):
        return

    user_id = message.from_user.id
    if user_id in sessions and sessions[user_id].provider:
        await sessions[user_id].provider.disconnect()
        if sessions[user_id].api_key:
            await sessions[user_id].initialize_provider()

    await message.reply("🗑️ Conversation cleared.")


@router.message(Command("stop"))
async def cmd_stop(message: Message) -> None:
    if not _is_authorized(message.from_user.id):
        return

    user_id = message.from_user.id
    session = sessions.get(user_id)
    if session and session.provider:
        await session.provider.interrupt()
        session.processing = False
        await message.reply("🛑 Task interrupted.")
    else:
        await message.reply("Nothing to stop.")


@router.message(Command("plugins"))
async def cmd_plugins(message: Message) -> None:
    if not _is_authorized(message.from_user.id):
        return

    from plugins import load_all_plugins
    plugins = load_all_plugins()

    if not plugins:
        await message.reply("No plugins installed.")
        return

    lines = []
    for p in plugins:
        lines.append(f"• **{p.name}** ({p.execution.type}) — {p.description}")

    await message.reply(
        f"📦 Installed plugins ({len(plugins)}):\n" + "\n".join(lines),
        parse_mode="Markdown",
    )


@router.message(Command("status"))
async def cmd_status(message: Message) -> None:
    if not _is_authorized(message.from_user.id):
        return

    user_id = message.from_user.id
    session = sessions.get(user_id)

    if not session:
        await message.reply("No active session. Use /start first.")
        return

    ego = load_ego(session.ego_id)
    ego_name = ego["name"] if ego else session.ego_id
    ego_emoji = ego.get("emoji", "🤖") if ego else "🤖"

    await message.reply(
        f"**Rain Status:**\n"
        f"• Provider: `{session.provider_name}`\n"
        f"• Model: `{session.model}`\n"
        f"• Directory: `{session.cwd}`\n"
        f"• API Key: {'✅ Set' if session.api_key else '❌ Not set'}\n"
        f"• Provider Ready: {'✅' if session.provider else '❌'}\n"
        f"• Alter Ego: {ego_emoji} {ego_name}\n"
        f"• Memories: {len(load_memories())} stored",
        parse_mode="Markdown",
    )


@router.message(Command("ego"))
async def cmd_ego(message: Message) -> None:
    """Switch alter ego or list available egos."""
    if not _is_authorized(message.from_user.id):
        return

    user_id = message.from_user.id
    if user_id not in sessions:
        sessions[user_id] = TelegramSession(user_id)

    session = sessions[user_id]
    parts = message.text.split(maxsplit=1)

    if len(parts) < 2:
        # List all egos
        egos = load_all_egos()
        lines = ["**Available Alter Egos:**\n"]
        for ego in egos:
            active = " ← active" if ego["id"] == session.ego_id else ""
            lines.append(f"{ego.get('emoji', '🤖')} `{ego['id']}` — {ego['name']}{active}")
        lines.append(f"\nUsage: `/ego <id>` to switch")
        await message.reply("\n".join(lines), parse_mode="Markdown")
        return

    new_ego_id = parts[1].strip().lower()
    ego = load_ego(new_ego_id)
    if not ego:
        await message.reply(f"⚠️ Ego `{new_ego_id}` not found. Use `/ego` to see available egos.", parse_mode="Markdown")
        return

    session.ego_id = new_ego_id
    set_active_ego_id(new_ego_id)

    # Re-initialize provider with new prompt
    if session.provider and session.api_key:
        await session.provider.disconnect()
        await session.initialize_provider()

    await message.reply(
        f"{ego.get('emoji', '🤖')} Switched to **{ego['name']}**\n_{ego.get('description', '')}_",
        parse_mode="Markdown",
    )


@router.message(Command("memories"))
async def cmd_memories(message: Message) -> None:
    """Show stored memories."""
    if not _is_authorized(message.from_user.id):
        return

    memories = load_memories()
    if not memories:
        await message.reply("🧠 No memories stored yet.\nTell Rain to remember something!")
        return

    lines = [f"🧠 **Stored Memories ({len(memories)}):**\n"]
    for m in memories:
        cat = m.get("category", "fact")
        lines.append(f"• [{cat}] {m['content']}")

    await message.reply("\n".join(lines), parse_mode="Markdown")


# ---------------------------------------------------------------------------
# Permission callback handler
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("perm_"))
async def handle_permission_callback(callback: CallbackQuery) -> None:
    """Handle permission approval/denial via inline keyboard."""
    data = callback.data
    parts = data.split("_")
    if len(parts) < 3:
        return

    action = parts[1]  # "yes" or "no"
    user_id = int(parts[2])

    session = sessions.get(user_id)
    if not session or not session.pending_permission:
        await callback.answer("Permission request expired.")
        return

    if action == "yes":
        session.pending_permission["approved"] = True
        await callback.answer("✅ Approved")
        try:
            await callback.message.edit_text(
                callback.message.text + "\n\n✅ **Approved**",
                parse_mode="Markdown",
            )
        except Exception:
            pass
    else:
        session.pending_permission["approved"] = False
        await callback.answer("❌ Denied")
        try:
            await callback.message.edit_text(
                callback.message.text + "\n\n❌ **Denied**",
                parse_mode="Markdown",
            )
        except Exception:
            pass

    session.pending_permission["event"].set()


# ---------------------------------------------------------------------------
# Text message handler
# ---------------------------------------------------------------------------

@router.message(F.text & ~F.text.startswith("/"))
async def handle_text(message: Message, bot: Bot) -> None:
    """Handle user text messages — send to AI provider and stream response."""
    if not _is_authorized(message.from_user.id):
        return

    user_id = message.from_user.id
    session = sessions.get(user_id)

    if not session:
        await message.reply("Use /start to begin.")
        return

    if not session.provider:
        err = await session.initialize_provider()
        if err:
            await message.reply(f"⚠️ {err}")
            return

    if session.processing:
        await message.reply("⏳ Still processing previous message. Use /stop to interrupt.")
        return

    session.processing = True
    session._bot = bot

    # Send "thinking" message
    thinking_msg = await message.reply("🤔 Rain is thinking...")

    try:
        await session.provider.send_message(message.text)

        buffer = ""
        last_edit_time = 0.0
        tool_info = ""

        async for event in session.provider.stream_response():
            if event.type == "assistant_text":
                buffer += event.data.get("text", "")
                now = time.time()
                if now - last_edit_time > EDIT_INTERVAL and buffer:
                    display = buffer[:MAX_MESSAGE_LENGTH]
                    try:
                        await thinking_msg.edit_text(display)
                    except Exception:
                        pass
                    last_edit_time = now

            elif event.type == "tool_use":
                tool_name = event.data.get("tool", "unknown")
                tool_info = f"\n\n🔧 Using: `{tool_name}`"
                display = (buffer + tool_info)[:MAX_MESSAGE_LENGTH]
                try:
                    await thinking_msg.edit_text(display)
                except Exception:
                    pass

            elif event.type == "tool_result":
                tool_info = ""

            elif event.type == "result":
                pass

            elif event.type == "error":
                error_text = event.data.get("text", "Unknown error")
                buffer += f"\n\n⚠️ Error: {error_text}"

        # Send final response
        if buffer.strip():
            try:
                await thinking_msg.delete()
            except Exception:
                pass

            for chunk in _split_message(buffer):
                try:
                    await message.reply(chunk, parse_mode="Markdown")
                except Exception:
                    # Fallback without markdown parsing
                    await message.reply(chunk)
        else:
            try:
                await thinking_msg.edit_text("(No response)")
            except Exception:
                pass

    except Exception as e:
        logger.exception("Error processing message")
        try:
            await thinking_msg.edit_text(f"⚠️ Error: {e}")
        except Exception:
            await message.reply(f"⚠️ Error: {e}")
    finally:
        session.processing = False


# ---------------------------------------------------------------------------
# Voice message handler
# ---------------------------------------------------------------------------

@router.message(F.voice | F.audio)
async def handle_voice(message: Message, bot: Bot) -> None:
    """Handle voice messages: download -> transcribe -> process as text."""
    if not _is_authorized(message.from_user.id):
        return

    user_id = message.from_user.id
    session = sessions.get(user_id)

    if not session:
        await message.reply("Use /start to begin.")
        return

    # Download voice file
    file_id = message.voice.file_id if message.voice else message.audio.file_id
    file = await bot.get_file(file_id)

    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        await bot.download_file(file.file_path, tmp_path)

        # Transcribe
        transcribing_msg = await message.reply("🎤 Transcribing...")

        from transcriber import Transcriber
        transcriber = Transcriber(model_size="base", language="es")
        text = transcriber.transcribe(tmp_path)

        if not text or not text.strip():
            await transcribing_msg.edit_text("❌ Could not transcribe voice message.")
            return

        await transcribing_msg.edit_text(f"🎤 Heard: _{text}_", parse_mode="Markdown")

        # Process as regular text
        message.text = text
        await handle_text(message, bot)

    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Bot startup
# ---------------------------------------------------------------------------

async def run_telegram_bot_async() -> None:
    """Start the Telegram bot (runs in existing event loop)."""
    token = get_bot_token()
    if not token:
        logger.error(
            "Telegram bot token not configured. "
            "Add to ~/.rain-assistant/config.json: "
            '{"telegram": {"bot_token": "YOUR_TOKEN"}}'
        )
        return

    bot = Bot(token=token)
    dp = Dispatcher()
    dp.include_router(router)

    logger.info("Starting Telegram bot...")
    print("  Telegram bot started", flush=True)

    try:
        await dp.start_polling(bot, allowed_updates=["message", "callback_query"])
    finally:
        await bot.session.close()


def run_telegram_bot() -> None:
    """Start the Telegram bot standalone (creates event loop)."""
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_telegram_bot_async())


if __name__ == "__main__":
    run_telegram_bot()
