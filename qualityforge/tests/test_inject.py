"""Tests for the defect-injection harness core (spec section 12.3, review R1)."""

import copy
import json
from pathlib import Path

import pytest

from qualityforge.harness.fixtures.reference_suite import REFERENCE_NOTES
from qualityforge.harness.inject import (
    DISCLAIMER,
    EVALUATOR_SPEC_ENV_VAR,
    OPERATOR_REGISTRY,
    DetectionReport,
    EvaluateResponse,
    HarnessConsistencyError,
    SuiteBaselineError,
    SuiteResult,
    build_evaluator_spec,
    drop_evidence_spans,
    evaluator_from_spec,
    flip_finding_statuses,
    load_config,
    remove_section_check,
    run_injection_round,
    skip_criterion_check,
    skip_plan_relation_check,
)
from qualityforge.harness.loader import DEFAULT_CONFIG_PATH, DEFAULT_MODULE

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG = load_config(REPO_ROOT / "qualityforge" / "schemas" / "completeness-criteria.example.yaml")

REQUEST = {"note_id": "n1", "note_text": "S: Chief complaint: cough."}


def _span(start: int, end: int, text: str) -> dict:
    return {"start": start, "end": end, "text": text}


def _finding(criterion_id: str, section: str | None, status: str, evidence: list) -> dict:
    return {
        "criterion_id": criterion_id,
        "section": section,
        "status": status,
        "evidence": evidence,
        "message": f"{criterion_id} {status}",
    }


def _response(findings: list) -> EvaluateResponse:
    return {
        "note_id": "n1",
        "criteria_version": "0.1.0",
        "overall_status": "incomplete",
        "findings": findings,
    }


def _stub_evaluator(response: dict):
    def evaluate(request):
        return copy.deepcopy(response)

    return evaluate


class _StubRunner:
    """SuiteRunner double returning scripted results (no subprocesses)."""

    def __init__(self, *results: SuiteResult) -> None:
        self.results = list(results)

    def run(self, mutant_spec):
        assert self.results, "no scripted result left for this run"
        return self.results.pop(0)


def _passing() -> SuiteResult:
    return SuiteResult(passed=3, failed=0, summary_line="3 passed in 0.00s")


def _failing() -> SuiteResult:
    return SuiteResult(
        passed=1,
        failed=2,
        failed_test_ids=("test_reference_suite.py::test_reference_check[check_a]",),
        summary_line="2 failed, 1 passed in 0.00s",
    )


def _round(operators, runner) -> DetectionReport:
    return run_injection_round(
        run_id="test-round",
        module=DEFAULT_MODULE,
        factory="create_evaluator",
        config_path=DEFAULT_CONFIG_PATH,
        suite_runner=runner,
        operators=operators,
        probes=[note.request() for note in REFERENCE_NOTES],
    )


# --- the four operators -------------------------------------------------------


def test_remove_section_check_drops_only_that_sections_findings() -> None:
    response = _response(
        [
            _finding("O-01", "O", "missing", []),
            _finding("O-02", "O", "present", [_span(0, 5, "O: ch")]),
            _finding("S-01", "S", "present", [_span(6, 10, "S: x")]),
        ]
    )
    operator = remove_section_check(CONFIG, section="O")
    mutant = operator.apply(_stub_evaluator(response))
    out = mutant(REQUEST)
    assert [f["criterion_id"] for f in out["findings"]] == ["S-01"]


def test_remove_section_check_unknown_section_raises() -> None:
    with pytest.raises(ValueError, match="no criteria"):
        remove_section_check(CONFIG, section="Z")


def test_drop_evidence_spans_empties_present_and_partial_only() -> None:
    response = _response(
        [
            _finding("O-01", "O", "present", [_span(0, 5, "O: ch")]),
            _finding("A-01", "A", "partial", [_span(7, 9, "A:")]),
            _finding("O-02", "O", "missing", []),
        ]
    )
    mutant = drop_evidence_spans().apply(_stub_evaluator(response))
    out = mutant(REQUEST)
    by_id = {f["criterion_id"]: f for f in out["findings"]}
    assert by_id["O-01"]["evidence"] == []
    assert by_id["A-01"]["evidence"] == []
    assert by_id["O-02"]["evidence"] == []
    assert by_id["O-01"]["message"] == "O-01 present"  # untouched fields stay untouched


def test_flip_finding_statuses_swaps_and_recomputes_overall() -> None:
    response = _response(
        [
            _finding("O-01", "O", "missing", []),
            _finding("S-01", "S", "present", [_span(6, 10, "S: x")]),
            _finding("A-01", "A", "partial", [_span(0, 2, "A:")]),
        ]
    )
    mutant = flip_finding_statuses().apply(_stub_evaluator(response))
    out = mutant(REQUEST)
    by_id = {f["criterion_id"]: f for f in out["findings"]}
    assert by_id["O-01"]["status"] == "present"
    assert by_id["S-01"]["status"] == "missing"
    assert by_id["A-01"]["status"] == "partial"  # partial is untouched
    assert out["overall_status"] == "incomplete"


