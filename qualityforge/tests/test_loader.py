"""Tests for the evaluator-under-test loader seam (review R1 plumbing)."""

import copy
import json

import pytest

from qualityforge.harness.fixtures.reference_evaluator import create_evaluator
from qualityforge.harness.fixtures.reference_suite import (
    REFERENCE_CHECKS,
    REFERENCE_NOTES,
)
from qualityforge.harness.inject import (
    EvaluatorSpecError,
    evaluator_from_spec,
    remove_section_check,
)
from qualityforge.harness.loader import (
    DEFAULT_CONFIG_PATH,
    EVALUATOR_SPEC_ENV_VAR,
    default_spec,
    get_config_under_test,
    get_evaluator_under_test,
    parse_spec_text,
)


def _set_spec(monkeypatch, spec: dict | None) -> None:
    if spec is None:
        monkeypatch.delenv(EVALUATOR_SPEC_ENV_VAR, raising=False)
    else:
        monkeypatch.setenv(EVALUATOR_SPEC_ENV_VAR, json.dumps(spec))


def test_default_load_is_the_pristine_reference_evaluator(monkeypatch) -> None:
    _set_spec(monkeypatch, None)
    evaluator = get_evaluator_under_test()
    config = get_config_under_test()
    for check in REFERENCE_CHECKS:
        check(evaluator, config)  # agreement at baseline, per R1
    assert config["criteria_version"] == "0.1.0"


def test_env_spec_selects_a_mutant(monkeypatch) -> None:
    operator = remove_section_check(get_config_under_test(), section="O")
    spec = copy.deepcopy(default_spec())
    spec["operators"] = [{"op": operator.op_name, "args": operator.args}]
    _set_spec(monkeypatch, spec)

    evaluator = get_evaluator_under_test()
    response = evaluator(REFERENCE_NOTES[0].request())
    ids = {finding["criterion_id"] for finding in response["findings"]}
    assert "O-01" not in ids and "O-02" not in ids  # the defect is live in-process
    assert "S-01" in ids


def test_malformed_env_spec_raises_with_the_variable_named(monkeypatch) -> None:
    monkeypatch.setenv(EVALUATOR_SPEC_ENV_VAR, "{not json")
    with pytest.raises(EvaluatorSpecError, match=EVALUATOR_SPEC_ENV_VAR):
        get_evaluator_under_test()


def test_spec_missing_required_keys_raises(monkeypatch) -> None:
    monkeypatch.setenv(EVALUATOR_SPEC_ENV_VAR, json.dumps({"module": "x"}))
    with pytest.raises(EvaluatorSpecError, match="factory"):
        get_evaluator_under_test()


def test_parse_spec_text_rejects_non_objects() -> None:
    with pytest.raises(EvaluatorSpecError):
        parse_spec_text(json.dumps(["not", "an", "object"]))


def test_spec_with_unknown_operator_raises_before_any_suite_runs() -> None:
    spec = {
        "module": "qualityforge.harness.fixtures.reference_evaluator",
        "factory": "create_evaluator",
        "config_path": str(DEFAULT_CONFIG_PATH),
        "operators": [{"op": "does_not_exist", "args": {}}],
    }
    with pytest.raises(EvaluatorSpecError, match="unknown operator"):
        evaluator_from_spec(spec)


def test_wrong_factory_name_fails_loudly() -> None:
    # A wrong factory name must fail loudly rather than silently loading a default.
    spec = copy.deepcopy(default_spec())
    spec["factory"] = "not_a_real_factory"
    with pytest.raises(EvaluatorSpecError, match="not_a_real_factory"):
        evaluator_from_spec(spec)
    assert create_evaluator is not None  # the real factory exists under its own name
