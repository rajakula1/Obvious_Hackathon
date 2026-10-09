"""Smoke evidence: each agent's canned transcript passes its contract checker.

Runs the real harness (qualityforge.tools.smoke) over the canned input/output
pairs under ``qualityforge/agents/<agent>/smoke/`` — the §7 input/output
contracts, with the R2 guard, R6 rule, manifest re-hash, and PHI scan
executing for real (task todo_eY0KFAHI).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from qualityforge.tools.smoke import CHECKERS, check_agent
from qualityforge.tools.validate import EXIT_VALID

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("agent", sorted(CHECKERS))
def test_agent_smoke_contract(agent: str) -> None:
    """Acceptance: every agent passes its §7 smoke contract check."""
    assert check_agent(agent, REPO_ROOT) == []


def test_smoke_cli_all_agents() -> None:
    """The documented CLI path runs clean over every agent."""
    result = subprocess.run(
        [sys.executable, "-m", "qualityforge.tools.smoke"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == EXIT_VALID, result.stdout + result.stderr


def test_smoke_cli_rejects_unknown_agent() -> None:
    """An unknown agent name is a harness error, not a silent pass."""
    result = subprocess.run(
        [sys.executable, "-m", "qualityforge.tools.smoke", "no-such-agent"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
