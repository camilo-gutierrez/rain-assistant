"""Tests for telegram_bot.py — Telegram bot interface for Rain Assistant.

Covers: TelegramSession, message splitting, authorization, device registration,
session management, permission callbacks, and command handlers.
"""

import asyncio
import sys
import types
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

# ---------------------------------------------------------------------------
# Pre-import: mock heavy external dependencies that may not be installed
# in the test environment (aiogram, etc.)
# ---------------------------------------------------------------------------

def _make_stub_module(name, attrs=None):
    mod = types.ModuleType(name)
    if attrs:
        for k, v in attrs.items():
            setattr(mod, k, v)
    return mod


# aiogram stubs
_aiogram = _make_stub_module("aiogram", {
    "Bot": MagicMock,
    "Dispatcher": MagicMock,
    "Router": MagicMock(),
    "F": MagicMock(),
})
_aiogram_filters = _make_stub_module("aiogram.filters", {
    "Command": lambda *a, **kw: lambda fn: fn,
    "CommandStart": lambda *a, **kw: lambda fn: fn,
})
_aiogram_types = _make_stub_module("aiogram.types", {
    "Message": MagicMock,
    "CallbackQuery": MagicMock,
    "InlineKeyboardMarkup": MagicMock,
    "InlineKeyboardButton": MagicMock,
})

sys.modules.setdefault("aiogram", _aiogram)
sys.modules.setdefault("aiogram.filters", _aiogram_filters)
sys.modules.setdefault("aiogram.types", _aiogram_types)

# The Router() mock needs .message() and .callback_query() to act as decorators
_router_mock = _aiogram.Router
_router_mock.message = lambda *a, **kw: lambda fn: fn
_router_mock.callback_query = lambda *a, **kw: lambda fn: fn


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_message(user_id=12345, text="/start", username="testuser", first_name="Test"):
    """Create a mock aiogram Message object."""
    msg = AsyncMock()
    msg.from_user = MagicMock()
    msg.from_user.id = user_id
    msg.from_user.username = username
    msg.from_user.first_name = first_name
    msg.text = text
    return msg


def _make_callback(user_id=12345, data="perm_yes_12345_abc123"):
    """Create a mock aiogram CallbackQuery object."""
    cb = AsyncMock()
    cb.from_user = MagicMock()
    cb.from_user.id = user_id
    cb.data = data
    cb.message = AsyncMock()
    cb.message.text = "Permission required"
    cb.message.message_id = 999
    return cb


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def mock_telegram_config():
    with patch('telegram_bot.get_allowed_users', return_value=[12345]), \
         patch('telegram_bot.get_default_provider', return_value='claude'), \
         patch('telegram_bot.get_default_model', return_value='auto'), \
         patch('telegram_bot.get_default_cwd', return_value='/tmp'), \
         patch('telegram_bot.get_active_ego_id', return_value='default'):
        yield


@pytest.fixture(autouse=True)
def clear_sessions():
    """Clear the sessions dict before each test."""
    import telegram_bot
    telegram_bot.sessions.clear()
    yield
    telegram_bot.sessions.clear()


# ===========================================================================
# 1. TelegramSession creation and properties
# ===========================================================================

class TestTelegramSession:
    def test_session_creation(self):
        from telegram_bot import TelegramSession
        session = TelegramSession(12345)
        assert session.user_id == 12345
        assert session.provider is None
        assert session.provider_name == 'claude'
        assert session.model == 'auto'
        assert session.cwd == '/tmp'
        assert session.api_key == ''
        assert session.processing is False
        assert session.pending_permission is None
        assert session.ego_id == 'default'

    def test_user_id_str_property(self):
        from telegram_bot import TelegramSession
        session = TelegramSession(99999)
        assert session.user_id_str == '99999'
        assert isinstance(session.user_id_str, str)

    def test_session_defaults_from_config(self):
        """Session pulls defaults from telegram_config functions."""
        with patch('telegram_bot.get_default_provider', return_value='openai'), \
             patch('telegram_bot.get_default_model', return_value='gpt-4o'), \
             patch('telegram_bot.get_default_cwd', return_value='/home/user'):
            from telegram_bot import TelegramSession
            session = TelegramSession(11111)
            assert session.provider_name == 'openai'
            assert session.model == 'gpt-4o'
            assert session.cwd == '/home/user'


# ===========================================================================
# 2. TelegramSession.initialize_provider
# ===========================================================================

