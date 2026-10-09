"""Run 1 workload spec assets: acceptance criteria and criteria config v1.

Validates the of-record criteria config against the scaffold's schema
(spec sections 8.2 and 9), checks the acceptance-criteria file's structure
(spec section 7.1), and pins the review amendments (R1, R3, R4, R5).
"""

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from qualityforge.tools.validate import EXIT_VALID, load_config, validate_criteria

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKLOAD_DIR = Path(__file__).resolve().parents[1] / "workloads" / "soap-evaluator"
CRITERIA_V1 = WORKLOAD_DIR / "criteria-v1.yaml"
ACCEPTANCE = WORKLOAD_DIR / "acceptance-criteria.yaml"
REQUIREMENT = Path(__file__).resolve().parents[1] / "requirements" / "run-1-soap.md"

SECTION_8_2_IDS = {"S-01", "S-02", "O-01", "O-02", "A-01", "P-01", "P-02", "X-01"}
CHECK_TYPES = {"unit_test", "schema_check", "behavior_check"}
SOURCES = {"requirement", "assumption"}

# Spec section 8.1, quoted verbatim in the Run 1 requirement input.
VERBATIM_REQUIREMENT = (
    "Build a Python API that evaluates the clinical completeness of SOAP notes. It must "
    "identify missing sections, return structured findings with supporting evidence, "
    "generate unit tests, execute those tests, fix implementation defects, and produce "
    "an evaluation report."
)


# --- criteria config v1 (spec section 8.2) ------------------------------------


def test_criteria_v1_validates_against_scaffold_schema() -> None:
    """Acceptance: the of-record config passes the T1 schema + semantic checks."""
    assert validate_criteria(load_config(CRITERIA_V1)) == []


def test_criteria_v1_validates_via_documented_cli() -> None:
    """The validator's documented usage path works on the of-record config."""
    result = subprocess.run(
        [sys.executable, "-m", "qualityforge.tools.validate", "criteria", str(CRITERIA_V1)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == EXIT_VALID, result.stdout + result.stderr


def test_criteria_v1_covers_section_8_2() -> None:
    """Every rule of spec section 8.2 is present in the versioned config."""
    config = load_config(CRITERIA_V1)
    assert {criterion["id"] for criterion in config["criteria"]} == SECTION_8_2_IDS


def test_criteria_v1_pins_evidence_span_semantics() -> None:
    """Review R3: one span definition, inherited by every downstream agent."""
    config = load_config(CRITERIA_V1)
    assert config["evidence_span_semantics"] == {
        "offset_base": "character",
        "index_origin": "zero",
        "end_exclusive": True,
        "reference_text": "raw note_text from the request",
        "normalization": "none",
    }


def test_criteria_v1_section_detection_is_configured_not_hardcoded() -> None:
    """Review R5: header markers plus a documented fallback, versioned in config."""
    detection = load_config(CRITERIA_V1)["section_detection"]
    assert detection["strategy"] == "header_markers_with_fallback"
    assert all(detection["header_markers"][section] for section in "SOAP")
    assert detection["fallback"].strip()


# --- acceptance criteria (spec section 7.1 output shape) ----------------------


@pytest.fixture
def acceptance() -> dict[str, Any]:
    return load_config(ACCEPTANCE)


def test_acceptance_criteria_are_well_formed(acceptance: dict[str, Any]) -> None:
    """Every criterion has an ID, a plain statement, and a verifiable check type."""
    criteria = acceptance["criteria"]
    assert criteria, "acceptance criteria file must not be empty"
    ids = [criterion["id"] for criterion in criteria]
    assert len(ids) == len(set(ids)), "duplicate acceptance criterion ids"
    for criterion in criteria:
        assert criterion["id"]
        assert criterion["statement"].strip()
        assert criterion["check_type"] in CHECK_TYPES
        assert criterion["source"] in SOURCES
        if criterion["source"] == "assumption":
            assert criterion.get("note"), "assumptions record their note explicitly"


def test_acceptance_criteria_pin_review_amendments(acceptance: dict[str, Any]) -> None:
    """The review's pins are represented as criteria, not prose (R1, R3, R4)."""
    by_id = {criterion["id"]: criterion["statement"] for criterion in acceptance["criteria"]}
    # R3: span semantics pinned to offsets into raw note_text.
    assert "zero-based" in by_id["AC-04"]
    assert "end-exclusive" in by_id["AC-04"]
    # R4: determinism as byte-identical repeat-call behavior.
    assert "byte-identical" in by_id["AC-05"]
    # R1: the defect-injection round and the repair loop are acceptance criteria.
    assert "injected" in by_id["AC-09"] and "80" in by_id["AC-09"]
    assert "repair" in by_id["AC-10"].lower()


def test_run_1_requirement_is_verbatim() -> None:
    """The Run 1 input quotes spec section 8.1 without paraphrase."""
    assert VERBATIM_REQUIREMENT in REQUIREMENT.read_text(encoding="utf-8")