def test_skip_criterion_check_drops_only_that_criterion() -> None:
    response = _response(
        [
            _finding("S-01", "S", "present", []),
            _finding("P-02", "P", "missing", []),
        ]
    )
    operator = skip_criterion_check(CONFIG, criterion_id="P-02")
    mutant = operator.apply(_stub_evaluator(response))
    out = mutant(REQUEST)
    assert [f["criterion_id"] for f in out["findings"]] == ["S-01"]


def test_skip_criterion_check_unknown_id_raises() -> None:
    with pytest.raises(ValueError, match="not defined"):
        skip_criterion_check(CONFIG, criterion_id="Z-99")


def test_skip_plan_relation_check_targets_p02() -> None:
    response = _response(
        [
            _finding("S-01", "S", "present", []),
            _finding("P-02", "P", "present", []),
        ]
    )
    operator = skip_plan_relation_check(CONFIG)
    assert operator.op_id == "skip-plan-relation-check"
    mutant = operator.apply(_stub_evaluator(response))
    out = mutant(REQUEST)
    assert [f["criterion_id"] for f in out["findings"]] == ["S-01"]


def test_skip_plan_relation_check_rejects_mismatched_configs() -> None:
    no_p02 = copy.deepcopy(CONFIG)
    no_p02["criteria"] = [c for c in no_p02["criteria"] if c["id"] != "P-02"]
    with pytest.raises(ValueError, match="P-02"):
        skip_plan_relation_check(no_p02)

    wrong_section = copy.deepcopy(CONFIG)
    for criterion in wrong_section["criteria"]:
        if criterion["id"] == "P-02":
            criterion["section"] = "S"
    with pytest.raises(ValueError, match="not a Plan criterion"):
        skip_plan_relation_check(wrong_section)


# --- operator purity and registry round-trip ----------------------------------


def test_operators_never_mutate_the_base_evaluator_or_the_request() -> None:
    canned = _response([_finding("O-01", "O", "present", [_span(0, 5, "O: ch")])])
    frozen_response = copy.deepcopy(canned)
    request = {"note_id": "n1", "note_text": "O: Vitals: normal."}
    frozen_request = copy.deepcopy(request)
    base = _stub_evaluator(canned)

    for operator in (
        remove_section_check(CONFIG, section="O"),
        drop_evidence_spans(),
        flip_finding_statuses(),
        skip_plan_relation_check(CONFIG),
    ):
        mutant = operator.apply(base)
        mutant(request)
        assert request == frozen_request, f"{operator.op_id} mutated the request"
    assert canned == frozen_response, "an operator mutated the base evaluator's response"


def test_registry_rebuilds_behaviorally_identical_mutants() -> None:
    canned = _response([_finding("O-01", "O", "present", [_span(0, 5, "O: ch")])])
    for operator in (
        remove_section_check(CONFIG, section="O"),
        drop_evidence_spans(),
        flip_finding_statuses(),
        skip_plan_relation_check(CONFIG),
    ):
        entry = OPERATOR_REGISTRY[operator.op_name]
        rebuilt = (
            entry.constructor(CONFIG, **operator.args)
            if entry.requires_config
            else entry.constructor(**operator.args)
        )
        original = operator.apply(_stub_evaluator(canned))(REQUEST)
        rebuilt_out = rebuilt.apply(_stub_evaluator(canned))(REQUEST)
        assert json.dumps(original, sort_keys=True) == json.dumps(rebuilt_out, sort_keys=True), (
            f"{operator.op_id} does not round-trip through the registry"
        )


# --- round honesty rules -------------------------------------------------------


def test_vacuous_mutant_is_flagged_and_excluded_from_the_share() -> None:
    # The stub evaluator never emits Objective findings, so remove-O changes
    # nothing on any probe (vacuous); the flip does change outputs. The stub
    # suite never fails, so the only valid mutant escapes: share 0.0 over one
    # valid mutant — and the vacuous one is excluded, not counted as detected.
    report = run_injection_round(
        run_id="vacuous-round",
        module="qualityforge.tests.stub_evaluator_module",
        factory="create_evaluator",
        config_path=DEFAULT_CONFIG_PATH,
        suite_runner=_StubRunner(_passing(), _passing(), _passing()),
        operators=[
            remove_section_check(CONFIG, section="O"),
            flip_finding_statuses(),
        ],
        probes=[note.request() for note in REFERENCE_NOTES],
    )
    remove_result = next(m for m in report.mutants if m.op_id == "remove-section-check-o")
    flip_result = next(m for m in report.mutants if m.op_id == "flip-finding-statuses")
    assert remove_result.vacuous and not remove_result.detected
    assert not flip_result.vacuous and not flip_result.detected
    assert report.mutants_total == 2
    assert report.mutants_detected == 0
    assert report.detection_share == 0.0
    assert report.r1_threshold_met is False