class TestInitializeProvider:
    @pytest.mark.asyncio
    async def test_no_api_key(self):
        from telegram_bot import TelegramSession
        session = TelegramSession(12345)
        err = await session.initialize_provider()
        assert err is not None
        assert "No API key" in err

    @pytest.mark.asyncio
    async def test_success(self):
        from telegram_bot import TelegramSession
        session = TelegramSession(12345)
        session.api_key = "sk-test-key"

        mock_provider = AsyncMock()
        with patch('telegram_bot.get_provider', return_value=mock_provider), \
             patch('telegram_bot.compose_system_prompt', return_value='system prompt'):
            err = await session.initialize_provider()

        assert err is None
        assert session.provider is mock_provider
        mock_provider.initialize.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_provider_init_failure(self):
        from telegram_bot import TelegramSession
        session = TelegramSession(12345)
        session.api_key = "sk-bad-key"

        with patch('telegram_bot.get_provider', side_effect=Exception("Invalid key")):
            err = await session.initialize_provider()

        assert err is not None
        assert "Failed to initialize" in err
        assert session.provider is None


# ===========================================================================
# 3. _split_message
# ===========================================================================

class TestSplitMessage:
    def test_short_message(self):
        from telegram_bot import _split_message
        result = _split_message("Hello world")
        assert result == ["Hello world"]

    def test_exact_limit(self):
        from telegram_bot import _split_message
        text = "a" * 4096
        result = _split_message(text)
        assert result == [text]

    def test_long_message_splits_at_newline(self):
        from telegram_bot import _split_message
        # Create text with newlines where a split should happen
        line = "x" * 80 + "\n"
        text = line * 100  # 8100 chars, well over 4096
        result = _split_message(text)
        assert len(result) >= 2
        # Each chunk must be <= 4096
        for chunk in result:
            assert len(chunk) <= 4096

    def test_long_message_no_newlines(self):
        from telegram_bot import _split_message
        text = "a" * 10000
        result = _split_message(text)
        assert len(result) >= 3
        for chunk in result:
            assert len(chunk) <= 4096

    def test_custom_max_len(self):
        from telegram_bot import _split_message
        text = "abcdefghij"
        result = _split_message(text, max_len=5)
        assert len(result) == 2
        assert result[0] == "abcde"
        assert result[1] == "fghij"

    def test_empty_string(self):
        from telegram_bot import _split_message
        result = _split_message("")
        assert result == [""]


# ===========================================================================
# 4. _is_authorized
# ===========================================================================

class TestIsAuthorized:
    def test_authorized_user(self):
        from telegram_bot import _is_authorized
        assert _is_authorized(12345) is True

    def test_unauthorized_user(self):
        from telegram_bot import _is_authorized
        assert _is_authorized(99999) is False

    def test_empty_allowed_list_allows_all(self):
        from telegram_bot import _is_authorized
        with patch('telegram_bot.get_allowed_users', return_value=[]):
            assert _is_authorized(99999) is True

    def test_none_allowed_list_allows_all(self):
        from telegram_bot import _is_authorized
        with patch('telegram_bot.get_allowed_users', return_value=None):
            assert _is_authorized(99999) is True


# ===========================================================================
# 5. _register_telegram_device
# ===========================================================================

class TestRegisterTelegramDevice:
    @patch('telegram_bot.database')
    def test_success_new_device(self, mock_db):
        from telegram_bot import _register_telegram_device
        mock_db.cleanup_expired_sessions = MagicMock()
        mock_db.get_session_by_device_id = MagicMock(return_value=None)
        mock_db.count_active_devices = MagicMock(return_value=0)
        mock_db.create_session = MagicMock()

        err = _register_telegram_device(12345, "testuser", "Test")
        assert err is None
        mock_db.create_session.assert_called_once()
        # Verify device_id format
        call_args = mock_db.create_session.call_args
        assert call_args[0][3] == "telegram:12345"  # device_id
        assert "Telegram (@testuser)" in call_args[0][4]  # device_name

    @patch('telegram_bot.database')
    def test_existing_device_refreshes(self, mock_db):
        from telegram_bot import _register_telegram_device
        mock_db.cleanup_expired_sessions = MagicMock()
        mock_db.get_session_by_device_id = MagicMock(
            return_value={"token_hash": "abc123"}
        )
        mock_db.update_session_activity = MagicMock()

        err = _register_telegram_device(12345, "testuser", "Test")
        assert err is None
        mock_db.update_session_activity.assert_called_once_with("abc123")
        mock_db.create_session.assert_not_called()

    @patch('telegram_bot.database')
    def test_device_limit_reached(self, mock_db):
        from telegram_bot import _register_telegram_device, _get_max_devices
        mock_db.cleanup_expired_sessions = MagicMock()
        mock_db.get_session_by_device_id = MagicMock(return_value=None)
        mock_db.count_active_devices = MagicMock(return_value=2)

        with patch('telegram_bot._get_max_devices', return_value=2):
            err = _register_telegram_device(12345, "testuser", "Test")

        assert err is not None
        assert "Maximum devices" in err
        mock_db.create_session.assert_not_called()

    @patch('telegram_bot.database')
    def test_device_name_without_username(self, mock_db):
        from telegram_bot import _register_telegram_device
        mock_db.cleanup_expired_sessions = MagicMock()
        mock_db.get_session_by_device_id = MagicMock(return_value=None)
        mock_db.count_active_devices = MagicMock(return_value=0)
        mock_db.create_session = MagicMock()

        _register_telegram_device(12345, None, "TestUser")
        call_args = mock_db.create_session.call_args
        assert "Telegram (TestUser)" in call_args[0][4]


