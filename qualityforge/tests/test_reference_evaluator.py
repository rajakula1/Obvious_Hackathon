"""Unit tests for the reference evaluator fixture itself.

The harness can only be trusted if the "validated implementation" it injects
defects into is itself correct: these pin the section 8.2 behavior, the R3
evidence-span semantics, and the determinism requirement directly.
"""

import copy
import json
from pathlib import Path

import pytest

from qualityforge.harness.fixtures.reference_evaluator import (
    create_evaluator,
    identify_sections,
)
from qualityforge.harness.fixtures.reference_suite import (
    NOTE_COMPLETE,
    NOTE_MISSING_OBJECTIVE,
    LabeledNote,
)
from qualityforge.harness.inject import load_config

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG = load_config(REPO_ROOT / "qualityforge" / "schemas" / "completeness-criteria.example.yaml")
EVALUATOR = create_evaluator(CONFIG)

# Two plan items: one tied to the diagnosis ("acute bronchitis"), one not.
NOTE_MIXED_PLAN = LabeledNote(
    note_id="note-mixed-plan",
    visit_type="follow-up",
    text=(
        "S: Chief complaint: Persistent cough for five days.\n"
        "HPI: Patient reports a dry cough worsening at night, no fever.\n"
        "O: Vitals: Temp 37.1 C, HR 82, BP 118/76, SpO2 98 percent.\n"
        "Exam: Chest clear to auscultation bilaterally.\n"
        "A: Diagnosis: Acute bronchitis.\n"
        "P: Plan:\n"
        "- Continue supportive care for acute bronchitis.\n"
        "- Schedule a same-day follow-up call.\n"
    ),
    expected_status={},
    expected_overall="incomplete",  # P-02 is partial, so not all criteria are present
)


def test_sections_are_identified_in_document_order() -> None:
    spans = identify_sections(NOTE_COMPLETE.text, CONFIG["section_detection"]["header_markers"])
    assert set(spans) == {"S", "O", "A", "P"}
    assert spans["S"][0] < spans["O"][0] < spans["A"][0] < spans["P"][0]
    for section, (start, _end) in spans.items():
        assert NOTE_COMPLETE.text[start].upper() == section  # each span starts at its marker


def test_every_evidence_span_matches_the_raw_text() -> None:
    response = EVALUATOR(NOTE_COMPLETE.request())
    for finding in response["findings"]:
        for span in finding["evidence"]:
            assert NOTE_COMPLETE.text[span["start"] : span["end"]] == span["text"]


def test_plan_partially_related_to_assessment_is_partial() -> None:
    response = EVALUATOR(NOTE_MIXED_PLAN.request())
    by_id = {f["criterion_id"]: f for f in response["findings"]}
    assert by_id["P-02"]["status"] == "partial"
    assert response["overall_status"] == "incomplete"


def test_note_without_any_markers_is_fully_missing() -> None:
    note = LabeledNote(
        note_id="note-no-markers",
        visit_type="intake",
        text="Free text with no section markers at all, and no criteria content.",
        expected_status={},
        expected_overall="incomplete",
    )
    response = EVALUATOR(note.request())
    assert all(f["status"] == "missing" for f in response["findings"])
    structure = next(f for f in response["findings"] if f["criterion_id"] == "X-01")
    assert structure["status"] == "missing"
    assert structure["section"] is None  # structure criteria are section-less


def test_determinism_two_calls_are_byte_identical() -> None:
    first = json.dumps(EVALUATOR(NOTE_COMPLETE.request()), sort_keys=True)
    second = json.dumps(EVALUATOR(NOTE_COMPLETE.request()), sort_keys=True)
    assert first == second


def test_unknown_criterion_id_fails_loudly() -> None:
    config = copy.deepcopy(CONFIG)
    config["criteria"].append(
        {
            "id": "Z-99",
            "statement": "Test-only criterion outside the starting set.",
            "section": "S",
        }
    )
    evaluator = create_evaluator(config)
    with pytest.raises(ValueError, match="Z-99"):
        evaluator(NOTE_COMPLETE.request())


def test_structure_criterion_spans_each_found_section_header() -> None:
    response = EVALUATOR(NOTE_COMPLETE.request())
    structure = next(f for f in response["findings"] if f["criterion_id"] == "X-01")
    assert structure["status"] == "present"
    assert len(structure["evidence"]) == 4  # one span per identified section
    # Missing one section -> Structure criterion degrades to partial.
    response = EVALUATOR(NOTE_MISSING_OBJECTIVE.request())
    structure = next(f for f in response["findings"] if f["criterion_id"] == "X-01")
    assert structure["status"] == "partial"
    assert len(structure["evidence"]) == 3
