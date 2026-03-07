"""Policy engine for Rain Assistant.

Evaluates configurable rules before tool execution and LLM requests.
Policies are loaded from YAML config (~/.rain-assistant/policies.yaml).

Supports:
- Budget limits (max USD per day/week/month)
- Schedule restrictions (allowed hours of operation)
- Tool blocking (blacklist specific tools by context)
- Token limits (max tokens per conversation)
- Provider restrictions (only allow certain providers)
"""

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

from .rules import PolicyRule, BudgetPolicy, SchedulePolicy, ToolBlockPolicy, TokenLimitPolicy, ProviderPolicy

logger = logging.getLogger("rain.policies")

CONFIG_DIR = Path.home() / ".rain-assistant"
POLICIES_FILE = CONFIG_DIR / "policies.yaml"


@dataclass
class PolicyResult:
    """Result of a policy evaluation."""
    allowed: bool
    policy_name: str = ""       # which policy blocked it (if denied)
    reason: str = ""            # human-readable reason
    details: dict = field(default_factory=dict)

    @staticmethod
    def allow() -> 'PolicyResult':
        return PolicyResult(allowed=True)

    @staticmethod
    def deny(policy_name: str, reason: str, **details) -> 'PolicyResult':
        return PolicyResult(
            allowed=False,
            policy_name=policy_name,
            reason=reason,
            details=details,
        )