# ===========================================================================
# 6. _unregister_telegram_device
# ===========================================================================

class TestUnregisterTelegramDevice:
    @patch('telegram_bot.database')
    def test_unregister(self, mock_db):
        from telegram_bot import _unregister_telegram_device
        mock_db.revoke_session_by_device_id = MagicMock()

        _unregister_telegram_device(12345)
        mock_db.revoke_session_by_device_id.assert_called_once_with("telegram:12345")


# ===========================================================================
# 7. _ensure_session
# ===========================================================================

class TestEnsureSession:
    @patch('telegram_bot._register_telegram_device', return_value=None)
    def test_new_session(self, mock_register):
        import telegram_bot
        from telegram_bot import _ensure_session

        msg = _make_message(user_id=12345)
        session, err = _ensure_session(msg)

        assert err is None
        assert session is not None
        assert session.user_id == 12345
        assert 12345 in telegram_bot.sessions
        mock_register.assert_called_once()

    @patch('telegram_bot._register_telegram_device', return_value=None)
    def test_existing_session_reused(self, mock_register):
        import telegram_bot
        from telegram_bot import _ensure_session, TelegramSession

        existing = TelegramSession(12345)
        existing.api_key = "already-set"
        telegram_bot.sessions[12345] = existing

        msg = _make_message(user_id=12345)
        session, err = _ensure_session(msg)

        assert err is None
        assert session is existing
        assert session.api_key == "already-set"
        mock_register.assert_not_called()

    @patch('telegram_bot._register_telegram_device', return_value="Device limit reached")
    def test_device_limit_error(self, mock_register):
        from telegram_bot import _ensure_session

        msg = _make_message(user_id=99999)
        session, err = _ensure_session(msg)

        assert session is None
        assert err == "Device limit reached"


# ===========================================================================
# 8. Permission callback
# ===========================================================================

class TestPermissionCallback:
    @pytest.mark.asyncio
    async def test_green_auto_approves(self):
        from telegram_bot import TelegramSession
        session = TelegramSession(12345)
        session._bot = AsyncMock()

        with patch('telegram_bot.classify', return_value=PermissionLevel_GREEN()):
            result = await session._permission_callback("read_file", "", {"path": "/tmp/x"})

        assert result is True
        session._bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_yellow_sends_keyboard(self):
        from telegram_bot import TelegramSession
        session = TelegramSession(12345)
        session._bot = AsyncMock()
        sent_msg = AsyncMock()
        sent_msg.message_id = 42
        session._bot.send_message = AsyncMock(return_value=sent_msg)

        with patch('telegram_bot.classify') as mock_classify:
            mock_classify.return_value = MagicMock()
            mock_classify.return_value.value = 'yellow'
            # Make it not GREEN
            mock_classify.return_value.__eq__ = lambda self, other: (
                other.value == 'yellow' if hasattr(other, 'value') else False
            )

            # We need to simulate the event being set immediately
            async def run_with_timeout():
                # Patch asyncio.wait_for to simulate approval
                with patch('asyncio.wait_for', side_effect=asyncio.TimeoutError):
                    result = await session._permission_callback(
                        "bash", "", {"command": "rm -rf /"}
                    )
                return result

            result = await run_with_timeout()

        # Timed out => denied
        assert result is False
        session._bot.send_message.assert_called()


