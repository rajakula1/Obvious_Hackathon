"""Shared fixtures for the generated SOAP-evaluator suite.

The suite exercises the evaluator through the app's seam: with
QUALITYFORGE_EVALUATOR_SPEC unset (repository CI, a plain pytest run),
create_app() binds the generated baseline evaluator; when the harness
runner sets the variable for an injection round, create_app() resolves
the evaluator AND config through the harness loader (§12.3, review R1).

This conftest deliberately does NOT set the environment variable itself:
it is process-global in a combined pytest run and would leak into sibling
suites that expect the loader default (the reference evaluator). The
injection runner sets it explicitly per subprocess.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from qualityforge.generated.soap_evaluator import create_app, load_criteria

REPO_ROOT = Path(__file__).resolve().parents[3]
GENERATED_MODULE = "qualityforge.generated.soap_evaluator"
GENERATED_FACTORY = "create_evaluator"
NOTES_DIR = REPO_ROOT / "qualityforge/workloads/soap-evaluator/data/notes"


def load_corpus() -> list[dict]:
    """All labeled corpus notes in stable note_id order."""
    records = [
        json.loads(p.read_text(encoding="utf-8")) for p in sorted(NOTES_DIR.glob("soap-*.json"))
    ]
    return sorted(records, key=lambda r: r["note_id"])


@pytest.fixture(scope="module")
def config():
    """The criteria config the app itself loads (same source, one truth)."""
    return load_criteria()


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app())


@pytest.fixture(scope="module")
def corpus():
    return load_corpus()
