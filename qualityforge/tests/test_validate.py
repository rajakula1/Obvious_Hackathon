"""Tests for qualityforge.tools.validate (spec sections 8.2 and 9, review R2)."""

import json
from pathlib import Path

import pytest

from qualityforge.tools.validate import (
    EXIT_ERROR,
    EXIT_INVALID,
    EXIT_VALID,
    load_config,
    main,
    recheck_manifest_hashes,
    sha256_file,
    validate_criteria,
    validate_manifest,
)

SCHEMAS_DIR = Path(__file__).resolve().parents[1] / "schemas"
EXAMPLE_CRITERIA = SCHEMAS_DIR / "completeness-criteria.example.yaml"

VALID_MANIFEST = {
    "manifest_version": "1.0",
    "run_id": "run-2026-10-09-01",
    "recorded_at": "2026-10-09T12:00:00Z",
    "recorded_by": "orchestrator",
    "test_files": [
        {"path": "tests/test_evaluate.py", "sha256": "a" * 64, "criteria_refs": ["S-01"]},
    ],
}


# --- completeness-criteria config (spec section 8.2) -------------------------


def test_example_criteria_config_validates() -> None:
    """Acceptance: the schema validates a sample criteria file."""
    assert validate_criteria(load_config(EXAMPLE_CRITERIA)) == []


def test_example_is_the_section_8_2_starting_set() -> None:
    config = load_config(EXAMPLE_CRITERIA)
    ids = {criterion["id"] for criterion in config["criteria"]}
    assert ids == {"S-01", "S-02", "O-01", "O-02", "A-01", "P-01", "P-02", "X-01"}


def test_missing_required_field_is_rejected() -> None:
    config = load_config(EXAMPLE_CRITERIA)
    del config["criteria_version"]
    assert any("criteria_version" in error for error in validate_criteria(config))


def test_unknown_check_type_is_rejected() -> None:
    config = load_config(EXAMPLE_CRITERIA)
    config["criteria"][0]["check_type"] = "vibes"
    assert any("check_type" in error for error in validate_criteria(config))


def test_unknown_property_is_rejected() -> None:
    config = load_config(EXAMPLE_CRITERIA)
    config["criteria"][0]["checktype"] = "behavior_check"  # typo'd key
    assert validate_criteria(config)


def test_assumption_without_note_is_rejected() -> None:
    config = load_config(EXAMPLE_CRITERIA)
    config["criteria"][0]["source"] = "assumption"
    errors = validate_criteria(config)
    assert any("assumption" in error and "S-01" in error for error in errors)


def test_assumption_with_note_is_accepted() -> None:
    config = load_config(EXAMPLE_CRITERIA)
    config["criteria"][0]["source"] = "assumption"
    config["criteria"][0]["note"] = "Assumed vitals parse from free text; flagged in Run #1."
    assert validate_criteria(config) == []


def test_duplicate_criterion_ids_are_rejected() -> None:
    config = load_config(EXAMPLE_CRITERIA)
    config["criteria"].append(dict(config["criteria"][0]))
    assert any("duplicate criterion id" in error for error in validate_criteria(config))


def test_evidence_span_semantics_are_pinned_to_review_r3() -> None:
    config = load_config(EXAMPLE_CRITERIA)
    assert config["evidence_span_semantics"] == {
        "offset_base": "character",
        "index_origin": "zero",
        "end_exclusive": True,
        "reference_text": "raw note_text from the request",
        "normalization": "none",
    }
    config["evidence_span_semantics"]["end_exclusive"] = False
    assert validate_criteria(config)  # the schema pins the R3 semantics


# --- test manifest (review R2) ------------------------------------------------


@pytest.fixture(name="test_tree")
def test_tree_fixture(tmp_path: Path) -> Path:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_evaluate.py").write_text(
        "def test_complete_note_is_complete():\n    assert True\n", encoding="utf-8"
    )
    return tmp_path


def manifest_with_hashes(test_tree: Path) -> dict:
    test_file = test_tree / "tests" / "test_evaluate.py"
    return {
        **VALID_MANIFEST,
        "test_files": [{"path": "tests/test_evaluate.py", "sha256": sha256_file(test_file)}],
    }


def test_valid_manifest_passes_schema_and_hash_recheck(test_tree: Path) -> None:
    manifest = manifest_with_hashes(test_tree)
    assert validate_manifest(manifest) == []
    assert recheck_manifest_hashes(manifest, test_tree) == []


def test_hash_recheck_detects_tampered_test_file(test_tree: Path) -> None:
    """The R2 Verify gate: any change to a recorded test file fails the gate."""
    manifest = manifest_with_hashes(test_tree)
    test_file = test_tree / "tests" / "test_evaluate.py"
    test_file.write_text(
        "def test_complete_note_is_complete():\n    assert True  # weakened\n",
        encoding="utf-8",
    )
    errors = recheck_manifest_hashes(manifest, test_tree)
    assert len(errors) == 1
    assert "sha256 mismatch" in errors[0]


def test_hash_recheck_reports_missing_test_file(test_tree: Path) -> None:
    manifest = {
        **VALID_MANIFEST,
        "test_files": [{"path": "tests/test_gone.py", "sha256": "a" * 64}],
    }
    errors = recheck_manifest_hashes(manifest, test_tree)
    assert len(errors) == 1
    assert "not found" in errors[0]


def test_manifest_rejects_unsafe_paths() -> None:
    manifest = {
        **VALID_MANIFEST,
        "test_files": [{"path": "../escape.py", "sha256": "a" * 64}],
    }
    assert any("unsafe" in error for error in validate_manifest(manifest))


def test_manifest_rejects_malformed_sha256() -> None:
    manifest = {
        **VALID_MANIFEST,
        "test_files": [{"path": "tests/test_evaluate.py", "sha256": "XYZ"}],
    }
    assert any("sha256" in error for error in validate_manifest(manifest))


def test_manifest_rejects_non_iso_timestamp() -> None:
    manifest = {**VALID_MANIFEST, "recorded_at": "yesterday"}
    assert any("ISO-8601" in error for error in validate_manifest(manifest))


def test_manifest_rejects_duplicate_paths() -> None:
    entry = {"path": "tests/test_evaluate.py", "sha256": "a" * 64}
    manifest = {**VALID_MANIFEST, "test_files": [entry, dict(entry)]}
    assert any("duplicate manifest path" in error for error in validate_manifest(manifest))


# --- CLI ----------------------------------------------------------------------


def test_cli_valid_config_exits_zero() -> None:
    assert main(["criteria", str(EXAMPLE_CRITERIA)]) == EXIT_VALID


def test_cli_invalid_config_exits_one(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("criteria: []\n", encoding="utf-8")  # missing every other field
    assert main(["criteria", str(bad)]) == EXIT_INVALID


def test_cli_missing_file_exits_two(tmp_path: Path) -> None:
    assert main(["criteria", str(tmp_path / "nope.yaml")]) == EXIT_ERROR


def test_cli_manifest_with_repo_root_recheck(test_tree: Path) -> None:
    manifest = manifest_with_hashes(test_tree)
    manifest_path = test_tree / "test-manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    assert main(["manifest", str(manifest_path), "--repo-root", str(test_tree)]) == EXIT_VALID
