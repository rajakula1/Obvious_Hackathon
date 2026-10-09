"""Run-status enum for QualityForge factory runs.

The ten statuses are fixed by the specification, section 9 ("Run statuses").
Groupings follow section 6 (pipeline stages), section 7.3 (needs_human
escalation), and section 7.9 (the human approval gate).

Writer rule, review recommendation R8: only the runbook script writes a
terminal status. That is what makes "runs ending in an undefined state: 0"
(spec section 12.2) hold by construction.
"""

from __future__ import annotations

from enum import StrEnum, unique


@unique
class RunStatus(StrEnum):
    """The ten run statuses defined in spec section 9."""

    ANALYZING = "analyzing"
    DESIGNING = "designing"
    GENERATING = "generating"
    TESTING = "testing"
    DEBUGGING = "debugging"
    VERIFYING = "verifying"
    AWAITING_APPROVAL = "awaiting_approval"
    DELIVERED = "delivered"
    NEEDS_HUMAN = "needs_human"
    REJECTED = "rejected"


# The six pipeline stages of spec section 6 advance the run through these
# (Analyze -> analyzing, ... Verify -> verifying). awaiting_approval is the
# human review gate of section 7.9, not a stage.
STAGE_STATUSES: frozenset[RunStatus] = frozenset(
    {
        RunStatus.ANALYZING,
        RunStatus.DESIGNING,
        RunStatus.GENERATING,
        RunStatus.TESTING,
        RunStatus.DEBUGGING,
        RunStatus.VERIFYING,
    }
)

# The run pauses here until an Approval record exists (spec section 7.9).
GATE_STATUS: RunStatus = RunStatus.AWAITING_APPROVAL

# Defined endings: delivered (approved at the gate), rejected (declined at the
# gate), needs_human (orchestrator escalation, spec section 7.3).
TERMINAL_STATUSES: frozenset[RunStatus] = frozenset(
    {
        RunStatus.DELIVERED,
        RunStatus.NEEDS_HUMAN,
        RunStatus.REJECTED,
    }
)


def is_terminal(status: RunStatus | str) -> bool:
    """Return True if `status` is a defined run ending (spec sections 9, 12.2).

    Raises ValueError for any status outside the spec's ten — an undefined
    state must fail loudly, never pass silently.
    """
    return RunStatus(status) in TERMINAL_STATUSES
