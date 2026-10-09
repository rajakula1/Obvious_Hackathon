"""Evaluator-under-test seam for the defect-injection harness.

Suite processes — the reference suite here, the factory's generated suite in
Run #1 — obtain the evaluator they exercise from this module instead of
importing an implementation directly. With QUALITYFORGE_EVALUATOR_SPEC unset
the loader returns the pristine reference evaluator; when the harness runner
sets the variable it carries a serialized evaluator spec (inject.py) naming
the implementation module, its factory, the criteria config, and the mutation
operators to apply. That is how one pytest suite runs unchanged against the
validated implementation and against every mutant (review R1), with the
suite itself in-process per the review R6 budget rule.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from qualityforge.harness.inject import (
    EVALUATOR_SPEC_ENV_VAR,
    Evaluator,
    EvaluatorSpecError,
    build_evaluator_spec,
    evaluator_from_spec,
    load_config,
)

_SCHEMAS_DIR = Path(__file__).resolve().parents[1] / "schemas"
DEFAULT_CONFIG_PATH = _SCHEMAS_DIR / "completeness-criteria.example.yaml"
DEFAULT_MODULE = "qualityforge.harness.fixtures.reference_evaluator"
DEFAULT_FACTORY = "create_evaluator"


def default_spec() -> dict[str, Any]:
    """Spec for the pristine reference evaluator with the example criteria."""
    return build_evaluator_spec(DEFAULT_MODULE, DEFAULT_FACTORY, DEFAULT_CONFIG_PATH, ())


def parse_spec_text(raw: str) -> dict[str, Any]:
    """Parse a serialized evaluator spec, failing loudly on malformed input."""
    try:
        spec = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise EvaluatorSpecError(f"{EVALUATOR_SPEC_ENV_VAR} is not valid JSON: {exc}") from exc
    required = {"module", "factory", "config_path"}
    if not isinstance(spec, dict) or not required.issubset(spec):
        raise EvaluatorSpecError(
            f"{EVALUATOR_SPEC_ENV_VAR} must be a JSON object with keys {sorted(required)}"
        )
    return spec


def _spec_from_env() -> dict[str, Any] | None:
    raw = os.environ.get(EVALUATOR_SPEC_ENV_VAR, "")
    return parse_spec_text(raw) if raw.strip() else None


def get_evaluator_under_test() -> Evaluator:
    """The evaluator this process should exercise: pristine default or mutant."""
    spec = _spec_from_env()
    return evaluator_from_spec(spec if spec is not None else default_spec())


def get_config_under_test() -> Any:
    """The criteria config of the evaluator under test (same spec source)."""
    spec = _spec_from_env()
    config_path = spec["config_path"] if spec is not None else DEFAULT_CONFIG_PATH
    return load_config(Path(config_path))
