"""Baseline execution of the reference suite (spec section 12.3, review R1).

This file IS the suite the injection round executes. CI runs it against the
pristine reference evaluator; the harness runner runs the same file in a
subprocess with QUALITYFORGE_EVALUATOR_SPEC selecting each mutant — one
suite serves both, which is the point of the check.
"""

import pytest

from qualityforge.harness.fixtures.reference_suite import REFERENCE_CHECKS
from qualityforge.harness.loader import get_config_under_test, get_evaluator_under_test

EVALUATOR = get_evaluator_under_test()
CONFIG = get_config_under_test()


@pytest.mark.parametrize(
    "check", REFERENCE_CHECKS, ids=[check.__name__ for check in REFERENCE_CHECKS]
)
def test_reference_check(check) -> None:
    check(EVALUATOR, CONFIG)
