"""Tests for the Rain Assistant policy engine."""

import datetime
import time
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from policies.engine import PolicyEngine, PolicyResult
from policies.rules import (
    BudgetPolicy,
    ProviderPolicy,
    SchedulePolicy,
    TokenLimitPolicy,
    ToolBlockPolicy,
)


# ---------------------------------------------------------------------------
# PolicyResult tests
# ---------------------------------------------------------------------------

class TestPolicyResult:
    def test_allow(self):
        result = PolicyResult.allow()
        assert result.allowed is True
        assert result.policy_name == ""
        assert result.reason == ""

    def test_deny(self):
        result = PolicyResult.deny("budget", "Over limit", limit=5.0, current=6.0)
        assert result.allowed is False
        assert result.policy_name == "budget"
        assert result.reason == "Over limit"
        assert result.details == {"limit": 5.0, "current": 6.0}


# ---------------------------------------------------------------------------
# BudgetPolicy tests
# ---------------------------------------------------------------------------

class TestBudgetPolicy:
    def test_under_limit(self):
        policy = BudgetPolicy(name="budget", max_daily=10.0)
        ctx = {"spending": {"day": 3.0, "week": 3.0, "month": 3.0}}
        result = policy.evaluate(ctx)
        assert result.allowed is True

    def test_over_daily(self):
        policy = BudgetPolicy(name="budget", max_daily=5.0)
        ctx = {"spending": {"day": 5.0, "week": 5.0, "month": 5.0}}
        result = policy.evaluate(ctx)
        assert result.allowed is False
        assert "Daily budget" in result.reason

    def test_over_weekly(self):
        policy = BudgetPolicy(name="budget", max_weekly=20.0)
        ctx = {"spending": {"day": 1.0, "week": 25.0, "month": 25.0}}
        result = policy.evaluate(ctx)
        assert result.allowed is False
        assert "Weekly budget" in result.reason

    def test_over_monthly(self):
        policy = BudgetPolicy(name="budget", max_monthly=50.0)
        ctx = {"spending": {"day": 1.0, "week": 10.0, "month": 55.0}}
        result = policy.evaluate(ctx)
        assert result.allowed is False
        assert "Monthly budget" in result.reason


# ---------------------------------------------------------------------------
# SchedulePolicy tests
# ---------------------------------------------------------------------------