class PolicyEngine:
    """Evaluates policies before allowing actions.

    Usage:
        engine = PolicyEngine()
        engine.load_policies()  # from YAML

        # Check before tool execution
        result = engine.check_tool(tool_name="bash", tool_input={...}, user_id="user1")
        if not result.allowed:
            print(f"Blocked by {result.policy_name}: {result.reason}")

        # Check before LLM request
        result = engine.check_llm_request(provider="claude", model="opus", user_id="user1")

        # Record spending for budget tracking
        engine.record_spending(0.05, user_id="user1")
        engine.record_tokens(1500, 500, user_id="user1")
    """

    def __init__(self, policies_file: Path = None):
        self.policies_file = policies_file or POLICIES_FILE
        self._rules: list[PolicyRule] = []
        self._lock = threading.Lock()

        # Budget tracking (in-memory, reset on restart)
        self._spending: dict[str, list[tuple[float, float]]] = {}  # user_id -> [(timestamp, amount)]
        self._tokens: dict[str, dict[str, int]] = {}  # user_id -> {"input": N, "output": N}

        self._enabled = True

    def load_policies(self) -> int:
        """Load policies from YAML file. Returns number of rules loaded."""
        if not self.policies_file.exists():
            logger.info("No policies file found at %s -- all actions allowed", self.policies_file)
            return 0

        try:
            with open(self.policies_file, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
        except Exception as e:
            logger.error("Failed to load policies: %s", e)
            return 0

        with self._lock:
            self._rules.clear()
            self._enabled = config.get("enabled", True)

            for rule_config in config.get("rules", []):
                rule = self._parse_rule(rule_config)
                if rule:
                    self._rules.append(rule)
                    logger.info("Loaded policy: %s (%s)", rule.name, rule.__class__.__name__)

        return len(self._rules)

    def load_from_dict(self, config: dict) -> int:
        """Load policies from a dict (for testing or programmatic use)."""
        with self._lock:
            self._rules.clear()
            self._enabled = config.get("enabled", True)

            for rule_config in config.get("rules", []):
                rule = self._parse_rule(rule_config)
                if rule:
                    self._rules.append(rule)

        return len(self._rules)

    def check_tool(self, tool_name: str, tool_input: dict = None,
                   user_id: str = "default", agent_id: str = "default") -> PolicyResult:
        """Check if a tool execution is allowed by all policies."""
        if not self._enabled:
            return PolicyResult.allow()

        with self._lock:
            rules = list(self._rules)

        context = {
            "type": "tool",
            "tool_name": tool_name,
            "tool_input": tool_input or {},
            "user_id": user_id,
            "agent_id": agent_id,
            "timestamp": time.time(),
            "spending": self._get_spending(user_id),
            "tokens": self._get_tokens(user_id),
        }

        for rule in rules:
            if not rule.enabled:
                continue
            result = rule.evaluate(context)
            if not result.allowed:
                return result

        return PolicyResult.allow()

    def check_llm_request(self, provider: str, model: str = "",
                          user_id: str = "default",
                          agent_id: str = "default") -> PolicyResult:
        """Check if an LLM request is allowed by all policies."""
        if not self._enabled:
            return PolicyResult.allow()

        with self._lock:
            rules = list(self._rules)

        context = {
            "type": "llm_request",
            "provider": provider,
            "model": model,
            "user_id": user_id,
            "agent_id": agent_id,
            "timestamp": time.time(),
            "spending": self._get_spending(user_id),
            "tokens": self._get_tokens(user_id),
        }

        for rule in rules:
            if not rule.enabled:
                continue
            result = rule.evaluate(context)
            if not result.allowed:
                return result

        return PolicyResult.allow()

    def record_spending(self, amount_usd: float, user_id: str = "default"):
        """Record spending for budget tracking."""
        with self._lock:
            if user_id not in self._spending:
                self._spending[user_id] = []
            self._spending[user_id].append((time.time(), amount_usd))
            # Trim old entries (keep last 90 days)
            cutoff = time.time() - (90 * 86400)
            self._spending[user_id] = [
                (ts, amt) for ts, amt in self._spending[user_id] if ts > cutoff
            ]

    def record_tokens(self, input_tokens: int, output_tokens: int,
                      user_id: str = "default"):
        """Record token usage for limit tracking."""
        with self._lock:
            if user_id not in self._tokens:
                self._tokens[user_id] = {"input": 0, "output": 0}
            self._tokens[user_id]["input"] += input_tokens
            self._tokens[user_id]["output"] += output_tokens

    def reset_tokens(self, user_id: str = "default"):
        """Reset token counter (e.g. on new conversation)."""
        with self._lock:
            self._tokens.pop(user_id, None)

    def get_status(self, user_id: str = "default") -> dict:
        """Get current policy status for a user."""
        with self._lock:
            return {
                "enabled": self._enabled,
                "rules": [
                    {"name": r.name, "type": r.__class__.__name__, "enabled": r.enabled}
                    for r in self._rules
                ],
                "spending": self._get_spending(user_id),
                "tokens": self._get_tokens(user_id),
            }

    def _get_spending(self, user_id: str) -> dict:
        """Get spending breakdown for a user."""
        entries = self._spending.get(user_id, [])
        now = time.time()
        day_cutoff = now - 86400
        week_cutoff = now - (7 * 86400)
        month_cutoff = now - (30 * 86400)

        return {
            "day": sum(amt for ts, amt in entries if ts > day_cutoff),
            "week": sum(amt for ts, amt in entries if ts > week_cutoff),
            "month": sum(amt for ts, amt in entries if ts > month_cutoff),
        }

    def _get_tokens(self, user_id: str) -> dict:
        return self._tokens.get(user_id, {"input": 0, "output": 0})

    @staticmethod
    def _parse_rule(config: dict) -> Optional[PolicyRule]:
        """Parse a rule from config dict."""
        rule_type = config.get("type", "")
        name = config.get("name", rule_type)
        enabled = config.get("enabled", True)

        try:
            if rule_type == "budget":
                return BudgetPolicy(
                    name=name,
                    enabled=enabled,
                    max_daily=config.get("max_daily"),
                    max_weekly=config.get("max_weekly"),
                    max_monthly=config.get("max_monthly"),
                )
            elif rule_type == "schedule":
                return SchedulePolicy(
                    name=name,
                    enabled=enabled,
                    allowed_hours=config.get("allowed_hours", [0, 24]),
                    allowed_days=config.get("allowed_days"),
                    timezone=config.get("timezone", "local"),
                )
            elif rule_type == "tool_block":
                return ToolBlockPolicy(
                    name=name,
                    enabled=enabled,
                    blocked_tools=config.get("blocked_tools", []),
                    reason=config.get("reason", "Tool blocked by policy"),
                )
            elif rule_type == "token_limit":
                return TokenLimitPolicy(
                    name=name,
                    enabled=enabled,
                    max_input_tokens=config.get("max_input_tokens"),
                    max_output_tokens=config.get("max_output_tokens"),
                    max_total_tokens=config.get("max_total_tokens"),
                )
            elif rule_type == "provider":
                return ProviderPolicy(
                    name=name,
                    enabled=enabled,
                    allowed_providers=config.get("allowed_providers", []),
                    blocked_providers=config.get("blocked_providers", []),
                )
            else:
                logger.warning("Unknown policy type: %s", rule_type)
                return None
        except Exception as e:
            logger.error("Failed to parse policy rule '%s': %s", name, e)
            return None

    @staticmethod
    def generate_default_config() -> str:
        """Generate a default policies.yaml with examples."""
        return '''# Rain Assistant -- Policy Configuration
# Place this file at ~/.rain-assistant/policies.yaml

enabled: true

rules:
  # Budget limit: max spending per period
  - type: budget
    name: daily_budget
    enabled: false
    max_daily: 5.00    # USD
    max_weekly: 20.00
    max_monthly: 50.00

  # Schedule: only allow during work hours
  - type: schedule
    name: work_hours
    enabled: false
    allowed_hours: [8, 22]  # 8 AM to 10 PM
    allowed_days: [0, 1, 2, 3, 4, 5, 6]  # 0=Monday, 6=Sunday
    timezone: local

  # Block specific tools
  - type: tool_block
    name: no_destructive
    enabled: false
    blocked_tools:
      - bash  # Block all bash access
    reason: "Bash execution disabled by policy"

  # Token limits per conversation
  - type: token_limit
    name: conversation_limit
    enabled: false
    max_total_tokens: 100000  # input + output combined

  # Provider restrictions
  - type: provider
    name: local_only
    enabled: false
    allowed_providers:
      - ollama
    # Or use blocked_providers:
    # blocked_providers:
    #   - claude
'''
