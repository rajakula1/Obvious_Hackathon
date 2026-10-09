"""Tests for qualityforge.tools.validate_dataset (spec sections 8.4 and 11.1).

The real corpus under qualityforge/workloads/soap-evaluator/data is the
fixture: the suite re-runs every validator check against it (so CI fails if a
corpus edit drifts from the manifest or the criteria config) and exercises the
validator's failure paths on mutated copies.
"""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from qualityforge.tools.validate import load_config, validate_criteria
from qualityforge.tools.validate_dataset import (
    CATEGORIES,
    MAX_NOTES,
    MIN_NOTES,
    load_notes,
    scan_phi,
    validate_manifest,
    validate_records,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "qualityforge" / "workloads" / "soap-evaluator" / "data"
CRITERIA_PATH = REPO_ROOT / "qualityforge" / "workloads" / "soap-evaluator" / "criteria-v1.yaml"
MANIFEST_PATH = DATA_DIR / "corpus.manifest.json"


@pytest.fixture(name="criteria")
def criteria_config() -> dict:
    return load_config(CRITERIA_PATH)


@pytest.fixture(name="loaded")
def loaded_corpus() -> list[tuple[Path, dict]]:
    loaded, errors = load_notes(DATA_DIR)
    assert errors == []
    return loaded


@pytest.fixture(name="manifest")
def corpus_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_real_corpus_records_are_valid(criteria: dict, loaded: list) -> None:
    """Acceptance: the committed corpus passes every structure + label check."""
    assert validate_records(loaded, criteria) == []


def test_real_corpus_matches_manifest(criteria: dict, loaded: list, manifest: dict) -> None:
    """Acceptance: manifest counts and per-note digests match the corpus (re-hash)."""
    assert validate_manifest(manifest, DATA_DIR, loaded) == []


def test_real_corpus_criteria_config_is_valid(criteria: dict) -> None:
    assert validate_criteria(criteria) == []


def test_phi_scan_returns_zero_hits(loaded: list) -> None:
    """Acceptance (spec section 11.1): zero PHI-pattern hits over every string."""
    hits: list[tuple[str, int]] = []
    for _, record in loaded:
        for text in record.values():
            if isinstance(text, str):
                hits.extend(scan_phi(text))
    assert hits == []


def test_corpus_size_within_contract(loaded: list) -> None:
    assert MIN_NOTES <= len(loaded) <= MAX_NOTES


def test_labels_cover_every_criterion_in_config_order(criteria: dict, loaded: list) -> None:
    criterion_order = [criterion["id"] for criterion in criteria["criteria"]]
    for _, record in loaded:
        finding_ids = [finding["criterion_id"] for finding in record["expected"]["findings"]]
        assert finding_ids == criterion_order


def test_overall_status_consistent_with_findings(loaded: list) -> None:
    for _, record in loaded:
        all_present = all(f["status"] == "present" for f in record["expected"]["findings"])
        assert record["expected"]["overall_status"] == ("complete" if all_present else "incomplete")


def test_corpus_spans_all_brief_categories(loaded: list) -> None:
    """The brief's coverage: complete, per-section removals, corruption, and edge cases."""
    categories = {record["category"] for _, record in loaded}
    assert categories == CATEGORIES


def test_manifest_rehash_detects_drift(
    criteria: dict, loaded: list, manifest: dict, tmp_path: Path
) -> None:
    """A note file changed after the manifest was recorded must fail the re-hash."""
    tampered = deepcopy(loaded[0][1])
    tampered["note_text"] += " Appended after finalization."
    notes_dir = tmp_path / "notes"
    notes_dir.mkdir()
    path = notes_dir / loaded[0][0].name
    path.write_text(json.dumps(tampered, indent=2) + "\n", encoding="utf-8")
    errors = validate_manifest(manifest, tmp_path, [(path, tampered)])
    assert any("sha256 mismatch" in error for error in errors)


def test_phi_scan_detects_injected_identifier() -> None:
    text = "O: Vitals stable. MRN 4839201. Contact 555-867-5309 or a.b@example.com."
    detected = {name for name, _ in scan_phi(text)}
    assert detected >= {"mrn_label", "phone_number", "email_address", "long_digit_run"}


def test_duplicate_note_id_is_rejected(criteria: dict, loaded: list) -> None:
    duplicated = deepcopy(loaded)
    duplicated[1] = (duplicated[1][0], deepcopy(duplicated[0][1]))
    errors = validate_records(duplicated, criteria)
    assert any("duplicate note_id" in error for error in errors)
