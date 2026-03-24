"""Tests for backend/governance/stages.py"""
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from backend.config import (
    STAGE2_CONSECUTIVE_QUARTERS,
    STAGE2_TRIGGER_THRESHOLD,
    STAGE3_CONSECUTIVE_QUARTERS,
)
from backend.governance.models import GovernanceStage, PollResult
from backend.governance.stages import StageManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_poll(satisfaction_rate: float, quarter: str = "2026-Q1") -> PollResult:
    return PollResult(
        bot_id="test-bot",
        quarter=quarter,
        satisfaction_rate=satisfaction_rate,
        satisfied_weight=satisfaction_rate * 1000.0,
        total_weight=1000.0,
        stage_at_close=1,
        closed_at=datetime(2026, 3, 31, tzinfo=timezone.utc),
    )


def _make_stage_manager(polls: list[PollResult]) -> StageManager:
    voting_manager = MagicMock()
    voting_manager.get_poll_history.return_value = polls
    return StageManager(db=MagicMock(), voting_manager=voting_manager)


# ---------------------------------------------------------------------------
# _trailing_below — static helper
# ---------------------------------------------------------------------------

def test_trailing_below_all_above_threshold_returns_zero() -> None:
    assert StageManager._trailing_below([0.6, 0.7, 0.8], STAGE2_TRIGGER_THRESHOLD) == 0


def test_trailing_below_all_below_threshold_returns_full_count() -> None:
    assert StageManager._trailing_below([0.3, 0.4, 0.2], STAGE2_TRIGGER_THRESHOLD) == 3


def test_trailing_below_trailing_two_below() -> None:
    assert StageManager._trailing_below([0.8, 0.3, 0.4], STAGE2_TRIGGER_THRESHOLD) == 2


def test_trailing_below_resets_at_high_rate() -> None:
    # Last two are below, separated by a high rate — only trailing tail counts
    assert StageManager._trailing_below([0.2, 0.2, 0.9, 0.2, 0.3], STAGE2_TRIGGER_THRESHOLD) == 2


def test_trailing_below_empty_list_returns_zero() -> None:
    assert StageManager._trailing_below([], STAGE2_TRIGGER_THRESHOLD) == 0


def test_trailing_below_single_above_returns_zero() -> None:
    assert StageManager._trailing_below([0.9], STAGE2_TRIGGER_THRESHOLD) == 0


def test_trailing_below_single_below_returns_one() -> None:
    assert StageManager._trailing_below([0.1], STAGE2_TRIGGER_THRESHOLD) == 1


# ---------------------------------------------------------------------------
# _stage_from_consecutive — static helper
# ---------------------------------------------------------------------------

def test_stage_from_consecutive_zero_returns_normal() -> None:
    assert StageManager._stage_from_consecutive(0) == GovernanceStage.NORMAL


def test_stage_from_consecutive_one_returns_normal() -> None:
    assert StageManager._stage_from_consecutive(1) == GovernanceStage.NORMAL


def test_stage_from_consecutive_stage2_boundary_returns_review() -> None:
    assert StageManager._stage_from_consecutive(STAGE2_CONSECUTIVE_QUARTERS) == GovernanceStage.REVIEW


def test_stage_from_consecutive_stage3_boundary_returns_community() -> None:
    assert StageManager._stage_from_consecutive(STAGE3_CONSECUTIVE_QUARTERS) == GovernanceStage.COMMUNITY


def test_stage_from_consecutive_above_stage3_returns_community() -> None:
    assert StageManager._stage_from_consecutive(STAGE3_CONSECUTIVE_QUARTERS + 10) == GovernanceStage.COMMUNITY


# ---------------------------------------------------------------------------
# get_current_stage
# ---------------------------------------------------------------------------

def test_get_current_stage_normal_with_no_polls() -> None:
    assert _make_stage_manager([]).get_current_stage("test-bot") == GovernanceStage.NORMAL


def test_get_current_stage_normal_with_high_satisfaction() -> None:
    polls = [_make_poll(0.8, "2026-Q1"), _make_poll(0.9, "2026-Q2")]
    assert _make_stage_manager(polls).get_current_stage("test-bot") == GovernanceStage.NORMAL


def test_get_current_stage_normal_after_one_bad_quarter() -> None:
    """One quarter below threshold is not enough for REVIEW."""
    polls = [_make_poll(0.3, "2026-Q1")]
    assert _make_stage_manager(polls).get_current_stage("test-bot") == GovernanceStage.NORMAL


