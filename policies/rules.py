"""Individual policy rules for the Rain Assistant policy engine."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional
import time
import datetime


@dataclass
class PolicyRule(ABC):
    """Base class for policy rules."""
    name: str
    enabled: bool = True

    @abstractmethod
    def evaluate(self, context: dict) -> 'PolicyResult':
        """Evaluate this rule against the given context.

        Args:
            context: dict with keys like:
                - type: "tool" or "llm_request"
                - tool_name, tool_input (for tool checks)
                - provider, model (for LLM checks)
                - user_id, agent_id
                - timestamp
                - spending: {"day": X, "week": Y, "month": Z}
                - tokens: {"input": N, "output": M}

        Returns:
            PolicyResult (import from engine to avoid circular -- use string ref)
        """
        pass


# Import PolicyResult lazily to avoid circular imports
def _result_allow():
    from .engine import PolicyResult
    return PolicyResult.allow()

def _result_deny(policy_name, reason, **details):
    from .engine import PolicyResult
    return PolicyResult.deny(policy_name, reason, **details)


@dataclass
class BudgetPolicy(PolicyRule):
    """Enforce spending limits per time period."""
    max_daily: Optional[float] = None
    max_weekly: Optional[float] = None
    max_monthly: Optional[float] = None

    def evaluate(self, context: dict):
        spending = context.get("spending", {})

        if self.max_daily is not None and spending.get("day", 0) >= self.max_daily:
            return _result_deny(
                self.name,
                f"Daily budget exceeded: ${spending['day']:.2f} / ${self.max_daily:.2f}",
                limit=self.max_daily,
                current=spending["day"],
                period="day",
            )

        if self.max_weekly is not None and spending.get("week", 0) >= self.max_weekly:
            return _result_deny(
                self.name,
                f"Weekly budget exceeded: ${spending['week']:.2f} / ${self.max_weekly:.2f}",
                limit=self.max_weekly,
                current=spending["week"],
                period="week",
            )

        if self.max_monthly is not None and spending.get("month", 0) >= self.max_monthly:
            return _result_deny(
                self.name,
                f"Monthly budget exceeded: ${spending['month']:.2f} / ${self.max_monthly:.2f}",
                limit=self.max_monthly,
                current=spending["month"],
                period="month",
            )

        return _result_allow()


@dataclass
class SchedulePolicy(PolicyRule):
    """Restrict operations to specific hours/days."""
    allowed_hours: list = field(default_factory=lambda: [0, 24])  # [start, end)
    allowed_days: Optional[list] = None  # 0=Monday, 6=Sunday; None=all days
    timezone: str = "local"

    def evaluate(self, context: dict):
        now = datetime.datetime.now()
        hour = now.hour
        day = now.weekday()  # 0=Monday

        start_hour, end_hour = self.allowed_hours[0], self.allowed_hours[1]
        if not (start_hour <= hour < end_hour):
            return _result_deny(
                self.name,
                f"Outside allowed hours ({start_hour}:00-{end_hour}:00). Current: {hour}:00",
                current_hour=hour,
                allowed_start=start_hour,
                allowed_end=end_hour,
            )

        if self.allowed_days is not None and day not in self.allowed_days:
            day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            return _result_deny(
                self.name,
                f"Not allowed on {day_names[day]}",
                current_day=day,
                allowed_days=self.allowed_days,
            )

        return _result_allow()


@dataclass
class ToolBlockPolicy(PolicyRule):
    """Block specific tools."""
    blocked_tools: list = field(default_factory=list)
    reason: str = "Tool blocked by policy"

    def evaluate(self, context: dict):
        if context.get("type") != "tool":
            return _result_allow()

        tool_name = context.get("tool_name", "")
        if tool_name in self.blocked_tools:
            return _result_deny(
                self.name,
                f"{self.reason}: {tool_name}",
                blocked_tool=tool_name,
            )

        return _result_allow()


@dataclass
class TokenLimitPolicy(PolicyRule):
    """Limit tokens per conversation."""
    max_input_tokens: Optional[int] = None
    max_output_tokens: Optional[int] = None
    max_total_tokens: Optional[int] = None

    def evaluate(self, context: dict):
        tokens = context.get("tokens", {"input": 0, "output": 0})
        total = tokens.get("input", 0) + tokens.get("output", 0)

        if self.max_input_tokens and tokens.get("input", 0) >= self.max_input_tokens:
            return _result_deny(
                self.name,
                f"Input token limit exceeded: {tokens['input']} / {self.max_input_tokens}",
                limit=self.max_input_tokens,
                current=tokens["input"],
            )

        if self.max_output_tokens and tokens.get("output", 0) >= self.max_output_tokens:
            return _result_deny(
                self.name,
                f"Output token limit exceeded: {tokens['output']} / {self.max_output_tokens}",
                limit=self.max_output_tokens,
                current=tokens["output"],
            )

        if self.max_total_tokens and total >= self.max_total_tokens:
            return _result_deny(
                self.name,
                f"Total token limit exceeded: {total} / {self.max_total_tokens}",
                limit=self.max_total_tokens,
                current=total,
            )

        return _result_allow()


@dataclass
class ProviderPolicy(PolicyRule):
    """Restrict which AI providers can be used."""
    allowed_providers: list = field(default_factory=list)
    blocked_providers: list = field(default_factory=list)

    def evaluate(self, context: dict):
        if context.get("type") != "llm_request":
            return _result_allow()

        provider = context.get("provider", "")

        if self.allowed_providers and provider not in self.allowed_providers:
            return _result_deny(
                self.name,
                f"Provider '{provider}' not allowed. Allowed: {', '.join(self.allowed_providers)}",
                provider=provider,
                allowed=self.allowed_providers,
            )

        if self.blocked_providers and provider in self.blocked_providers:
            return _result_deny(
                self.name,
                f"Provider '{provider}' is blocked by policy",
                provider=provider,
            )

        return _result_allow()
