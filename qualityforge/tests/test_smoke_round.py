"""The smoke-round acceptance test (spec section 12.3, review R1).

Runs the real harness end to end: reference evaluator + reference suite +
subprocess pytest runner. The smoke round must detect 100% of its own
injected faults; this test pins that requirement. A second test demonstrates
the honest-negative path: a suite that ignores evidence and statuses detects
nothing, and the harness says so instead of papering over it.
"""

from pathlib import Path

from qualityforge.harness.fixtures.reference_suite import REFERENCE_NOTES
from qualityforge.harness.inject import (
    PytestSuiteRunner,
    drop_evidence_spans,
    flip_finding_statuses,
    load_config,
    remove_section_check,
    run_injection_round,
    skip_plan_relation_check,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SUITE_PATHS = (REPO_ROOT / "qualityforge" / "tests" / "test_reference_suite.py",)
CONFIG_PATH = REPO_ROOT / "qualityforge" / "schemas" / "completeness-criteria.example.yaml"


def _operators():
    config = load_config(CONFIG_PATH)
    return [
        remove_section_check(config, section="O"),
        drop_evidence_spans(),
        flip_finding_statuses(),
        skip_plan_relation_check(config),
    ]


def test_smoke_round_detects_every_injected_fault() -> None:
    report = run_injection_round(
        run_id="smoke-reference-round",
        module="qualityforge.harness.fixtures.reference_evaluator",
        factory="create_evaluator",
        config_path=CONFIG_PATH,
        suite_runner=PytestSuiteRunner(SUITE_PATHS, repo_root=REPO_ROOT),
        operators=_operators(),
        probes=[note.request() for note in REFERENCE_NOTES],
    )

    assert not report.baseline.failed, "reference suite must pass before injection"
    assert report.mutants_total == 4
    assert report.mutants_detected == 4, [m.op_id for m in report.mutants if not m.detected]
    assert all(not m.vacuous for m in report.mutants)
    assert report.detection_share == 1.0
    assert report.r1_threshold_met is True

    # Section 8.5 conventions, spot-checked on the real artifact.
    rendered = report.render_markdown()
    assert "Repair attempts" in rendered
    assert "None. The injection round measures detection only" in rendered
    assert "the detect, repair, retest loop is the Debug stage's evidence" in rendered
    assert report.to_dict()["disclaimer"] == (
        "Results reflect software correctness against stated criteria, not clinical validity."
    )


def test_blind_suite_reports_zero_detection_honestly(tmp_path: Path) -> None:
    blind = tmp_path / "test_blind_suite.py"
    blind.write_text(
        "import pytest\n\n"
        "@pytest.mark.parametrize('n', range(5))\n"
        "def test_always_passes(n):\n"
        "    assert n < 5\n",
        encoding="utf-8",
    )
    report = run_injection_round(
        run_id="smoke-blind-round",
        module="qualityforge.harness.fixtures.reference_evaluator",
        factory="create_evaluator",
        config_path=CONFIG_PATH,
        suite_runner=PytestSuiteRunner((blind,), repo_root=REPO_ROOT),
        operators=_operators(),
        probes=[note.request() for note in REFERENCE_NOTES],
    )
    assert report.mutants_detected == 0
    assert report.detection_share == 0.0
    assert report.r1_threshold_met is False
