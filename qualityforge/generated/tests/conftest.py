"""Shared fixtures for the Run 2 generated SOAP-evaluator suite (stage 5, T1).

Seam law (§12.3, review R1; stage-2 spec section 3): the evaluator AND the
criteria config under test are resolved ONLY through the harness loader seam —
never imported from the implementation. With ``QUALITYFORGE_EVALUATOR_SPEC``
set (the injection round: baseline spec or a mutant spec), this suite resolves
exactly what the harness serialized. With it unset (plain ``pytest
qualityforge/``), the suite's default spec names the generated baseline —
``qualityforge.generated.soap_evaluator:create_evaluator`` over the of-record
config ``qualityforge/workloads/soap-evaluator/criteria-v1.yaml``.

This conftest deliberately does NOT set the environment variable itself: the
variable is process-global in a combined pytest run, and a sibling suite (the
reference suite) resolves ``get_evaluator_under_test()`` at import time and
expects the loader default. Instead both fixtures read the variable through
``loader.parse_spec_text`` and fall back to the generated-baseline spec — same
parse, same build path as the harness, zero global side effects.

All API tests run in-process: ``TestClient`` over the app module named by the
resolved spec — no bound ports, no network loopback (review R6).
"""

from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from qualityforge.harness import loader
from qualityforge.harness.inject import (
    EVALUATOR_SPEC_ENV_VAR,
    build_evaluator_spec,
    evaluator_from_spec,
    load_config,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
GENERATED_MODULE = "qualityforge.generated.soap_evaluator"
GENERATED_FACTORY = "create_evaluator"
OF_RECORD_CONFIG = REPO_ROOT / "qualityforge/workloads/soap-evaluator/criteria-v1.yaml"
NOTES_DIR = REPO_ROOT / "qualityforge/workloads/soap-evaluator/data/notes"


def baseline_spec() -> dict[str, Any]:
    """The generated-baseline evaluator spec, held to the harness's own
    validation by parsing it through the loader (a default that would not
    parse is a bug this suite must hit, not hide)."""
    spec = build_evaluator_spec(GENERATED_MODULE, GENERATED_FACTORY, OF_RECORD_CONFIG, ())
    return loader.parse_spec_text(json.dumps(spec))


def seam_spec() -> dict[str, Any]:
    """The evaluator spec in force: harness-provided (baseline or mutant)
    when QUALITYFORGE_EVALUATOR_SPEC is set, the generated baseline otherwise."""
    raw = os.environ.get(EVALUATOR_SPEC_ENV_VAR, "")
    return loader.parse_spec_text(raw) if raw.strip() else baseline_spec()


def load_corpus() -> list[dict]:
    """All labeled corpus notes in stable note_id order."""
    records = [
        json.loads(p.read_text(encoding="utf-8")) for p in sorted(NOTES_DIR.glob("soap-*.json"))
    ]
    return sorted(records, key=lambda r: r["note_id"])


@pytest.fixture(scope="module")
def config() -> Any:
    """The criteria config of the evaluator under test — via the seam."""
    return load_config(seam_spec()["config_path"])


@pytest.fixture(scope="module")
def evaluator() -> Any:
    """The evaluator under test — via the seam (pristine baseline here,
    a wrapped mutant during an injection round)."""
    return evaluator_from_spec(seam_spec())


@pytest.fixture(scope="module")
def app_module() -> Any:
    """The app module named by the resolved spec — the same module string the
    harness resolves; never a direct implementation import in this suite."""
    return importlib.import_module(str(seam_spec()["module"]))


@pytest.fixture(scope="module")
def client(app_module: Any) -> TestClient:
    """In-process client over the app built from the seam-named module (R6)."""
    return TestClient(app_module.create_app())


@pytest.fixture(scope="module")
def corpus() -> list[dict]:
    return load_corpus()
