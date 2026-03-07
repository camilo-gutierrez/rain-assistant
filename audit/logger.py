"""Immutable audit log for Rain Assistant.

Records all security-relevant actions: tool calls, permission decisions,
config changes, auth events, and policy violations.

Each entry includes a hash chain (each entry references the previous
entry's hash) to detect tampering.
"""

import hashlib
import json
import time
import uuid
import threading
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Optional


class AuditEventType(str, Enum):
    TOOL_EXECUTED = "tool_executed"
    TOOL_DENIED = "tool_denied"
    PERMISSION_GRANTED = "permission_granted"
    PERMISSION_DENIED = "permission_denied"
    AUTH_SUCCESS = "auth_success"
    AUTH_FAILURE = "auth_failure"
    AUTH_LOCKOUT = "auth_lockout"
    SESSION_CREATED = "session_created"
    SESSION_REVOKED = "session_revoked"
    CONFIG_CHANGED = "config_changed"
    POLICY_VIOLATION = "policy_violation"
    PLUGIN_INSTALLED = "plugin_installed"
    PLUGIN_REMOVED = "plugin_removed"
    DIRECTOR_STARTED = "director_started"
    DIRECTOR_COMPLETED = "director_completed"
    COMPUTER_USE_ACTION = "computer_use_action"
    SANDBOX_VIOLATION = "sandbox_violation"


@dataclass
class AuditEvent:
    event_id: str
    event_type: AuditEventType
    timestamp: float
    user_id: str = "system"
    agent_id: str = "default"
    tool_name: str = ""
    action: str = ""
    details: dict = field(default_factory=dict)
    result: str = ""        # "success", "denied", "error"
    ip_address: str = ""
    prev_hash: str = ""     # hash of previous event (chain)
    event_hash: str = ""    # hash of this event

    def compute_hash(self) -> str:
        """Compute SHA-256 hash of this event for chain integrity."""
        payload = json.dumps({
            "event_id": self.event_id,
            "event_type": self.event_type.value if isinstance(self.event_type, AuditEventType) else self.event_type,
            "timestamp": self.timestamp,
            "user_id": self.user_id,
            "agent_id": self.agent_id,
            "tool_name": self.tool_name,
            "action": self.action,
            "result": self.result,
            "prev_hash": self.prev_hash,
        }, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value if isinstance(self.event_type, AuditEventType) else self.event_type,
            "timestamp": self.timestamp,
            "user_id": self.user_id,
            "agent_id": self.agent_id,
            "tool_name": self.tool_name,
            "action": self.action,
            "details": self.details,
            "result": self.result,
            "ip_address": self.ip_address,
            "prev_hash": self.prev_hash,
            "event_hash": self.event_hash,
        }


class AuditLogger:
    """Thread-safe audit logger with hash chain integrity.

    Usage:
        logger = AuditLogger()
        logger.log_tool_executed("bash", {"command": "ls"}, "green", user_id="user1")
        logger.log_auth_success(user_id="user1", ip="127.0.0.1")
    """

    def __init__(self, storage: Optional['AuditStorage'] = None):
        self._lock = threading.Lock()
        self._last_hash: str = "genesis"
        self._storage = storage
        self._event_count: int = 0

    def set_storage(self, storage: 'AuditStorage'):
        self._storage = storage
        # Load last hash from storage for chain continuity
        last = storage.get_last_event()
        if last:
            self._last_hash = last.get("event_hash", "genesis")

    def _create_event(self, event_type: AuditEventType, **kwargs) -> AuditEvent:
        with self._lock:
            event = AuditEvent(
                event_id=str(uuid.uuid4()),
                event_type=event_type,
                timestamp=time.time(),
                prev_hash=self._last_hash,
                **kwargs,
            )
            event.event_hash = event.compute_hash()
            self._last_hash = event.event_hash
            self._event_count += 1

        if self._storage:
            self._storage.save_event(event)

        return event

    # -- Convenience methods ---------------------------------------------------

    def log_tool_executed(self, tool_name: str, tool_input: dict,
                          permission_level: str, user_id: str = "default",
                          agent_id: str = "default") -> AuditEvent:
        # Sanitize sensitive data from tool_input
        safe_input = self._sanitize_input(tool_input)
        return self._create_event(
            AuditEventType.TOOL_EXECUTED,
            tool_name=tool_name,
            action="execute",
            details={"input": safe_input, "permission_level": permission_level},
            result="success",
            user_id=user_id,
            agent_id=agent_id,
        )

    def log_tool_denied(self, tool_name: str, tool_input: dict,
                        reason: str, user_id: str = "default",
                        agent_id: str = "default") -> AuditEvent:
        safe_input = self._sanitize_input(tool_input)
        return self._create_event(
            AuditEventType.TOOL_DENIED,
            tool_name=tool_name,
            action="deny",
            details={"input": safe_input, "reason": reason},
            result="denied",
            user_id=user_id,
            agent_id=agent_id,
        )

    def log_permission_granted(self, tool_name: str, permission_level: str,
                               user_id: str = "default") -> AuditEvent:
        return self._create_event(
            AuditEventType.PERMISSION_GRANTED,
            tool_name=tool_name,
            action="grant",
            details={"permission_level": permission_level},
            result="success",
            user_id=user_id,
        )

    def log_permission_denied(self, tool_name: str, permission_level: str,
                              user_id: str = "default") -> AuditEvent:
        return self._create_event(
            AuditEventType.PERMISSION_DENIED,
            tool_name=tool_name,
            action="deny",
            details={"permission_level": permission_level},
            result="denied",
            user_id=user_id,
        )

    def log_auth_success(self, user_id: str = "default", ip: str = "") -> AuditEvent:
        return self._create_event(
            AuditEventType.AUTH_SUCCESS,
            action="login",
            result="success",
            user_id=user_id,
            ip_address=ip,
        )

    def log_auth_failure(self, ip: str = "", reason: str = "") -> AuditEvent:
        return self._create_event(
            AuditEventType.AUTH_FAILURE,
            action="login",
            details={"reason": reason},
            result="denied",
            ip_address=ip,
        )

    def log_config_changed(self, key: str, user_id: str = "default") -> AuditEvent:
        return self._create_event(
            AuditEventType.CONFIG_CHANGED,
            action="config_change",
            details={"key": key},
            result="success",
            user_id=user_id,
        )

    def log_policy_violation(self, policy_name: str, details: dict,
                             user_id: str = "default",
                             agent_id: str = "default") -> AuditEvent:
        return self._create_event(
            AuditEventType.POLICY_VIOLATION,
            action="policy_violation",
            details={"policy": policy_name, **details},
            result="denied",
            user_id=user_id,
            agent_id=agent_id,
        )

    def log_computer_use_action(self, action: str, params: dict,
                                 user_id: str = "default") -> AuditEvent:
        return self._create_event(
            AuditEventType.COMPUTER_USE_ACTION,
            tool_name="computer",
            action=action,
            details={"params": params},
            result="success",
            user_id=user_id,
        )

    @staticmethod
    def _sanitize_input(tool_input: dict) -> dict:
        """Remove sensitive values from tool input before logging."""
        sensitive_keys = {"api_key", "password", "token", "secret", "pin", "key"}
        sanitized = {}
        for k, v in tool_input.items():
            if any(s in k.lower() for s in sensitive_keys):
                sanitized[k] = "***REDACTED***"
            elif isinstance(v, str) and len(v) > 1000:
                sanitized[k] = v[:200] + f"... [{len(v)} chars]"
            else:
                sanitized[k] = v
        return sanitized
