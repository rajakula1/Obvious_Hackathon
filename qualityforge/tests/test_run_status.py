"""Tests for the run-status enum (spec section 9)."""

import pytest

from qualityforge.run_status import (
    GATE_STATUS,
    STAGE_STATUSES,
    TERMINAL_STATUSES,
    RunStatus,
    is_terminal,
)

# The exact strings of spec section 9 ("Run statuses").
SPEC_SECTION_9_STATUSES = {
    "analyzing",
    "designing",
    "generating",
    "testing",
    "debugging",
    "verifying",
    "awaiting_approval",
    "delivered",
    "needs_human",
    "rejected",
}


def test_exactly_the_ten_spec_section_9_statuses() -> None:
    assert {status.value for status in RunStatus} == SPEC_SECTION_9_STATUSES
    assert len(RunStatus) == 10


def test_stage_statuses_map_the_six_pipeline_stages_of_section_6() -> None:
    assert {status.value for status in STAGE_STATUSES} == {
        "analyzing",
        "designing",
        "generating",
        "testing",
        "debugging",
        "verifying",
    }


def test_gate_status_is_the_human_review_pause_of_section_7_9() -> None:
    assert GATE_STATUS is RunStatus.AWAITING_APPROVAL


def test_terminal_statuses_partition_the_enum() -> None:
    assert {status.value for status in TERMINAL_STATUSES} == {
        "delivered",
        "needs_human",
        "rejected",
    }
    assert STAGE_STATUSES | TERMINAL_STATUSES | {GATE_STATUS} == set(RunStatus)


def test_is_terminal_holds_for_terminal_only() -> None:
    for terminal in TERMINAL_STATUSES:
        assert is_terminal(terminal)
    for non_terminal in set(RunStatus) - TERMINAL_STATUSES:
        assert not is_terminal(non_terminal)


def test_is_terminal_accepts_plain_strings_and_rejects_undefined() -> None:
    assert is_terminal("delivered")
    with pytest.raises(ValueError):
        # An undefined status fails loudly — spec section 12.2: zero runs
        # ending in an undefined state.
        is_terminal("shipped")