# Use a helper to get PermissionLevel.GREEN without importing the real enum
def PermissionLevel_GREEN():
    """Return a mock that behaves like PermissionLevel.GREEN."""
    mock = MagicMock()
    mock.value = 'green'
    # Make == comparison work with PermissionLevel.GREEN
    return mock


# Patch PermissionLevel for the callback tests
@pytest.fixture(autouse=True)
def mock_permission_level():
    with patch('telegram_bot.PermissionLevel') as mock_pl:
        green = MagicMock()
        green.value = 'green'
        yellow = MagicMock()
        yellow.value = 'yellow'
        red = MagicMock()
        red.value = 'red'
        mock_pl.GREEN = green
        mock_pl.YELLOW = yellow
        mock_pl.RED = red
        yield mock_pl


# ===========================================================================
# 9. cmd_start
# ===========================================================================

class TestCmdStart:
    @pytest.mark.asyncio
    @patch('telegram_bot._register_telegram_device', return_value=None)
    async def test_authorized_user(self, mock_register):
        import telegram_bot
        from telegram_bot import cmd_start

        msg = _make_message(user_id=12345, text="/start")
        await cmd_start(msg)

        msg.reply.assert_awaited()
        reply_text = msg.reply.call_args[0][0]
        assert "Welcome" in reply_text
        assert 12345 in telegram_bot.sessions

    @pytest.mark.asyncio
    async def test_unauthorized_user(self):
        from telegram_bot import cmd_start

        msg = _make_message(user_id=99999, text="/start")
        await cmd_start(msg)

        msg.reply.assert_awaited_once()
        reply_text = msg.reply.call_args[0][0]
        assert "not authorized" in reply_text

    @pytest.mark.asyncio
    @patch('telegram_bot._register_telegram_device', return_value="Device limit")
    async def test_device_limit(self, mock_register):
        from telegram_bot import cmd_start

        msg = _make_message(user_id=12345, text="/start")
        await cmd_start(msg)

        msg.reply.assert_awaited()
        reply_text = msg.reply.call_args[0][0]
        assert "Device limit" in reply_text


# ===========================================================================
# 10. cmd_key
# ===========================================================================

class TestCmdKey:
    @pytest.mark.asyncio
    @patch('telegram_bot._register_telegram_device', return_value=None)
    async def test_valid_key(self, mock_register):
        import telegram_bot
        from telegram_bot import cmd_key

        msg = _make_message(user_id=12345, text="/key sk-test-12345")

        mock_provider = AsyncMock()
        with patch('telegram_bot.get_provider', return_value=mock_provider), \
             patch('telegram_bot.compose_system_prompt', return_value='prompt'):
            await cmd_key(msg)

        # Should try to delete the message with the key
        msg.delete.assert_awaited()
        # Should confirm success
        msg.answer.assert_awaited()
        answer_text = msg.answer.call_args[0][0]
        assert "API key set" in answer_text

    @pytest.mark.asyncio
    @patch('telegram_bot._register_telegram_device', return_value=None)
    async def test_missing_key(self, mock_register):
        from telegram_bot import cmd_key

        msg = _make_message(user_id=12345, text="/key")
        await cmd_key(msg)

        msg.reply.assert_awaited_once()
        reply_text = msg.reply.call_args[0][0]
        assert "Usage" in reply_text

    @pytest.mark.asyncio
    async def test_unauthorized_user(self):
        from telegram_bot import cmd_key

        msg = _make_message(user_id=99999, text="/key sk-test")
        await cmd_key(msg)

        # Should silently return — no reply, no answer
        msg.reply.assert_not_awaited()
        msg.answer.assert_not_awaited()

    @pytest.mark.asyncio
    @patch('telegram_bot._register_telegram_device', return_value=None)
    async def test_provider_init_error(self, mock_register):
        from telegram_bot import cmd_key

        msg = _make_message(user_id=12345, text="/key sk-bad-key")

        with patch('telegram_bot.get_provider', side_effect=Exception("Bad")), \
             patch('telegram_bot.compose_system_prompt', return_value='prompt'):
            await cmd_key(msg)

        msg.answer.assert_awaited()
        answer_text = msg.answer.call_args[0][0]
        assert "Failed to initialize" in answer_text


# ===========================================================================
# 11. cmd_model
# ===========================================================================

