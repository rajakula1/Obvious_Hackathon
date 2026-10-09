"""Reference suite: labeled synthetic notes and contract-level checks.

The suite the smoke round executes against every mutant (spec section 12.3,
review R1). The notes are synthetic (spec section 8.4, section 11.1) and each
carries a labeled expected result per criterion — the labels are derived from
how the note was constructed, never from reading the implementation, which is
what keeps the suite from being self-confirming. `qualityforge/tests/
test_reference_suite.py` runs these checks at baseline; the harness runner
runs the same file against each mutant.

The checks are deliberately derived from the acceptance criteria and the API
contract, not from implementation internals:

1. findings cover every configured criterion on every note (tests derive
   from criteria, spec section 7.6);
2. per-criterion statuses match the labels;
3. overall_status matches the label;
4. every present or partial finding carries evidence whose offsets follow
   the pinned R3 semantics against the raw note text (spec section 8.3);
5. two identical calls return identical responses (spec section 8.3
   determinism requirement).
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from qualityforge.harness.inject import EvaluateRequest, Evaluator

SuiteCheck = Callable[[Evaluator, Mapping[str, Any]], None]


@dataclass(frozen=True)
class LabeledNote:
    """A synthetic SOAP note with its hand-derived expected result (§8.4)."""

    note_id: str
    visit_type: str
    text: str
    expected_status: Mapping[str, str]
    expected_overall: str

    def request(self) -> EvaluateRequest:
        return {"note_id": self.note_id, "note_text": self.text, "visit_type": self.visit_type}


_ALL_PRESENT = {
    "S-01": "present",
    "S-02": "present",
    "O-01": "present",
    "O-02": "present",
    "A-01": "present",
    "P-01": "present",
    "P-02": "present",
    "X-01": "present",
}

NOTE_COMPLETE = LabeledNote(
    note_id="note-complete",
    visit_type="follow-up",
    text=(
        "S: Chief complaint: Persistent cough for five days.\n"
        "HPI: Patient reports a dry cough worsening at night, no fever.\n"
        "O: Vitals: Temp 37.1 C, HR 82, BP 118/76, SpO2 98 percent.\n"
        "Exam: Chest clear to auscultation bilaterally.\n"
        "A: Diagnosis: Acute bronchitis.\n"
        "P: Plan:\n"
        "- Continue supportive care for acute bronchitis.\n"
    ),
    expected_status=dict(_ALL_PRESENT),
    expected_overall="complete",
)

# The Objective section is absent entirely: O-01 and O-02 fail, and only
# three of the four sections are identifiable, so the Structure criterion is
# partial.
NOTE_MISSING_OBJECTIVE = LabeledNote(
    note_id="note-missing-objective",
    visit_type="follow-up",
    text=(
        "S: Chief complaint: Persistent cough for five days.\n"
        "HPI: Patient reports a dry cough worsening at night, no fever.\n"
        "A: Diagnosis: Acute bronchitis.\n"
        "P: Plan:\n"
        "- Continue supportive care for acute bronchitis.\n"
    ),
    expected_status=_ALL_PRESENT | {"O-01": "missing", "O-02": "missing", "X-01": "partial"},
    expected_overall="incomplete",
)

# Every section is present but the plan item never mentions the diagnosis,
# so the plan-relation criterion fails.
NOTE_UNRELATED_PLAN = LabeledNote(
    note_id="note-unrelated-plan",
    visit_type="follow-up",
    text=(
        "S: Chief complaint: Persistent cough for five days.\n"
        "HPI: Patient reports a dry cough worsening at night, no fever.\n"
        "O: Vitals: Temp 37.2 C, HR 84, BP 120/78, SpO2 98 percent.\n"
        "Exam: Chest clear to auscultation bilaterally.\n"
        "A: Diagnosis: Acute bronchitis.\n"
        "P: Plan:\n"
        "- Prescribe a seven-day course of physical therapy.\n"
    ),
    expected_status=_ALL_PRESENT | {"P-02": "missing"},
    expected_overall="incomplete",
)

# No Assessment section: A-01 fails, the plan cannot relate to a stated
# assessment, and the Structure criterion is partial.
NOTE_NO_ASSESSMENT = LabeledNote(
    note_id="note-no-assessment",
    visit_type="follow-up",
    text=(
        "S: Chief complaint: Persistent cough for five days.\n"
        "HPI: Patient reports a dry cough worsening at night, no fever.\n"
        "O: Vitals: Temp 37.0 C, HR 80, BP 116/74, SpO2 99 percent.\n"
        "Exam: Chest clear to auscultation bilaterally.\n"
        "P: Plan:\n"
        "- Continue supportive care and rest.\n"
    ),
    expected_status=_ALL_PRESENT | {"A-01": "missing", "P-02": "missing", "X-01": "partial"},
    expected_overall="incomplete",
)

REFERENCE_NOTES: tuple[LabeledNote, ...] = (
    NOTE_COMPLETE,
    NOTE_MISSING_OBJECTIVE,
    NOTE_UNRELATED_PLAN,
    NOTE_NO_ASSESSMENT,
)


def check_findings_cover_config_criteria(evaluator: Evaluator, config: Mapping[str, Any]) -> None:
    expected = {criterion["id"] for criterion in config["criteria"]}
    for note in REFERENCE_NOTES:
        response = evaluator(note.request())
        reported = {finding["criterion_id"] for finding in response["findings"]}
        assert reported == expected, (
            f"{note.note_id}: findings must cover every configured criterion "
            f"(missing {sorted(expected - reported)}, unexpected {sorted(reported - expected)})"
        )


def check_findings_match_labels(evaluator: Evaluator, config: Mapping[str, Any]) -> None:
    for note in REFERENCE_NOTES:
        response = evaluator(note.request())
        actual = {finding["criterion_id"]: finding["status"] for finding in response["findings"]}
        for criterion_id, expected in note.expected_status.items():
            assert actual.get(criterion_id) == expected, (
                f"{note.note_id}/{criterion_id}: expected {expected!r}, "
                f"got {actual.get(criterion_id)!r}"
            )


def check_overall_matches_label(evaluator: Evaluator, config: Mapping[str, Any]) -> None:
    for note in REFERENCE_NOTES:
        response = evaluator(note.request())
        assert response["overall_status"] == note.expected_overall, (
            f"{note.note_id}: expected overall {note.expected_overall!r}, "
            f"got {response['overall_status']!r}"
        )


def check_present_findings_carry_evidence(evaluator: Evaluator, config: Mapping[str, Any]) -> None:
    for note in REFERENCE_NOTES:
        response = evaluator(note.request())
        for finding in response["findings"]:
            if finding["status"] not in ("present", "partial"):
                continue
            assert finding["evidence"], (
                f"{note.note_id}/{finding['criterion_id']}: present or partial finding without "
                "evidence (spec section 8.3)"
            )
            for span in finding["evidence"]:
                start, end = span["start"], span["end"]
                assert 0 <= start < end <= len(note.text), (
                    f"{note.note_id}/{finding['criterion_id']}: evidence offsets out of bounds "
                    f"({start}, {end})"
                )
                assert note.text[start:end] == span["text"], (
                    f"{note.note_id}/{finding['criterion_id']}: evidence text does not match "
                    "note_text[start:end] — the pinned R3 span semantics are violated"
                )


def check_deterministic_responses(evaluator: Evaluator, config: Mapping[str, Any]) -> None:
    for note in REFERENCE_NOTES:
        first = json.dumps(evaluator(note.request()), sort_keys=True)
        second = json.dumps(evaluator(note.request()), sort_keys=True)
        assert first == second, f"{note.note_id}: repeated calls returned different responses"


REFERENCE_CHECKS: tuple[SuiteCheck, ...] = (
    check_findings_cover_config_criteria,
    check_findings_match_labels,
    check_overall_matches_label,
    check_present_findings_carry_evidence,
    check_deterministic_responses,
)