class TestSchedulePolicy:
    def test_during_allowed_hours(self):
        policy = SchedulePolicy(name="schedule", allowed_hours=[8, 22])
        fake_now = datetime.datetime(2026, 3, 7, 14, 0, 0)  # Saturday 14:00
        with patch("policies.rules.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = fake_now
            result = policy.evaluate({})
        assert result.allowed is True

    def test_outside_allowed_hours(self):
        policy = SchedulePolicy(name="schedule", allowed_hours=[8, 18])
        fake_now = datetime.datetime(2026, 3, 7, 23, 0, 0)  # 23:00
        with patch("policies.rules.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = fake_now
            result = policy.evaluate({})
        assert result.allowed is False
        assert "Outside allowed hours" in result.reason

    def test_wrong_day(self):
        policy = SchedulePolicy(name="schedule", allowed_hours=[0, 24], allowed_days=[0, 1, 2, 3, 4])
        # 2026-03-07 is a Saturday (weekday=5)
        fake_now = datetime.datetime(2026, 3, 7, 12, 0, 0)
        with patch("policies.rules.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = fake_now
            result = policy.evaluate({})
        assert result.allowed is False
        assert "Sat" in result.reason


# ---------------------------------------------------------------------------
# ToolBlockPolicy tests
# ---------------------------------------------------------------------------

class TestToolBlockPolicy:
    def test_allowed_tool(self):
        policy = ToolBlockPolicy(name="block", blocked_tools=["bash"])
        ctx = {"type": "tool", "tool_name": "read_file"}
        result = policy.evaluate(ctx)
        assert result.allowed is True

    def test_blocked_tool(self):
        policy = ToolBlockPolicy(name="block", blocked_tools=["bash", "write_file"])
        ctx = {"type": "tool", "tool_name": "bash"}
        result = policy.evaluate(ctx)
        assert result.allowed is False
        assert "bash" in result.reason

    def test_non_tool_context(self):
        policy = ToolBlockPolicy(name="block", blocked_tools=["bash"])
        ctx = {"type": "llm_request", "tool_name": "bash"}
        result = policy.evaluate(ctx)
        assert result.allowed is True


# ---------------------------------------------------------------------------
# TokenLimitPolicy tests
# ---------------------------------------------------------------------------

class TestTokenLimitPolicy:
    def test_under_limit(self):
        policy = TokenLimitPolicy(name="tokens", max_total_tokens=100000)
        ctx = {"tokens": {"input": 5000, "output": 2000}}
        result = policy.evaluate(ctx)
        assert result.allowed is True

    def test_over_input(self):
        policy = TokenLimitPolicy(name="tokens", max_input_tokens=10000)
        ctx = {"tokens": {"input": 15000, "output": 500}}
        result = policy.evaluate(ctx)
        assert result.allowed is False
        assert "Input token limit" in result.reason

    def test_over_output(self):
        policy = TokenLimitPolicy(name="tokens", max_output_tokens=5000)
        ctx = {"tokens": {"input": 1000, "output": 6000}}
        result = policy.evaluate(ctx)
        assert result.allowed is False
        assert "Output token limit" in result.reason

    def test_over_total(self):
        policy = TokenLimitPolicy(name="tokens", max_total_tokens=10000)
        ctx = {"tokens": {"input": 6000, "output": 5000}}
        result = policy.evaluate(ctx)
        assert result.allowed is False
        assert "Total token limit" in result.reason


# ---------------------------------------------------------------------------
# ProviderPolicy tests
# ---------------------------------------------------------------------------

class TestProviderPolicy:
    def test_allowed_provider(self):
        policy = ProviderPolicy(name="prov", allowed_providers=["claude", "openai"])
        ctx = {"type": "llm_request", "provider": "claude"}
        result = policy.evaluate(ctx)
        assert result.allowed is True

    def test_provider_not_in_allow_list(self):
        policy = ProviderPolicy(name="prov", allowed_providers=["ollama"])
        ctx = {"type": "llm_request", "provider": "claude"}
        result = policy.evaluate(ctx)
        assert result.allowed is False
        assert "not allowed" in result.reason

    def test_blocked_provider(self):
        policy = ProviderPolicy(name="prov", blocked_providers=["claude"])
        ctx = {"type": "llm_request", "provider": "claude"}
        result = policy.evaluate(ctx)
        assert result.allowed is False
        assert "blocked" in result.reason

    def test_non_llm_context_passes(self):
        policy = ProviderPolicy(name="prov", blocked_providers=["claude"])
        ctx = {"type": "tool", "provider": "claude"}
        result = policy.evaluate(ctx)
        assert result.allowed is True


# ---------------------------------------------------------------------------
# PolicyEngine tests
# ---------------------------------------------------------------------------

class TestPolicyEngine:
    def _make_config(self, rules, enabled=True):
        return {"enabled": enabled, "rules": rules}

    def test_load_from_dict_multiple_rules(self):
        engine = PolicyEngine()
        config = self._make_config([
            {"type": "budget", "name": "b", "max_daily": 5.0},
            {"type": "tool_block", "name": "t", "blocked_tools": ["bash"]},
        ])
        count = engine.load_from_dict(config)
        assert count == 2

    def test_check_tool_passing(self):
        engine = PolicyEngine()
        engine.load_from_dict(self._make_config([
            {"type": "tool_block", "name": "t", "blocked_tools": ["bash"]},
        ]))
        result = engine.check_tool("read_file")
        assert result.allowed is True

    def test_check_tool_failing(self):
        engine = PolicyEngine()
        engine.load_from_dict(self._make_config([
            {"type": "tool_block", "name": "t", "blocked_tools": ["bash"]},
        ]))
        result = engine.check_tool("bash")
        assert result.allowed is False

    def test_check_llm_request_passing(self):
        engine = PolicyEngine()
        engine.load_from_dict(self._make_config([
            {"type": "provider", "name": "p", "allowed_providers": ["claude"]},
        ]))
        result = engine.check_llm_request(provider="claude")
        assert result.allowed is True

    def test_check_llm_request_failing(self):
        engine = PolicyEngine()
        engine.load_from_dict(self._make_config([
            {"type": "provider", "name": "p", "allowed_providers": ["ollama"]},
        ]))
        result = engine.check_llm_request(provider="claude")
        assert result.allowed is False

    def test_record_spending_and_budget(self):
        engine = PolicyEngine()
        engine.load_from_dict(self._make_config([
            {"type": "budget", "name": "b", "max_daily": 1.0},
        ]))
        # Under budget
        engine.record_spending(0.50, user_id="u1")
        result = engine.check_tool("anything", user_id="u1")
        assert result.allowed is True
        # Over budget
        engine.record_spending(0.60, user_id="u1")
        result = engine.check_tool("anything", user_id="u1")
        assert result.allowed is False

    def test_record_tokens_and_limit(self):
        engine = PolicyEngine()
        engine.load_from_dict(self._make_config([
            {"type": "token_limit", "name": "tl", "max_total_tokens": 10000},
        ]))
        engine.record_tokens(5000, 2000, user_id="u1")
        result = engine.check_tool("x", user_id="u1")
        assert result.allowed is True
        engine.record_tokens(2000, 2000, user_id="u1")
        result = engine.check_tool("x", user_id="u1")
        assert result.allowed is False

    def test_reset_tokens(self):
        engine = PolicyEngine()
        engine.load_from_dict(self._make_config([
            {"type": "token_limit", "name": "tl", "max_total_tokens": 10000},
        ]))
        engine.record_tokens(9000, 2000, user_id="u1")
        result = engine.check_tool("x", user_id="u1")
        assert result.allowed is False
        engine.reset_tokens(user_id="u1")
        result = engine.check_tool("x", user_id="u1")
        assert result.allowed is True

    def test_get_status(self):
        engine = PolicyEngine()
        engine.load_from_dict(self._make_config([
            {"type": "budget", "name": "b", "max_daily": 5.0},
        ]))
        engine.record_spending(1.0, user_id="u1")
        engine.record_tokens(100, 50, user_id="u1")
        status = engine.get_status(user_id="u1")
        assert status["enabled"] is True
        assert len(status["rules"]) == 1
        assert status["rules"][0]["name"] == "b"
        assert status["spending"]["day"] == pytest.approx(1.0, abs=0.01)
        assert status["tokens"]["input"] == 100
        assert status["tokens"]["output"] == 50

    def test_disabled_engine_allows_everything(self):
        engine = PolicyEngine()
        engine.load_from_dict(self._make_config(
            [{"type": "tool_block", "name": "t", "blocked_tools": ["bash"]}],
            enabled=False,
        ))
        result = engine.check_tool("bash")
        assert result.allowed is True

    def test_disabled_rule_skipped(self):
        engine = PolicyEngine()
        engine.load_from_dict(self._make_config([
            {"type": "tool_block", "name": "t", "blocked_tools": ["bash"], "enabled": False},
        ]))
        result = engine.check_tool("bash")
        assert result.allowed is True

    def test_generate_default_config_is_valid_yaml(self):
        config_str = PolicyEngine.generate_default_config()
        parsed = yaml.safe_load(config_str)
        assert parsed["enabled"] is True
        assert isinstance(parsed["rules"], list)
        assert len(parsed["rules"]) >= 4

    def test_load_policies_from_file(self, tmp_path):
        policies_file = tmp_path / "policies.yaml"
        policies_file.write_text(yaml.dump({
            "enabled": True,
            "rules": [
                {"type": "budget", "name": "b", "max_daily": 10.0},
                {"type": "tool_block", "name": "t", "blocked_tools": ["rm"]},
            ],
        }), encoding="utf-8")
        engine = PolicyEngine(policies_file=policies_file)
        count = engine.load_policies()
        assert count == 2

    def test_load_policies_missing_file(self, tmp_path):
        engine = PolicyEngine(policies_file=tmp_path / "nonexistent.yaml")
        count = engine.load_policies()
        assert count == 0