def test_baseline_failure_raises_and_never_injects() -> None:
    with pytest.raises(SuiteBaselineError, match="must pass against the validated implementation"):
        _round([drop_evidence_spans()], _StubRunner(_failing()))


def test_vacuous_but_failing_suite_is_a_consistency_error() -> None:
    # A vacuous mutant whose suite run fails means the suite is flaky or the
    # harness is broken — either way the result must not be reported.
    report_operators = [remove_section_check(CONFIG, section="O")]
    with pytest.raises(HarnessConsistencyError, match="flaky suite or a harness bug"):
        run_injection_round(
            run_id="inconsistent-round",
            module="qualityforge.tests.stub_evaluator_module",
            factory="create_evaluator",
            config_path=DEFAULT_CONFIG_PATH,
            suite_runner=_StubRunner(_passing(), _failing()),
            operators=report_operators,
            probes=[note.request() for note in REFERENCE_NOTES],
        )


def test_round_needs_at_least_one_probe() -> None:
    with pytest.raises(ValueError, match="at least one probe"):
        run_injection_round(
            run_id="no-probes",
            module=DEFAULT_MODULE,
            factory="create_evaluator",
            config_path=DEFAULT_CONFIG_PATH,
            suite_runner=_StubRunner(_passing()),
            operators=[drop_evidence_spans()],
            probes=[],
        )


# --- report: section 8.5 conventions ------------------------------------------


def test_report_follows_section_8_5_conventions() -> None:
    # Real reference evaluator + real probes; the stub suite fails on every
    # mutant, so all four defects are detected.
    report = _round(
        [
            remove_section_check(CONFIG, section="O"),
            drop_evidence_spans(),
            flip_finding_statuses(),
            skip_plan_relation_check(CONFIG),
        ],
        _StubRunner(_passing(), *([_failing()] * 4)),
    )
    data = report.to_dict()

    assert data["report_type"] == "defect_injection_detection"
    assert data["criteria_name"] == "soap-note-completeness"
    assert data["criteria_version"] == "0.1.0"
    assert data["baseline"] == {"passed": 3, "failed": 0}
    assert [c["id"] for c in data["criteria_tested"]] == ["O-01", "O-02", "P-02"]
    assert len(data["contract_targets"]) == 2  # evidence-drop and status-flip are contract-level
    assert data["mutants_total"] == 4 and data["mutants_detected"] == 4
    assert data["detection_share"] == 1.0
    assert data["r1_threshold_met"] is True
    # The harness records; repair is the Debugging Agent's loop (spec section 6).
    assert data["repair_attempts"] == []
    assert data["disclaimer"] == DISCLAIMER
    assert data["limitations"]

    rendered = report.render_markdown()
    for fragment in (
        "## Tests passed and failed",
        "## Detection share",
        "## Criteria tested",
        "## Repair attempts",
        "## Remaining known limitations",
        DISCLAIMER,
        "100%",
    ):
        assert fragment in rendered, f"missing {fragment!r} in the rendered report"


def test_report_saves_as_json_artifact(tmp_path: Path) -> None:
    report = _round(
        [remove_section_check(CONFIG, section="O")],
        _StubRunner(_passing(), _failing()),
    )
    path = report.save(tmp_path / "detection-report.json")
    reloaded = json.loads(path.read_text(encoding="utf-8"))
    assert reloaded["detection_share"] == 1.0
    assert reloaded["mutants"][0]["op_id"] == "remove-section-check-o"
    assert reloaded["mutants"][0]["spec"]["operators"] == [
        {"op": "remove_section_check", "args": {"section": "O"}}
    ]


def test_spec_round_trip_through_evaluator_from_spec() -> None:
    operator = remove_section_check(CONFIG, section="O")
    spec = build_evaluator_spec(
        DEFAULT_MODULE, "create_evaluator", DEFAULT_CONFIG_PATH, (operator,)
    )
    mutant = evaluator_from_spec(spec)
    response = mutant({"note_id": "note-complete", "note_text": REFERENCE_NOTES[0].text})
    ids = {f["criterion_id"] for f in response["findings"]}
    assert "O-01" not in ids and "O-02" not in ids
    assert "S-01" in ids
    assert EVALUATOR_SPEC_ENV_VAR == "QUALITYFORGE_EVALUATOR_SPEC"  # the seam the suites rely on