def test_get_current_stage_review_after_two_bad_quarters() -> None:
    polls = [_make_poll(0.3, "2026-Q1"), _make_poll(0.4, "2026-Q2")]
    assert _make_stage_manager(polls).get_current_stage("test-bot") == GovernanceStage.REVIEW


def test_get_current_stage_community_after_four_bad_quarters() -> None:
    polls = [
        _make_poll(0.2, "2025-Q1"),
        _make_poll(0.3, "2025-Q2"),
        _make_poll(0.1, "2025-Q3"),
        _make_poll(0.4, "2025-Q4"),
    ]
    assert _make_stage_manager(polls).get_current_stage("test-bot") == GovernanceStage.COMMUNITY


def test_get_current_stage_resets_to_normal_after_recovery() -> None:
    polls = [
        _make_poll(0.2, "2025-Q3"),
        _make_poll(0.3, "2025-Q4"),
        _make_poll(0.8, "2026-Q1"),  # recovery breaks the streak
    ]
    assert _make_stage_manager(polls).get_current_stage("test-bot") == GovernanceStage.NORMAL


def test_get_current_stage_at_exact_threshold_is_normal() -> None:
    """Rate == threshold is NOT below it; must be strictly less than."""
    polls = [
        _make_poll(STAGE2_TRIGGER_THRESHOLD, "2026-Q1"),
        _make_poll(STAGE2_TRIGGER_THRESHOLD, "2026-Q2"),
    ]
    assert _make_stage_manager(polls).get_current_stage("test-bot") == GovernanceStage.NORMAL


# ---------------------------------------------------------------------------
# evaluate_transition
# ---------------------------------------------------------------------------

def test_evaluate_transition_returns_none_with_no_polls() -> None:
    assert _make_stage_manager([]).evaluate_transition("test-bot") is None


def test_evaluate_transition_returns_none_single_poll_above_threshold() -> None:
    polls = [_make_poll(0.9, "2026-Q1")]
    assert _make_stage_manager(polls).evaluate_transition("test-bot") is None


def test_evaluate_transition_returns_none_when_stage_unchanged() -> None:
    """Three bad quarters — prior=REVIEW, current=REVIEW → no transition event."""
    polls = [
        _make_poll(0.3, "2025-Q1"),
        _make_poll(0.3, "2025-Q2"),
        _make_poll(0.3, "2025-Q3"),
    ]
    assert _make_stage_manager(polls).evaluate_transition("test-bot") is None


def test_evaluate_transition_detects_normal_to_review() -> None:
    polls = [
        _make_poll(0.3, "2026-Q1"),  # 1 bad → NORMAL
        _make_poll(0.4, "2026-Q2"),  # 2 bad → REVIEW (transition!)
    ]
    event = _make_stage_manager(polls).evaluate_transition("test-bot")
    assert event is not None
    assert event.from_stage == int(GovernanceStage.NORMAL)
    assert event.to_stage == int(GovernanceStage.REVIEW)


def test_evaluate_transition_detects_review_to_community() -> None:
    polls = [
        _make_poll(0.2, "2025-Q1"),
        _make_poll(0.3, "2025-Q2"),
        _make_poll(0.1, "2025-Q3"),  # 3 bad → REVIEW
        _make_poll(0.4, "2025-Q4"),  # 4 bad → COMMUNITY (transition!)
    ]
    event = _make_stage_manager(polls).evaluate_transition("test-bot")
    assert event is not None
    assert event.from_stage == int(GovernanceStage.REVIEW)
    assert event.to_stage == int(GovernanceStage.COMMUNITY)


def test_evaluate_transition_event_contains_bot_id() -> None:
    polls = [_make_poll(0.3, "2026-Q1"), _make_poll(0.4, "2026-Q2")]
    event = _make_stage_manager(polls).evaluate_transition("test-bot")
    assert event is not None
    assert event.bot_id == "test-bot"


def test_evaluate_transition_event_has_datetime_timestamp() -> None:
    polls = [_make_poll(0.3, "2026-Q1"), _make_poll(0.4, "2026-Q2")]
    event = _make_stage_manager(polls).evaluate_transition("test-bot")
    assert event is not None
    assert isinstance(event.timestamp, datetime)


def test_evaluate_transition_triggered_by_mentions_threshold() -> None:
    polls = [_make_poll(0.3, "2026-Q1"), _make_poll(0.4, "2026-Q2")]
    event = _make_stage_manager(polls).evaluate_transition("test-bot")
    assert event is not None
    assert str(STAGE2_TRIGGER_THRESHOLD) in event.triggered_by