class TestCmdModel:
    @pytest.mark.asyncio
    @patch('telegram_bot._register_telegram_device', return_value=None)
    async def test_change_provider(self, mock_register):
        import telegram_bot
        from telegram_bot import cmd_model

        msg = _make_message(user_id=12345, text="/model openai gpt-4o")
        await cmd_model(msg)

        msg.reply.assert_awaited()
        reply_text = msg.reply.call_args[0][0]
        assert "openai" in reply_text
        assert "gpt-4o" in reply_text

    @pytest.mark.asyncio
    @patch('telegram_bot._register_telegram_device', return_value=None)
    async def test_missing_provider(self, mock_register):
        from telegram_bot import cmd_model

        msg = _make_message(user_id=12345, text="/model")
        await cmd_model(msg)

        msg.reply.assert_awaited()
        reply_text = msg.reply.call_args[0][0]
        assert "Usage" in reply_text

    @pytest.mark.asyncio
    @patch('telegram_bot._register_telegram_device', return_value=None)
    async def test_provider_only_defaults_model_to_auto(self, mock_register):
        import telegram_bot
        from telegram_bot import cmd_model

        msg = _make_message(user_id=12345, text="/model gemini")
        await cmd_model(msg)

        session = telegram_bot.sessions[12345]
        assert session.provider_name == 'gemini'
        assert session.model == 'auto'


# ===========================================================================
# 12. handle_permission_callback
# ===========================================================================

class TestHandlePermissionCallback:
    @pytest.mark.asyncio
    async def test_approve(self):
        import time
        import telegram_bot
        from telegram_bot import handle_permission_callback, TelegramSession

        session = TelegramSession(12345)
        event = asyncio.Event()
        nonce = "abc123"
        session.pending_permission = {
            "event": event,
            "approved": False,
            "level": MagicMock(),
            "message_id": 999,
            "nonce": nonce,
            "created_at": time.time(),
        }
        telegram_bot.sessions[12345] = session

        cb = _make_callback(user_id=12345, data=f"perm_yes_12345_{nonce}")
        await handle_permission_callback(cb)

        assert session.pending_permission["approved"] is True
        assert event.is_set()
        cb.answer.assert_awaited()

    @pytest.mark.asyncio
    async def test_deny(self):
        import time
        import telegram_bot
        from telegram_bot import handle_permission_callback, TelegramSession

        session = TelegramSession(12345)
        event = asyncio.Event()
        nonce = "def456"
        session.pending_permission = {
            "event": event,
            "approved": False,
            "level": MagicMock(),
            "message_id": 999,
            "nonce": nonce,
            "created_at": time.time(),
        }
        telegram_bot.sessions[12345] = session

        cb = _make_callback(user_id=12345, data=f"perm_no_12345_{nonce}")
        await handle_permission_callback(cb)

        assert session.pending_permission["approved"] is False
        assert event.is_set()

    @pytest.mark.asyncio
    async def test_wrong_user(self):
        import time
        import telegram_bot
        from telegram_bot import handle_permission_callback, TelegramSession

        session = TelegramSession(12345)
        session.pending_permission = {
            "event": asyncio.Event(),
            "approved": False,
            "level": MagicMock(),
            "message_id": 999,
            "nonce": "xyz",
            "created_at": time.time(),
        }
        telegram_bot.sessions[12345] = session

        # Callback from different user
        cb = _make_callback(user_id=99999, data="perm_yes_12345_xyz")
        await handle_permission_callback(cb)

        # Should NOT approve
        assert session.pending_permission["approved"] is False
        assert not session.pending_permission["event"].is_set()

    @pytest.mark.asyncio
    async def test_expired_nonce(self):
        import telegram_bot
        from telegram_bot import handle_permission_callback, TelegramSession

        session = TelegramSession(12345)
        session.pending_permission = {
            "event": asyncio.Event(),
            "approved": False,
            "level": MagicMock(),
            "message_id": 999,
            "nonce": "old_nonce",
            "created_at": 0,
        }
        telegram_bot.sessions[12345] = session

        cb = _make_callback(user_id=12345, data="perm_yes_12345_wrong_nonce")
        await handle_permission_callback(cb)

        # Nonce mismatch => "Permission request expired"
        assert not session.pending_permission["event"].is_set()

    @pytest.mark.asyncio
    async def test_no_pending_permission(self):
        import telegram_bot
        from telegram_bot import handle_permission_callback, TelegramSession

        session = TelegramSession(12345)
        session.pending_permission = None
        telegram_bot.sessions[12345] = session

        cb = _make_callback(user_id=12345, data="perm_yes_12345_nonce")
        await handle_permission_callback(cb)

        cb.answer.assert_awaited_with("Permission request expired.")
